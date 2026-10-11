"""
Serviço — Importação de Vidas da Planilha Copacabana Hotel IT

Lê a planilha no formato:
  Sub | Modulos | Nomes | Data de Nascimento | CPF | Data de Admissao | Salario | Cargos

e persiste diretamente no DB2 (tabelas SEGURADO + COBERTURA)
compartilhado com o CICS, gerando também um registro em
IMPORTACAO_VIDAS para rastreabilidade e consulta via COBOL.

Fluxo:
  1. parse_planilha_vidas()  — lê e valida o arquivo
  2. gravar_vidas_db2()      — persiste no DB2 via ibm_db
  3. COBOL LCVIDAS01 (batch) — lê IMPORTACAO_VIDAS, aplica VGCCAP01
     e atualiza STATUS para 'OK'
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Mapa de alias para o formato da planilha Copacabana ───────────────────────
# Aceita tanto o formato informado quanto variantes comuns.
_ALIAS: dict[str, list[str]] = {
    "subestipulante": [
        "sub",
        "subestipulante",
        "sub_estipulante",
        "filial",
        "unidade",
    ],
    "modulo": ["modulos", "modulo", "plano", "cobertura", "grupo"],
    "nome_segurado": [
        "nomes",
        "nome",
        "nome_segurado",
        "colaborador",
        "funcionario",
    ],
    "dt_nascimento": [
        "data_de_nascimento",
        "data_nascimento",
        "dt_nascimento",
        "nascimento",
        "data_nasc",
    ],
    "cpf": ["cpf", "cpf_segurado", "documento"],
    "dt_admissao": [
        "data_de_admissao",
        "data_admissao",
        "dt_admissao",
        "admissao",
        "dt_inclusao",
        "data_de_inclusao",
    ],
    "vl_salario": [
        "salario",
        "salário",
        "vl_salario",
        "remuneracao",
        "remuneração",
        "salario_base",
    ],
    "cargo": [
        "cargos",
        "cargo",
        "funcao",
        "função",
        "perfil",
        "nivel",
        "categoria",
    ],
}

# Fator multiplicador padrão por cargo (VGC Escalonado)
_FATOR_CARGO: dict[str, float] = {
    "diretoria": 6.0,
    "diretor": 6.0,
    "diretor(a)": 6.0,
    "gerente": 5.0,
    "gerencial": 5.0,
    "coordenador": 4.0,
    "coordenador(a)": 4.0,
    "supervisor": 4.0,
    "supervisor(a)": 4.0,
    "funcionario": 3.0,
    "funcionário": 3.0,
    "funcionario(a)": 3.0,
    "funcionária(a)": 3.0,
    "operacional": 3.0,
    "assistente": 2.0,
    "estagiario": 1.0,
    "estagiário": 1.0,
}


def _norm(s: str) -> str:
    """Normaliza: lowercase, sem acento, espaços→underscore."""
    t = unicodedata.normalize("NFKD", str(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[\s]+", "_", t.strip().lower())


def _mapear_colunas(cabecalho: list[str]) -> dict[str, str]:
    """Retorna {canonical_name: real_column_name}."""
    cab_norm = {_norm(c): c for c in cabecalho}
    mapa: dict[str, str] = {}
    for canonico, aliases in _ALIAS.items():
        for alias in aliases:
            if alias in cab_norm:
                mapa[canonico] = cab_norm[alias]
                break
    return mapa


def _limpar_cpf(v: Any) -> str:
    cpf = re.sub(r"[^\d]", "", str(v or ""))
    if len(cpf) < 11:
        cpf = cpf.zfill(11)
    if len(cpf) != 11:
        raise ValueError(f"CPF inválido: {v!r}")
    return cpf


def _parsear_data(v: Any) -> str:
    """Retorna AAAAMMDD ou '' se vazio."""
    if v is None or str(v).strip() == "":
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y%m%d")
    s = str(v).strip()
    if re.match(r"^\d{8}$", s):
        return s
    m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", s)
    if m:
        d, mo, a = m.groups()
        return f"{a}{mo.zfill(2)}{d.zfill(2)}"
    m = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m:
        a, mo, d = m.groups()
        return f"{a}{mo.zfill(2)}{d.zfill(2)}"
    raise ValueError(f"Formato de data não reconhecido: {s!r}")


def _parsear_valor(v: Any) -> float | None:
    if v is None or str(v).strip() in ("", "-", "0"):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = re.sub(r"[R$\s]", "", str(v).strip())
    if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(,\d{3})*\.\d{2}$", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None


# ── Estruturas de resultado ───────────────────────────────────────────────────


@dataclass
class VidaImportada:
    linha: int
    cpf: str
    nome: str
    dt_nascimento: str
    dt_admissao: str
    subestipulante: str | None
    modulo: str | None
    cargo: str | None
    vl_salario: float | None
    nr_fator_mult: float | None
    vl_capital: float | None        # calculado = salario × fator
    sucesso: bool = True
    erros: list[str] = field(default_factory=list)


@dataclass
class ResultadoImportacaoVidas:
    id_importacao: str
    nr_apolice: str
    total_linhas: int = 0
    total_sucesso: int = 0
    total_erros: int = 0
    vidas: list[VidaImportada] = field(default_factory=list)
    sumario_sub: dict[str, int] = field(default_factory=dict)
    erros: list[dict] = field(default_factory=list)


# ── Parsers de arquivo ────────────────────────────────────────────────────────


def _parse_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    cabecalho = [str(c).strip() if c is not None else "" for c in rows[0]]
    linhas = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        linhas.append(dict(zip(cabecalho, row)))
    return cabecalho, linhas


def _parse_csv(content: bytes) -> tuple[list[str], list[dict]]:
    text = content.decode("utf-8-sig")
    sep = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    cabecalho = list(reader.fieldnames or [])
    return cabecalho, list(reader)


# ── Processamento de linha ────────────────────────────────────────────────────


def _processar_linha(nr: int, row: dict, mapa: dict[str, str]) -> VidaImportada:
    def g(campo: str) -> str:
        col = mapa.get(campo)
        return str(row.get(col) or "").strip() if col else ""

    erros: list[str] = []

    # CPF
    try:
        cpf = _limpar_cpf(g("cpf"))
    except ValueError as e:
        cpf = g("cpf")
        erros.append(str(e))

    # Nome
    nome = g("nome_segurado")
    if not nome:
        erros.append("Nome obrigatório.")

    # Data de nascimento
    try:
        dt_nasc = _parsear_data(row.get(mapa.get("dt_nascimento", ""), ""))
    except ValueError as e:
        dt_nasc = ""
        erros.append(f"Data de nascimento: {e}")

    # Data de admissão
    try:
        dt_adm_raw = row.get(mapa.get("dt_admissao", ""), "")
        dt_adm = _parsear_data(dt_adm_raw)
        if not dt_adm:
            raise ValueError("vazia")
    except ValueError as e:
        dt_adm = ""
        erros.append(f"Data de admissão: {e}")

    # Campos opcionais
    sub = g("subestipulante") or None
    modulo = g("modulo") or None
    cargo = g("cargo") or None

    vl_sal = _parsear_valor(row.get(mapa.get("vl_salario", ""), None))
    fator = _FATOR_CARGO.get((cargo or "").lower().strip())
    vl_capital = round(vl_sal * fator, 2) if (vl_sal and fator) else None

    return VidaImportada(
        linha=nr,
        cpf=cpf,
        nome=nome.upper()[:60],
        dt_nascimento=dt_nasc,
        dt_admissao=dt_adm,
        subestipulante=sub,
        modulo=modulo,
        cargo=cargo,
        vl_salario=vl_sal,
        nr_fator_mult=fator,
        vl_capital=vl_capital,
        sucesso=len(erros) == 0,
        erros=erros,
    )


# ── Função pública principal ──────────────────────────────────────────────────


def parse_planilha_vidas(
    filename: str,
    content: bytes,
    nr_apolice: str,
) -> ResultadoImportacaoVidas:
    """
    Lê a planilha e retorna ResultadoImportacaoVidas pronto para
    ser persistido no DB2 via gravar_vidas_db2().

    Formato aceito: .xlsx · .csv
    Colunas reconhecidas: Sub | Modulos | Nomes | Data de Nascimento |
                          CPF | Data de Admissao | Salario | Cargos
    """
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        cabecalho, linhas_raw = _parse_xlsx(content)
    elif ext == ".csv":
        cabecalho, linhas_raw = _parse_csv(content)
    else:
        raise ValueError(f"Formato '{ext}' não suportado. Use .xlsx ou .csv")

    if not linhas_raw:
        raise ValueError("Planilha vazia ou sem dados após o cabeçalho.")

    mapa = _mapear_colunas(cabecalho)
    faltando = [c for c in ("nome_segurado", "cpf", "dt_admissao") if c not in mapa]
    if faltando:
        raise ValueError(
            f"Colunas obrigatórias não encontradas: {faltando}. "
            f"Colunas detectadas: {cabecalho}"
        )

    resultado = ResultadoImportacaoVidas(
        id_importacao=str(uuid.uuid4()),
        nr_apolice=nr_apolice,
        total_linhas=len(linhas_raw),
    )

    for i, row in enumerate(linhas_raw, start=2):
        vida = _processar_linha(i, row, mapa)
        resultado.vidas.append(vida)
        if vida.sucesso:
            resultado.total_sucesso += 1
            sub = vida.subestipulante or "SEM SUB"
            resultado.sumario_sub[sub] = resultado.sumario_sub.get(sub, 0) + 1
        else:
            resultado.total_erros += 1
            resultado.erros.append(
                {"linha": vida.linha, "cpf": vida.cpf, "nome": vida.nome, "erros": vida.erros}
            )

    return resultado


# ── Persistência no DB2 ───────────────────────────────────────────────────────


def gravar_vidas_db2(
    resultado: ResultadoImportacaoVidas,
    cd_empresa: int,
    cd_empresa_sub1: int,
    cd_empresa_sub2: int,
    usuario: str,
    schema: str = "LIFECORE",
) -> dict[str, Any]:
    """
    Persiste no DB2:
      • SEGURADO       — cadastro do funcionário (upsert por CPF)
      • COBERTURA      — cobertura individual vinculada à apólice
      • IMPORTACAO_VIDAS — registro de rastreabilidade para o COBOL

    Retorna resumo da operação.
    """
    from app.repositories.empresa_db2 import _close, _connect, _prepare

    dt_hoje = datetime.now(UTC).strftime("%Y%m%d")
    id_usuario = usuario[:8].upper().ljust(8)
    nr_apolice = resultado.nr_apolice
    id_imp = resultado.id_importacao

    ibm_db, conn = _connect()
    gravados = 0
    erros_db2: list[dict] = []

    try:
        # Registro de cabeçalho do lote
        _prepare(
            ibm_db, conn,
            f"INSERT INTO {schema}.IMPORTACAO_VIDAS "
            "(ID_IMPORTACAO, NR_APOLICE, CD_EMPRESA, QT_REGISTROS, "
            " QT_VALIDOS, QT_ERROS, CD_STATUS, DT_IMPORTACAO, ID_USUARIO) "
            "VALUES (?, ?, ?, ?, ?, ?, 'PE', ?, ?)",
            (
                id_imp,
                nr_apolice,
                cd_empresa,
                resultado.total_linhas,
                resultado.total_sucesso,
                resultado.total_erros,
                dt_hoje,
                id_usuario,
            ),
        )

        for vida in resultado.vidas:
            if not vida.sucesso:
                continue

            # Determina empresa do substipulante pelo campo Sub da planilha
            sub_num = str(vida.subestipulante or "").strip()
            if sub_num == "1":
                cd_sub = cd_empresa_sub1
            elif sub_num == "2":
                cd_sub = cd_empresa_sub2
            else:
                cd_sub = cd_empresa

            try:
                # UPSERT SEGURADO (INSERT … ON CONFLICT ignored via SQLCODE)
                try:
                    _prepare(
                        ibm_db, conn,
                        f"INSERT INTO {schema}.SEGURADO "
                        "(CD_CPF, NM_SEGURADO, DT_NASCIMENTO, CD_EMPRESA, "
                        " VL_SALARIO, DT_ADMISSAO, DT_INCLUSAO, ID_USUARIO_INCL) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            vida.cpf,
                            vida.nome,
                            vida.dt_nascimento or dt_hoje,
                            cd_sub,
                            vida.vl_salario or 0.00,
                            vida.dt_admissao or dt_hoje,
                            dt_hoje,
                            id_usuario,
                        ),
                    )
                except Exception as dup:
                    # CPF já existe → UPDATE salário/empresa/admissão
                    if "-803" in str(dup) or "23505" in str(dup) or "duplicate" in str(dup).lower():
                        _prepare(
                            ibm_db, conn,
                            f"UPDATE {schema}.SEGURADO "
                            "SET NM_SEGURADO=?, DT_NASCIMENTO=?, CD_EMPRESA=?, "
                            "    VL_SALARIO=?, DT_ADMISSAO=? "
                            "WHERE CD_CPF=?",
                            (
                                vida.nome,
                                vida.dt_nascimento or dt_hoje,
                                cd_sub,
                                vida.vl_salario or 0.00,
                                vida.dt_admissao or dt_hoje,
                                vida.cpf,
                            ),
                        )
                    else:
                        raise

                # COBERTURA individual
                cd_cob = f"COB{vida.cpf[:11]}"[:16]
                vl_cap = vida.vl_capital or 0.00
                try:
                    _prepare(
                        ibm_db, conn,
                        f"INSERT INTO {schema}.COBERTURA "
                        "(CD_COBERTURA, NR_APOLICE, CD_TIPO, NM_COBERTURA, "
                        " VL_CAPITAL, NR_CARENCIA_DIAS, CD_STATUS) "
                        "VALUES (?, ?, 'MORT', ?, ?, 0, 'AT')",
                        (
                            cd_cob,
                            nr_apolice,
                            f"Morte — {vida.nome[:40]}",
                            vl_cap,
                        ),
                    )
                except Exception as dup_cob:
                    if "-803" in str(dup_cob) or "23505" in str(dup_cob) or "duplicate" in str(dup_cob).lower():
                        _prepare(
                            ibm_db, conn,
                            f"UPDATE {schema}.COBERTURA "
                            "SET VL_CAPITAL=?, NM_COBERTURA=? "
                            "WHERE CD_COBERTURA=?",
                            (
                                vl_cap,
                                f"Morte — {vida.nome[:40]}",
                                cd_cob,
                            ),
                        )
                    else:
                        raise

                # Item do lote
                _prepare(
                    ibm_db, conn,
                    f"INSERT INTO {schema}.IMPORTACAO_VIDAS_ITEM "
                    "(ID_IMPORTACAO, NR_LINHA, CD_CPF, NM_SEGURADO, "
                    " CD_SUBESTIPULANTE, CD_MODULO, CD_CARGO, "
                    " VL_SALARIO, NR_FATOR_MULT, VL_CAPITAL, "
                    " DT_ADMISSAO, CD_STATUS) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OK')",
                    (
                        id_imp,
                        vida.linha,
                        vida.cpf,
                        vida.nome,
                        vida.subestipulante or "",
                        vida.modulo or "",
                        vida.cargo or "",
                        vida.vl_salario or 0.00,
                        vida.nr_fator_mult or 1.00,
                        vl_cap,
                        vida.dt_admissao or dt_hoje,
                    ),
                )
                gravados += 1

            except Exception as exc:
                erros_db2.append(
                    {"linha": vida.linha, "cpf": vida.cpf, "erro": str(exc)}
                )

        # Atualiza status do lote
        novo_status = "OK" if not erros_db2 else "PA"
        _prepare(
            ibm_db, conn,
            f"UPDATE {schema}.IMPORTACAO_VIDAS "
            "SET CD_STATUS=?, QT_GRAVADOS=? "
            "WHERE ID_IMPORTACAO=?",
            (novo_status, gravados, id_imp),
        )

        ibm_db.commit(conn)

    except Exception:
        ibm_db.rollback(conn)
        raise
    finally:
        _close(ibm_db, conn)

    return {
        "id_importacao": id_imp,
        "nr_apolice": nr_apolice,
        "cd_status": novo_status,
        "total_linhas": resultado.total_linhas,
        "total_gravados": gravados,
        "total_erros_planilha": resultado.total_erros,
        "total_erros_db2": len(erros_db2),
        "sumario_sub": resultado.sumario_sub,
        "erros_db2": erros_db2[:20],
    }
