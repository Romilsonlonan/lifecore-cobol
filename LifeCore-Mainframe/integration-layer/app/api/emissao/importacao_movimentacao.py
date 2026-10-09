"""
Importação de Movimentação de Segurados via Planilha

POST /api/emissao/apolices/{nr_apolice}/movimentacao/importar
     Upload de planilha Excel ou CSV. Processa cada linha como endosso
     e retorna o resultado consolidado com sumário por subestipulante.

POST /api/emissao/apolices/{nr_apolice}/movimentacao/importar?modo=dry_run
     Valida a planilha sem gravar nenhum endosso (simulação).

GET  /api/emissao/apolices/{nr_apolice}/movimentacao/template
     Retorna o template CSV de exemplo para o operador preencher.

GET  /api/emissao/movimentacao/template.xlsx
     Download do template Excel com instruções.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi import Path as FPath
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.emissao.criticas_router import (
    registrar_critica_pendente,
    registrar_endosso_pendente_liberacao,
)
from app.api.emissao.faturamento import (
    _COBERTURAS,
    _ENDOSSOS,
    _calcular_capital,
    _calcular_premio,
    _gerar_nr_endosso,
    _get_apolice_or_404,
    _now,
    _taxa_mensal_vigente,
)
from app.schemas.lifecore import (
    StatusApoliceEnum,
    StatusCoberturaEnum,
    StatusEndossoEnum,
)
from app.services.criticas_segurado import (
    executar_criticas,
)
from app.services.movimentacao_segurados import (
    MovimentacaoResult,
    processar_movimentacao,
)

router = APIRouter()
router_templates = APIRouter()  # montado em /api/emissao (sem {nr_apolice})

_EXTENSOES = {".csv", ".xlsx", ".xls"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Schemas de resposta ───────────────────────────────────────────────────────


class CriticaItem(BaseModel):
    codigo: str
    severidade: str
    descricao: str
    orientacao: str
    valor_informado: str | None = None
    fl_liberavel: bool = False
    id_critica: str | None = None  # preenchido quando MANU é registrada


class EndossoProcessadoItem(BaseModel):
    linha_planilha: int
    cpf: str
    nome: str
    subestipulante: str | None
    modulo: str | None
    cargo: str | None
    tp_movimentacao: str
    dt_inclusao: str
    dt_nascimento: str | None
    nr_endosso: str | None = None
    vl_capital: float | None = None
    vl_premio_bruto: float | None = None
    status: str = "OK"  # OK | DRY_RUN | CRITICA_MANU | AVISO | ERRO
    mensagem: str | None = None
    criticas: list[CriticaItem] = []  # alertas e críticas MANU associadas


class ErroImportacaoItem(BaseModel):
    linha_planilha: int
    cpf: str
    nome: str
    erro: str
    criticas: list[CriticaItem] = []


class MovimentacaoImportacaoResponse(BaseModel):
    nr_apolice: str
    cd_competencia: str | None
    dry_run: bool
    total_linhas: int
    total_sucesso: int
    total_erros: int
    total_pendente_manu: int = 0
    sumario_sub: dict[str, int]
    sucesso: list[EndossoProcessadoItem]
    erros: list[ErroImportacaoItem]
    ts_processamento: datetime


# ── Template CSV ──────────────────────────────────────────────────────────────

_TEMPLATE_CSV_HEADER = (
    "subestipulante;modulo;nome_segurado;cpf;dt_nascimento;dt_inclusao;"
    "cargo;tp_movimentacao;vl_capital;vl_salario;nr_fator_mult;cd_motivo;ds_observacao"
)
_TEMPLATE_CSV_EXEMPLO = "\n".join(
    [
        _TEMPLATE_CSV_HEADER,
        "Sub1;Vida em Grupo;JOAO DA SILVA;12345678901;15/03/1985;01/06/2026;Funcionario;INC;200000;;3.0;ADMS;Admissão em junho",
        "Sub1;Vida em Grupo;MARIA SOUZA;98765432100;22/07/1990;01/06/2026;Gerencial;INC;350000;;;ADMS;",
        "Sub2;Acidentes Pessoais;PEDRO LIMA;11122233344;10/11/1978;01/06/2026;Diretoria;INC;;8000;6.0;ADMS;Capital múltiplo salarial",
        "Sub1;Vida em Grupo;ANA COSTA;55566677788;05/04/1995;15/06/2026;Funcionario;EXC;;;; DEMI;Demissão voluntária",
        "# Tipos aceitos em tp_movimentacao: INC=Inclusão | EXC=Exclusão | CAP=Alterar Capital | SAL=Alterar Salário | SUS=Suspender | REA=Reativar",
        "# Cargo influi no fator_mult padrão: Diretoria=6x | Gerencial=5x | Coordenador=4x | Funcionario=3x | Assistente=2x",
        "# Datas aceitas: DD/MM/AAAA | AAAA-MM-DD | AAAAMMDD",
        "# vl_capital: capital fixo em R$ (ex: 200000). Se usar capital múltiplo, preencha vl_salario e nr_fator_mult",
    ]
)


@router_templates.get(
    "/movimentacao/template",
    summary="Download do template CSV de movimentação de segurados",
    tags=["Movimentação · Importação"],
    response_class=StreamingResponse,
)
def download_template_csv():
    """Retorna o template CSV para o operador preencher e enviar."""
    content = _TEMPLATE_CSV_EXEMPLO.encode(
        "utf-8-sig"
    )  # BOM para Excel abrir corretamente
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": "attachment; filename=template_movimentacao_segurados.csv"
        },
    )


@router_templates.get(
    "/movimentacao/template.xlsx",
    summary="Download do template Excel (.xlsx) de movimentação de segurados",
    tags=["Movimentação · Importação"],
    response_class=StreamingResponse,
)
def download_template_xlsx():
    """Gera e retorna um arquivo .xlsx com o template e aba de instruções."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(503, detail="openpyxl não instalado. Use o template CSV.")

    wb = openpyxl.Workbook()

    # ── Aba principal: Movimentação ───────────────────────────────────────────
    ws = wb.active
    ws.title = "Movimentacao"

    header_cols = [
        ("subestipulante", 20, "SUB1, Sub São Paulo…"),
        ("modulo", 20, "Vida em Grupo, AP…"),
        ("nome_segurado", 40, "Nome completo MAIÚSCULO"),
        ("cpf", 14, "11 dígitos sem máscara"),
        ("dt_nascimento", 14, "DD/MM/AAAA"),
        ("dt_inclusao", 14, "DD/MM/AAAA *obrigatório*"),
        ("cargo", 20, "Funcionario | Gerencial | Diretoria…"),
        ("tp_movimentacao", 16, "INC | EXC | CAP | SAL | SUS | REA"),
        ("vl_capital", 16, "Capital fixo em R$ (ex: 200000)"),
        ("vl_salario", 16, "Salário base (capital tipo M)"),
        ("nr_fator_mult", 16, "Multiplicador salarial (ex: 3.0)"),
        ("cd_motivo", 10, "ADMS | DEMI | ALTS | ALTP"),
        ("ds_observacao", 40, "Texto livre até 200 chars"),
    ]

    header_fill = PatternFill("solid", fgColor="003366")
    header_font = Font(color="FFFFFF", bold=True)
    obrig_fill = PatternFill("solid", fgColor="C6EFCE")

    for col_idx, (col_name, width, hint) in enumerate(header_cols, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[cell.column_letter].width = width
        # Linha de dica (row 2 em cinza)
        hint_cell = ws.cell(row=2, column=col_idx, value=hint)
        hint_cell.font = Font(color="595959", italic=True, size=9)

    # Exemplos
    exemplos = [
        [
            "Sub1",
            "Vida em Grupo",
            "JOAO DA SILVA",
            "12345678901",
            "15/03/1985",
            "01/06/2026",
            "Funcionario",
            "INC",
            200000,
            None,
            3.0,
            "ADMS",
            "",
        ],
        [
            "Sub1",
            "Vida em Grupo",
            "MARIA SOUZA",
            "98765432100",
            "22/07/1990",
            "01/06/2026",
            "Gerencial",
            "INC",
            350000,
            None,
            None,
            "ADMS",
            "Gerente comercial",
        ],
        [
            "Sub2",
            "Acidentes Pessoais",
            "PEDRO LIMA",
            "11122233344",
            "10/11/1978",
            "01/06/2026",
            "Diretoria",
            "INC",
            None,
            8000,
            6.0,
            "ADMS",
            "Capital múltiplo",
        ],
        [
            "Sub1",
            "Vida em Grupo",
            "ANA COSTA",
            "55566677788",
            "05/04/1995",
            "15/06/2026",
            "Funcionario",
            "EXC",
            None,
            None,
            None,
            "DEMI",
            "Demissão voluntária",
        ],
    ]
    for row_idx, ex in enumerate(exemplos, start=3):
        for col_idx, val in enumerate(ex, start=1):
            ws.cell(row=row_idx, column=col_idx, value=val)

    # Destaca colunas obrigatórias (nome, cpf, dt_inclusao)
    for obrig_col in [3, 4, 6]:
        ws.cell(row=1, column=obrig_col).fill = PatternFill("solid", fgColor="C00000")

    # ── Aba: Instruções ───────────────────────────────────────────────────────
    wi = wb.create_sheet("Instrucoes")
    instrucoes = [
        ("LIFECORE IQ — Template de Movimentação de Segurados", True),
        ("", False),
        ("COLUNAS OBRIGATÓRIAS (marcadas em vermelho na aba Movimentacao):", True),
        ("  • nome_segurado — Nome completo em maiúsculas", False),
        ("  • cpf — 11 dígitos sem pontuação (ex: 12345678901)", False),
        ("  • dt_inclusao — Data de início da cobertura (DD/MM/AAAA)", False),
        ("", False),
        ("TIPOS DE MOVIMENTAÇÃO (coluna tp_movimentacao):", True),
        ("  INC — Inclusão: novo segurado entrando na apólice", False),
        ("  EXC — Exclusão: segurado saindo (demissão, desligamento)", False),
        ("  CAP — Alteração de capital: mudança no valor de cobertura", False),
        ("  SAL — Alteração de salário: atualiza salário base (capital tipo M)", False),
        ("  SUS — Suspensão: pausa cobertura temporariamente", False),
        ("  REA — Reativação: retoma cobertura após inadimplência/suspensão", False),
        ("", False),
        (
            "CARGO → FATOR MULTIPLICADOR PADRÃO (quando capital = Múltiplo Salarial):",
            True,
        ),
        ("  Diretoria → 6×    Gerencial → 5×    Coordenador → 4×", False),
        ("  Supervisor → 4×   Funcionário → 3×  Assistente → 2×", False),
        ("  Estagiário → 1×   (informe nr_fator_mult para sobrepor)", False),
        ("", False),
        ("FORMATOS ACEITOS:", True),
        ("  Datas: DD/MM/AAAA | AAAA-MM-DD | AAAAMMDD", False),
        ("  Valores: 200000 | 200.000,00 | R$ 200.000,00", False),
        (
            "  CPF: 12345678901 | 123.456.789-01 (máscara removida automaticamente)",  # presidio: ignore
            False,
        ),
        ("", False),
        ("REGRAS DE NEGÓCIO:", True),
        (
            "  • Inadimplência ≤ 3 meses → cobertura ATIVA mantida (grace period SUSEP)",
            False,
        ),
        ("  • Inadimplência > 3 meses → SEM cobertura sem cobrança retroativa", False),
        ("  • Reativação (REA) inicia nova vigência na dt_inclusao informada", False),
    ]
    wi.column_dimensions["A"].width = 80
    for r, (texto, negrito) in enumerate(instrucoes, start=1):
        cell = wi.cell(row=r, column=1, value=texto)
        if negrito:
            cell.font = Font(bold=True, color="003366")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=template_movimentacao_segurados.xlsx"
        },
    )


# ── Importação principal ──────────────────────────────────────────────────────


@router.post(
    "/{nr_apolice}/movimentacao/importar",
    response_model=MovimentacaoImportacaoResponse,
    summary="Importa planilha de movimentação de segurados e gera endossos",
    tags=["Movimentação · Importação"],
)
async def importar_movimentacao(
    arquivo: UploadFile = File(
        ...,
        description="Planilha Excel (.xlsx) ou CSV (.csv) com a movimentação mensal",
    ),
    nr_apolice: str = FPath(..., max_length=20),
    id_usuario: str = Query("SISTEMA", description="Operador que realiza a importação"),
    cd_competencia: str | None = Query(
        None, pattern=r"^\d{6}$", description="AAAAMM — mês de referência"
    ),
    dry_run: bool = Query(False, description="True = valida sem gravar endossos"),
    verificar_receita: bool = Query(
        False,
        description="True = consulta a ReceitaWS (gratuita, ~3 req/min). "
        "False = valida somente o dígito verificador (mais rápido).",
    ),
):
    """
    Recebe a planilha mensal de movimentação de segurados.

    **Críticas executadas em cada linha:**
    - E001/E002 — CPF: dígito verificador e formato
    - E003/W039 — CPF: situação na Receita Federal (se verificar_receita=true)
    - E010–E013 — Idade: mínima (14), máxima operacional (65), implementação (70)
    - W025 — Segurado ≥ 70 anos: pende liberação manual (novo) ou alerta (existente)
    - W026 — Faixa de atenção 60–65 anos
    - E020/W021 — Duplicidade de CPF na apólice
    - E030/W031 — Nome ausente ou muito curto
    - E040–W043 — Data de inclusão ausente, inválida ou fora da janela temporal

    Severidades:
    - **BLOQ** → linha rejeitada (vai para `erros`)
    - **MANU** → endosso criado em `PENDENTE_LIBERACAO`, aparece em `sucesso` com status `CRITICA_MANU`
    - **ALRT** → endosso gerado normalmente com aviso em `criticas`
    """
    # Validação do arquivo
    ext = Path(arquivo.filename or "").suffix.lower()
    if ext not in _EXTENSOES:
        raise HTTPException(
            422, detail=f"Formato '{ext}' não suportado. Use: {', '.join(_EXTENSOES)}"
        )
    conteudo = await arquivo.read()
    if len(conteudo) > _MAX_BYTES:
        raise HTTPException(413, detail="Arquivo maior que 10 MB.")

    # Valida apólice
    apolice = _get_apolice_or_404(nr_apolice)
    if apolice["cd_status"] not in (
        StatusApoliceEnum.ATIVA,
        StatusApoliceEnum.SUSPENSA,
    ):
        raise HTTPException(
            409,
            detail=f"Apólice está {apolice['cd_status']} — importação não permitida.",
        )

    # Processa a planilha
    try:
        result: MovimentacaoResult = processar_movimentacao(
            filename=arquivo.filename,
            content=conteudo,
            nr_apolice=nr_apolice,
            id_usuario=id_usuario,
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    # Monta resposta
    itens_sucesso: list[EndossoProcessadoItem] = []
    itens_erro_extra: list[ErroImportacaoItem] = []
    taxa_mensal = _taxa_mensal_vigente()
    total_manu = 0

    for endosso_payload in result.endossos:
        linha_nr = endosso_payload.pop("_linha_planilha")
        sub = endosso_payload.pop("_subestipulante")
        modulo = endosso_payload.pop("_modulo")
        cargo = endosso_payload.pop("_cargo")
        dt_nasc = endosso_payload.pop("_dt_nascimento")

        cpf = endosso_payload["cd_cpf_segurado"]
        nome = endosso_payload["nm_segurado"]
        tp_mov = endosso_payload["tp_endosso"]
        dt_inc = endosso_payload["dt_inicio_vigencia"]
        vl_cap = endosso_payload.get("vl_capital")
        vl_sal = endosso_payload.get("vl_salario_base")
        nr_fat = endosso_payload.get("nr_fator_mult")

        nr_endosso_gerado = None
        vl_cap_calc = None
        vl_brt_calc = None
        mensagem = None

        # ── Motor de críticas ──────────────────────────────────────────────
        res_crit = executar_criticas(
            cpf=cpf,
            nome=nome,
            dt_nascimento=dt_nasc,
            dt_inclusao=dt_inc,
            tp_movimentacao=tp_mov,
            nr_apolice=nr_apolice,
            coberturas=_COBERTURAS,
            verificar_receita=verificar_receita and not dry_run,
        )

        # Converte críticas para schema de resposta
        criticas_resp: list[CriticaItem] = []
        for c in res_crit.criticas:
            id_crit_reg = None
            if c.manual and not dry_run:
                # Registra crítica MANU no store para liberação posterior
                id_crit_reg = registrar_critica_pendente(
                    nr_apolice=nr_apolice,
                    cpf=cpf,
                    nome=nome,
                    codigo=c.codigo,
                    severidade=c.severidade,
                    descricao=c.descricao,
                    orientacao=c.orientacao,
                    valor_informado=c.valor_informado,
                    fl_liberavel=c.fl_liberavel,
                )
                # Guarda payload para reprocessar após liberação
                registrar_endosso_pendente_liberacao(
                    id_crit_reg,
                    {
                        **endosso_payload,
                        "_dt_nascimento": dt_nasc,
                    },
                )
                total_manu += 1
            criticas_resp.append(
                CriticaItem(
                    codigo=c.codigo,
                    severidade=c.severidade.value,
                    descricao=c.descricao,
                    orientacao=c.orientacao,
                    valor_informado=c.valor_informado,
                    fl_liberavel=c.fl_liberavel,
                    id_critica=id_crit_reg,
                )
            )

        # Linha bloqueante → vai para erros
        if res_crit.tem_bloqueante:
            result.total_erros += 1
            result.total_sucesso -= 1
            itens_erro_extra.append(
                ErroImportacaoItem(
                    linha_planilha=linha_nr,
                    cpf=cpf,
                    nome=nome,
                    erro="; ".join(
                        f"[{c.codigo}] {c.descricao}"
                        for c in res_crit.criticas
                        if c.bloqueante
                    ),
                    criticas=criticas_resp,
                )
            )
            continue

        # Linha com MANU pendente → pende liberação (não processa agora)
        if res_crit.tem_manual_pendente and not dry_run:
            itens_sucesso.append(
                EndossoProcessadoItem(
                    linha_planilha=linha_nr,
                    cpf=cpf,
                    nome=nome,
                    subestipulante=sub,
                    modulo=modulo,
                    cargo=cargo,
                    tp_movimentacao=tp_mov,
                    dt_inclusao=dt_inc,
                    dt_nascimento=dt_nasc,
                    nr_endosso=None,
                    vl_capital=vl_cap,
                    vl_premio_bruto=None,
                    status="CRITICA_MANU",
                    mensagem="Aguardando liberação manual. Acesse /movimentacao/criticas.",
                    criticas=criticas_resp,
                )
            )
            continue

        if dry_run:
            # Apenas calcula — não grava
            if tp_mov in ("INC", "CAP", "REA") and (vl_cap or vl_sal):
                vl_cap_calc = _calcular_capital(
                    apolice,
                    vl_capital=vl_cap,
                    vl_salario=vl_sal,
                    fator=nr_fat,
                )
                cap_ajust = round(vl_cap_calc * (1 + taxa_mensal / 100), 2)
                vl_brt_calc, _ = _calcular_premio(cap_ajust)
            mensagem = "dry_run — endosso validado, não gravado."
        else:
            # Grava o endosso e atualiza cobertura
            chave_cob = f"{nr_apolice}:{cpf}"
            nr_endosso_gerado = _gerar_nr_endosso()

            try:
                if tp_mov == "INC":
                    if chave_cob in _COBERTURAS:
                        mensagem = (
                            "AVISO: segurado já possui cobertura — endosso ignorado."
                        )
                        itens_sucesso.append(
                            EndossoProcessadoItem(
                                linha_planilha=linha_nr,
                                cpf=cpf,
                                nome=nome,
                                subestipulante=sub,
                                modulo=modulo,
                                cargo=cargo,
                                tp_movimentacao=tp_mov,
                                dt_inclusao=dt_inc,
                                dt_nascimento=dt_nasc,
                                nr_endosso=None,
                                vl_capital=vl_cap,
                                vl_premio_bruto=None,
                                status="AVISO",
                                mensagem=mensagem,
                            )
                        )
                        continue

                    vl_cap_calc = _calcular_capital(
                        apolice,
                        vl_capital=vl_cap,
                        vl_salario=vl_sal,
                        fator=nr_fat,
                    )
                    cap_ajust = round(vl_cap_calc * (1 + taxa_mensal / 100), 2)
                    vl_brt_calc, vl_liq = _calcular_premio(cap_ajust)

                    # Constrói observação enriquecida
                    obs_completa = endosso_payload.get("ds_observacao") or ""
                    if cd_competencia:
                        obs_completa = (
                            f"Competência: {cd_competencia} | {obs_completa}".strip(
                                " |"
                            )
                        )

                    _COBERTURAS[chave_cob] = {
                        "cd_cpf_segurado": cpf,
                        "nm_segurado": nome,
                        "nr_apolice": nr_apolice,
                        "dt_nascimento": dt_nasc,
                        "dt_admissao": dt_inc,
                        "dt_inicio_cobertura": dt_inc,
                        "dt_ultimo_pagamento": None,
                        "nr_meses_inadimplente": 0,
                        "cd_status_cobertura": StatusCoberturaEnum.ATIVA,
                        "fl_em_carencia": False,
                        "nr_dias_carencia": 0,
                        "vl_capital_base": vl_cap_calc,
                        "vl_capital_atual": vl_cap_calc,
                        "vl_reajuste_ipca": 0.0,
                        "vl_salario_base": vl_sal,
                        "nr_fator_mult": nr_fat,
                        "vl_premio_bruto": vl_brt_calc,
                        "vl_premio_liquido": vl_liq,
                        "vl_taxa_premio": 2.5,
                        "fl_revalidado": False,
                        "dt_revalidacao": None,
                        "cargo": cargo,
                        "subestipulante": sub,
                        "modulo": modulo,
                        "ds_status_detalhado": obs_completa or "Incluído via planilha.",
                    }

                elif tp_mov == "EXC":
                    if chave_cob in _COBERTURAS:
                        _COBERTURAS[chave_cob]["cd_status_cobertura"] = (
                            StatusCoberturaEnum.CANCELADA
                        )
                        _COBERTURAS[chave_cob]["ds_status_detalhado"] = (
                            f"Excluído via planilha — endosso {nr_endosso_gerado}."
                        )

                elif tp_mov == "SUS":
                    if chave_cob in _COBERTURAS:
                        _COBERTURAS[chave_cob]["cd_status_cobertura"] = (
                            StatusCoberturaEnum.SUSPENSA
                        )

                elif tp_mov == "REA":
                    if chave_cob in _COBERTURAS:
                        cob = _COBERTURAS[chave_cob]
                        cob["cd_status_cobertura"] = StatusCoberturaEnum.ATIVA
                        cob["nr_meses_inadimplente"] = 0
                        cob["fl_revalidado"] = True
                        cob["dt_revalidacao"] = dt_inc
                        cob["dt_inicio_cobertura"] = dt_inc

                elif tp_mov in ("CAP", "SAL"):
                    if chave_cob in _COBERTURAS:
                        cob = _COBERTURAS[chave_cob]
                        if vl_cap:
                            new_cap = _calcular_capital(
                                apolice,
                                vl_capital=vl_cap,
                                vl_salario=vl_sal,
                                fator=nr_fat,
                            )
                            cap_ajust = round(new_cap * (1 + taxa_mensal / 100), 2)
                            vl_brt_calc, vl_liq = _calcular_premio(cap_ajust)
                            cob["vl_capital_atual"] = new_cap
                            cob["vl_premio_bruto"] = vl_brt_calc
                            cob["vl_premio_liquido"] = vl_liq
                            vl_cap_calc = new_cap
                        if vl_sal:
                            cob["vl_salario_base"] = vl_sal
                        if nr_fat:
                            cob["nr_fator_mult"] = nr_fat

                # Grava endosso no store
                _ENDOSSOS[nr_endosso_gerado] = {
                    **endosso_payload,
                    "nr_endosso": nr_endosso_gerado,
                    "nr_apolice": nr_apolice,
                    "cd_status": StatusEndossoEnum.PROCESSADO,
                    "vl_capital_calculado": vl_cap_calc,
                    "vl_premio_calculado": vl_brt_calc,
                    "ts_inclusao": _now(),
                }
                mensagem = "Endosso processado com sucesso."

            except Exception as exc:
                mensagem = f"Erro ao processar: {exc}"
                result.total_erros += 1
                result.total_sucesso -= 1
                result.erros.append(
                    {"linha": linha_nr, "cpf": cpf, "nome": nome, "erro": mensagem}
                )
                itens_sucesso.append(
                    EndossoProcessadoItem(
                        linha_planilha=linha_nr,
                        cpf=cpf,
                        nome=nome,
                        subestipulante=sub,
                        modulo=modulo,
                        cargo=cargo,
                        tp_movimentacao=tp_mov,
                        dt_inclusao=dt_inc,
                        dt_nascimento=dt_nasc,
                        nr_endosso=None,
                        vl_capital=vl_cap,
                        vl_premio_bruto=None,
                        status="ERRO",
                        mensagem=mensagem,
                    )
                )
                continue

        # Alertas (ALRT) — processa normalmente, inclui na lista de críticas
        status_final = "DRY_RUN" if dry_run else "OK"
        msg_final = mensagem
        if criticas_resp:
            alertas = [c for c in criticas_resp if c.severidade == "ALRT"]
            if alertas and not dry_run:
                status_final = "AVISO"
                msg_final = f"{len(alertas)} alerta(s). Verifique a coluna 'criticas'."

        itens_sucesso.append(
            EndossoProcessadoItem(
                linha_planilha=linha_nr,
                cpf=cpf,
                nome=nome,
                subestipulante=sub,
                modulo=modulo,
                cargo=cargo,
                tp_movimentacao=tp_mov,
                dt_inclusao=dt_inc,
                dt_nascimento=dt_nasc,
                nr_endosso=nr_endosso_gerado,
                vl_capital=vl_cap_calc or vl_cap,
                vl_premio_bruto=vl_brt_calc,
                status=status_final,
                mensagem=msg_final,
                criticas=criticas_resp,
            )
        )

    # Combina erros do parser de planilha + erros de críticas bloqueantes
    todos_erros = [
        ErroImportacaoItem(
            linha_planilha=e["linha"],
            cpf=e["cpf"],
            nome=e["nome"],
            erro=e["erro"],
        )
        for e in result.erros
    ] + itens_erro_extra

    return MovimentacaoImportacaoResponse(
        nr_apolice=nr_apolice,
        cd_competencia=cd_competencia,
        dry_run=dry_run,
        total_linhas=result.total_linhas,
        total_sucesso=result.total_sucesso,
        total_erros=len(todos_erros),
        total_pendente_manu=total_manu,
        sumario_sub=result.sumario_sub,
        sucesso=itens_sucesso,
        erros=todos_erros,
        ts_processamento=_now(),
    )
