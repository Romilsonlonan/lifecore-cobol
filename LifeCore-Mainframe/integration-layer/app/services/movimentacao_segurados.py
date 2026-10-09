"""
Serviço — Importação de Movimentação de Segurados via Planilha

Lê um arquivo Excel (.xlsx) ou CSV (.csv) com a movimentação mensal de segurados
e converte cada linha em um EndossoSeguradorRequest pronto para ser processado.

Layout da planilha (colunas, nomes flexíveis — mapeamento por alias):
┌────────────────────┬─────────────┬────────────────────────────────────────────────┐
│ Coluna             │ Obrigatório │ Valores aceitos / formato                      │
├────────────────────┼─────────────┼────────────────────────────────────────────────┤
│ subestipulante     │ Não         │ Texto livre, ex: "SUB1", "Sub São Paulo"        │
│ modulo / módulo    │ Não         │ Código ou nome do módulo de cobertura          │
│ nome_segurado      │ Sim         │ Nome completo                                  │
│ cpf                │ Sim         │ 11 dígitos, com ou sem máscara                 │
│ dt_nascimento      │ Não         │ DD/MM/AAAA ou AAAAMMDD ou DD-MM-AAAA           │
│ dt_inclusao        │ Sim         │ DD/MM/AAAA ou AAAAMMDD — data de início cobert.│
│ cargo              │ Não         │ "Gerencial", "Funcionario", "Diretoria", etc.  │
│ tp_movimentacao    │ Não         │ INC/EXC/CAP/SAL/SUS/REA (default: INC)        │
│ vl_capital         │ Não         │ Número, ex: 200000 ou 200.000,00              │
│ vl_salario         │ Não         │ Número — obrigatório quando capital tipo M     │
│ nr_fator_mult      │ Não         │ Número — multiplicador salarial, ex: 3.0       │
│ cd_motivo          │ Não         │ Código até 4 chars, ex: ADMS, DEMI            │
│ ds_observacao      │ Não         │ Texto livre até 200 chars                     │
└────────────────────┴─────────────┴────────────────────────────────────────────────┘

Regras de mapeamento de cargo → fator_mult / capital:
  - Gerencial / Diretoria  → fator_mult = 5.0  se tp_capital = M
  - Funcionario / Operacional → fator_mult = 3.0  se tp_capital = M
  - Campos explícitos na planilha sobrepõem os defaults de cargo.

Retorno:
  MovimentacaoResult com listas de sucessos, erros e sumário por subestipulante.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Mapeamento de alias de colunas ────────────────────────────────────────────
# Cada entrada lista os nomes aceitos (lowercase, sem acento) para a mesma coluna.
_ALIAS: dict[str, list[str]] = {
    "subestipulante": [
        "subestipulante",
        "sub",
        "sub_estipulante",
        "subeestipulante",
        "filial",
        "unidade",
        "departamento",
    ],
    "modulo": ["modulo", "módulo", "plano", "grupo", "cobertura"],
    "nome_segurado": [
        "nome_segurado",
        "nome",
        "nm_segurado",
        "funcionario",
        "funcionário",
        "colaborador",
        "beneficiario",
        "beneficiário",
    ],
    "cpf": ["cpf", "cpf_segurado", "cd_cpf", "documento"],
    "dt_nascimento": [
        "dt_nascimento",
        "data_nascimento",
        "nascimento",
        "dt_nasc",
        "data_nasc",
        "data_de_nascimento",
        "data nasc",
        "data de nascimento",
    ],
    "dt_inclusao": [
        "dt_inclusao",
        "data_inclusao",
        "inclusao",
        "dt_inicio",
        "data inicio",
        "data de inclusao",
        "data_admissao",
        "dt_admissao",
        "admissao",
        "data admissao",
        "data de inclusao",
        "data_de_inclusao",
        "admissão",
        "data de admissao",
    ],
    "cargo": [
        "cargo",
        "funcao",
        "função",
        "perfil",
        "categoria",
        "nivel",
        "nível",
        "tipo_funcionario",
    ],
    "tp_movimentacao": [
        "tp_movimentacao",
        "tipo",
        "movimentacao",
        "movimentação",
        "operacao",
        "operação",
        "acao",
        "ação",
    ],
    "vl_capital": [
        "vl_capital",
        "capital",
        "capital_segurado",
        "valor_capital",
        "valor capital",
    ],
    "vl_salario": [
        "vl_salario",
        "salario",
        "salário",
        "vl_salario_base",
        "salario_base",
        "remuneracao",
        "remuneração",
    ],
    "nr_fator_mult": [
        "nr_fator_mult",
        "fator",
        "fator_mult",
        "multiplicador",
        "fator_multiplicador",
    ],
    "cd_motivo": ["cd_motivo", "motivo", "cod_motivo", "codigo_motivo"],
    "ds_observacao": [
        "ds_observacao",
        "observacao",
        "observação",
        "obs",
        "comentario",
        "comentário",
    ],
}

# Defaults de fator_mult por cargo (usado quando tp_capital = M e fator não informado)
_FATOR_POR_CARGO: dict[str, float] = {
    "diretoria": 6.0,
    "gerencial": 5.0,
    "gerente": 5.0,
    "coordenador": 4.0,
    "supervisor": 4.0,
    "funcionario": 3.0,
    "funcionário": 3.0,
    "operacional": 3.0,
    "assistente": 2.0,
    "aprendiz": 1.0,
    "estagiario": 1.0,
    "estagiário": 1.0,
}


@dataclass
class LinhaProcessada:
    linha: int
    cpf: str
    nome: str
    subestipulante: str | None
    modulo: str | None
    cargo: str | None
    dt_nascimento: str | None
    dt_inclusao: str
    tp_movimentacao: str
    vl_capital: float | None
    vl_salario: float | None
    nr_fator_mult: float | None
    cd_motivo: str | None
    ds_observacao: str | None
    # Resultado do processamento
    sucesso: bool = True
    erro: str | None = None


@dataclass
class MovimentacaoResult:
    total_linhas: int = 0
    total_sucesso: int = 0
    total_erros: int = 0
    linhas: list[LinhaProcessada] = field(default_factory=list)
    erros: list[dict] = field(default_factory=list)
    sumario_sub: dict[str, int] = field(default_factory=dict)
    # Endossos montados — prontos para POST /endossos
    endossos: list[dict] = field(default_factory=list)


# ── Utilitários ───────────────────────────────────────────────────────────────


def _normalizar_col(nome: str) -> str:
    """Remove acentos, lowercase, espaços→underscore."""
    import unicodedata

    s = unicodedata.normalize("NFKD", str(nome or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", "_", s.strip().lower())


def _mapear_colunas(cabecalho: list[str]) -> dict[str, str]:
    """
    Recebe o cabeçalho bruto da planilha e retorna
    { nome_canonico: nome_real_na_planilha }.
    """
    cab_norm = {_normalizar_col(c): c for c in cabecalho}
    mapa: dict[str, str] = {}
    for canonico, aliases in _ALIAS.items():
        for alias in aliases:
            if alias in cab_norm:
                mapa[canonico] = cab_norm[alias]
                break
    return mapa


def _limpar_cpf(valor: str) -> str:
    """Remove máscara e valida tamanho."""
    cpf = re.sub(r"[^\d]", "", str(valor or ""))
    if len(cpf) != 11:
        raise ValueError(f"CPF inválido: {valor!r} → '{cpf}' (esperado 11 dígitos)")
    return cpf


def _parsear_data(valor) -> str:
    """
    Aceita vários formatos e retorna AAAAMMDD.
    Suporta: datetime/date nativo (openpyxl), DD/MM/AAAA, AAAA-MM-DD, AAAAMMDD.
    """
    if valor is None or str(valor).strip() == "":
        return ""
    # Objeto date/datetime do openpyxl
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y%m%d")
    s = str(valor).strip()
    # AAAAMMDD já ok
    if re.match(r"^\d{8}$", s):
        return s
    # DD/MM/AAAA ou DD-MM-AAAA
    m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", s)
    if m:
        d, mo, a = m.groups()
        return f"{a}{mo.zfill(2)}{d.zfill(2)}"
    # AAAA-MM-DD ou AAAA/MM/DD
    m = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m:
        a, mo, d = m.groups()
        return f"{a}{mo.zfill(2)}{d.zfill(2)}"
    raise ValueError(f"Formato de data não reconhecido: {s!r}")


def _parsear_valor(valor) -> float | None:
    """Converte string monetária para float. Ex: '200.000,00' → 200000.0"""
    if valor is None or str(valor).strip() in ("", "-", "0"):
        return None
    if isinstance(valor, (int, float)):
        return float(valor) if valor > 0 else None
    s = str(valor).strip()
    # Remove R$, espaços
    s = re.sub(r"[R$\s]", "", s)
    # Formato BR: 200.000,00
    if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    # Formato EN: 200,000.00
    elif re.match(r"^\d{1,3}(,\d{3})*\.\d{2}$", s):
        s = s.replace(",", "")
    # Apenas vírgula como decimal: 200000,00
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _tp_movimentacao(valor: str | None) -> str:
    """Normaliza tipo de movimentação. Default = INC."""
    if not valor:
        return "INC"
    v = str(valor).strip().upper()
    _mapa = {
        "INC": "INC",
        "INCLUSAO": "INC",
        "INCLUSÃO": "INC",
        "ADMISSAO": "INC",
        "ADMISSÃO": "INC",
        "NOVO": "INC",
        "ENTRADA": "INC",
        "EXC": "EXC",
        "EXCLUSAO": "EXC",
        "EXCLUSÃO": "EXC",
        "DEMISSAO": "EXC",
        "DEMISSÃO": "EXC",
        "SAIDA": "EXC",
        "SAÍDA": "EXC",
        "DESLIGAMENTO": "EXC",
        "CAP": "CAP",
        "ALTERACAO_CAP": "CAP",
        "ALTERAÇÃO_CAP": "CAP",
        "ALTERACAO": "CAP",
        "ALTERAÇÃO": "CAP",
        "CAPITAL": "CAP",
        "SAL": "SAL",
        "ALTERACAO_SAL": "SAL",
        "SALARIO": "SAL",
        "SALÁRIO": "SAL",
        "SUS": "SUS",
        "SUSPENSAO": "SUS",
        "SUSPENSÃO": "SUS",
        "REA": "REA",
        "REATIVACAO": "REA",
        "REATIVAÇÃO": "REA",
        "RETORNO": "REA",
        "REINTEGRACAO": "REA",
    }
    return _mapa.get(v, "INC")


def _processar_linha(
    nr_linha: int,
    row: dict,
    mapa: dict[str, str],
    nr_apolice: str,
    id_usuario: str,
) -> LinhaProcessada:
    """Converte uma linha da planilha em LinhaProcessada."""

    def _get(campo: str) -> str:
        col = mapa.get(campo)
        if not col:
            return ""
        return str(row.get(col) or "").strip()

    # Campos obrigatórios
    cpf_raw = _get("cpf")
    nome_raw = _get("nome_segurado")

    try:
        cpf = _limpar_cpf(cpf_raw)
    except ValueError as e:
        return LinhaProcessada(
            linha=nr_linha,
            cpf=cpf_raw,
            nome=nome_raw,
            subestipulante=None,
            modulo=None,
            cargo=None,
            dt_nascimento=None,
            dt_inclusao="",
            tp_movimentacao="INC",
            vl_capital=None,
            vl_salario=None,
            nr_fator_mult=None,
            cd_motivo=None,
            ds_observacao=None,
            sucesso=False,
            erro=str(e),
        )

    if not nome_raw:
        return LinhaProcessada(
            linha=nr_linha,
            cpf=cpf,
            nome="",
            subestipulante=None,
            modulo=None,
            cargo=None,
            dt_nascimento=None,
            dt_inclusao="",
            tp_movimentacao="INC",
            vl_capital=None,
            vl_salario=None,
            nr_fator_mult=None,
            cd_motivo=None,
            ds_observacao=None,
            sucesso=False,
            erro="Nome do segurado obrigatório.",
        )

    # Data de inclusão
    try:
        dt_inc_raw = row.get(mapa.get("dt_inclusao", ""), "")
        dt_inclusao = _parsear_data(dt_inc_raw)
        if not dt_inclusao:
            raise ValueError("Data de inclusão vazia.")
    except ValueError as e:
        return LinhaProcessada(
            linha=nr_linha,
            cpf=cpf,
            nome=nome_raw,
            subestipulante=None,
            modulo=None,
            cargo=None,
            dt_nascimento=None,
            dt_inclusao="",
            tp_movimentacao="INC",
            vl_capital=None,
            vl_salario=None,
            nr_fator_mult=None,
            cd_motivo=None,
            ds_observacao=None,
            sucesso=False,
            erro=f"Data de inclusão inválida: {e}",
        )

    # Data de nascimento (opcional)
    try:
        dt_nasc_raw = row.get(mapa.get("dt_nascimento", ""), "")
        dt_nascimento = _parsear_data(dt_nasc_raw) or None
    except ValueError:
        dt_nascimento = None

    # Campos opcionais
    sub = _get("subestipulante") or None
    modulo = _get("modulo") or None
    cargo = _get("cargo") or None
    tp_mov = _tp_movimentacao(_get("tp_movimentacao"))

    vl_cap_raw = row.get(mapa.get("vl_capital", ""), None)
    vl_sal_raw = row.get(mapa.get("vl_salario", ""), None)
    fat_raw = row.get(mapa.get("nr_fator_mult", ""), None)

    vl_cap = _parsear_valor(vl_cap_raw)
    vl_sal = _parsear_valor(vl_sal_raw)
    nr_fat = _parsear_valor(fat_raw)

    # Default de fator_mult por cargo (se não informado explicitamente)
    if nr_fat is None and cargo:
        nr_fat = _FATOR_POR_CARGO.get(cargo.lower().strip())

    cd_motivo = _get("cd_motivo")[:4] or None
    ds_observacao = _get("ds_observacao")[:200] or None

    # Monta observação automática com subestipulante e módulo
    obs_partes = []
    if sub:
        obs_partes.append(f"Sub: {sub}")
    if modulo:
        obs_partes.append(f"Módulo: {modulo}")
    if cargo:
        obs_partes.append(f"Cargo: {cargo}")
    if dt_nascimento:
        obs_partes.append(f"Nasc: {dt_nascimento}")
    obs_auto = " | ".join(obs_partes)
    # Combina observação automática com a do operador
    obs_final = obs_auto
    if ds_observacao:
        obs_final = f"{obs_auto} | {ds_observacao}" if obs_auto else ds_observacao
    obs_final = obs_final[:200] or None

    return LinhaProcessada(
        linha=nr_linha,
        cpf=cpf,
        nome=nome_raw.upper(),
        subestipulante=sub,
        modulo=modulo,
        cargo=cargo,
        dt_nascimento=dt_nascimento,
        dt_inclusao=dt_inclusao,
        tp_movimentacao=tp_mov,
        vl_capital=vl_cap,
        vl_salario=vl_sal,
        nr_fator_mult=nr_fat,
        cd_motivo=cd_motivo,
        ds_observacao=obs_final,
        sucesso=True,
        erro=None,
    )


def _linha_para_endosso(
    linha: LinhaProcessada, nr_apolice: str, id_usuario: str
) -> dict:
    """Converte LinhaProcessada → payload de EndossoSeguradorRequest."""
    return {
        "cd_cpf_segurado": linha.cpf,
        "nm_segurado": linha.nome,
        "tp_endosso": linha.tp_movimentacao,
        "dt_inicio_vigencia": linha.dt_inclusao,
        "vl_capital": linha.vl_capital,
        "vl_salario_base": linha.vl_salario,
        "nr_fator_mult": linha.nr_fator_mult,
        "cd_motivo": linha.cd_motivo,
        "ds_observacao": linha.ds_observacao,
        "id_usuario": id_usuario,
        # Campos extras (não vão para o endosso, ficam no contexto)
        "_subestipulante": linha.subestipulante,
        "_modulo": linha.modulo,
        "_cargo": linha.cargo,
        "_dt_nascimento": linha.dt_nascimento,
        "_linha_planilha": linha.linha,
    }


# ── Parsers ───────────────────────────────────────────────────────────────────


def _parse_rows_csv(content: bytes) -> tuple[list[str], list[dict]]:
    """Retorna (cabecalho, linhas)."""
    text = content.decode("utf-8-sig")
    sep = ";" if text.count(";") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    cabecalho = list(reader.fieldnames or [])
    linhas = list(reader)
    return cabecalho, linhas


def _parse_rows_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    """Retorna (cabecalho, linhas) a partir do XLSX."""
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


# ── Função principal ──────────────────────────────────────────────────────────


def processar_movimentacao(
    filename: str,
    content: bytes,
    nr_apolice: str,
    id_usuario: str,
) -> MovimentacaoResult:
    """
    Lê a planilha e processa cada linha como uma movimentação de segurado.

    Retorna MovimentacaoResult com:
      - linhas processadas (sucesso + erros)
      - endossos prontos para disparar via API
      - sumário por subestipulante
    """
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        cabecalho, linhas_raw = _parse_rows_xlsx(content)
    elif ext == ".csv":
        cabecalho, linhas_raw = _parse_rows_csv(content)
    else:
        raise ValueError(f"Formato '{ext}' não suportado. Use .xlsx ou .csv")

    if not linhas_raw:
        raise ValueError("Planilha vazia ou sem dados após o cabeçalho.")

    mapa = _mapear_colunas(cabecalho)

    # Valida colunas obrigatórias
    faltando = [c for c in ("nome_segurado", "cpf", "dt_inclusao") if c not in mapa]
    if faltando:
        raise ValueError(
            f"Colunas obrigatórias não encontradas na planilha: {faltando}. "
            f"Colunas detectadas: {cabecalho}"
        )

    result = MovimentacaoResult(total_linhas=len(linhas_raw))

    for i, row in enumerate(linhas_raw, start=2):  # linha 1 = cabeçalho
        linha = _processar_linha(i, row, mapa, nr_apolice, id_usuario)
        result.linhas.append(linha)

        if linha.sucesso:
            result.total_sucesso += 1
            endosso = _linha_para_endosso(linha, nr_apolice, id_usuario)
            result.endossos.append(endosso)
            # Sumário por subestipulante
            sub = linha.subestipulante or "SEM SUBESTIPULANTE"
            result.sumario_sub[sub] = result.sumario_sub.get(sub, 0) + 1
        else:
            result.total_erros += 1
            result.erros.append(
                {
                    "linha": linha.linha,
                    "cpf": linha.cpf,
                    "nome": linha.nome,
                    "erro": linha.erro,
                }
            )

    return result
