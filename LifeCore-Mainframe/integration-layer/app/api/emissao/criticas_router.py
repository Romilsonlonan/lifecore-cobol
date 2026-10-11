"""
Críticas de Importação — Endpoints de consulta e liberação manual

GET  /api/emissao/apolices/{nr_apolice}/movimentacao/criticas
     Lista todas as críticas pendentes de liberação manual (W025, etc.)
     geradas na última importação ou ao longo do tempo.

GET  /api/emissao/criticas/catalogo
     Retorna o catálogo completo de códigos de crítica (documentação).

POST /api/emissao/apolices/{nr_apolice}/movimentacao/criticas/{id_critica}/liberar
     Operador libera uma crítica MANU → endosso é reprocessado.

POST /api/emissao/apolices/{nr_apolice}/movimentacao/criticas/{id_critica}/bloquear
     Operador bloqueia definitivamente → linha é rejeitada.

POST /api/emissao/criticas/cpf/validar
     Valida um CPF isolado (formato + Receita Federal) antes da importação.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.services.criticas_segurado import (
    CATALOGO,
    IDADE_IMPLEMENTACAO,
    IDADE_MAXIMA_OPERAT,
    IDADE_MINIMA,
    SeveridadeCritica,
    StatusLiberacao,
    _consultar_receita_federal,
    _validar_cpf_algoritmo,
)

router = APIRouter()  # montado em /api/emissao/apolices — rotas com {nr_apolice}
router_util = APIRouter()  # montado em /api/emissao — catálogo e validação de CPF

# ── Store in-memory de críticas pendentes (fallback) ─────────────────────────
_CRITICAS_PENDENTES: dict[str, dict] = {}


def _sb_ok(table: str = "criticas_pendentes") -> bool:
    try:
        from app.repositories.supabase_repo import sb_available
        return sb_available(table)
    except Exception:
        return False


def _get_critica(id_critica: str) -> dict | None:
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            return sr.get_one("criticas_pendentes", {"id_critica": id_critica})
    except Exception:
        pass
    return _CRITICAS_PENDENTES.get(id_critica)


def _save_critica(c: dict) -> None:
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            sr.upsert("criticas_pendentes", {k: v for k, v in c.items()
                      if k not in ("ts_critica", "ts_resolucao")})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Supabase save_critica falhou: %s", exc)
    _CRITICAS_PENDENTES[c["id_critica"]] = c


# ── Schemas ───────────────────────────────────────────────────────────────────


class CriticaDetalhe(BaseModel):
    id_critica: str
    nr_apolice: str
    cpf: str
    nome: str
    codigo: str
    severidade: str
    descricao: str
    orientacao: str
    valor_informado: str | None
    fl_liberavel: bool
    fl_liberado: bool
    status_liberacao: str
    id_usuario_lib: str | None
    dt_liberacao: str | None
    ts_critica: datetime


class LiberacaoRequest(BaseModel):
    id_usuario: str = Field(..., max_length=20)
    ds_justificativa: str = Field(
        ..., max_length=300, description="Justificativa obrigatória para a decisão"
    )


class LiberacaoResponse(BaseModel):
    id_critica: str
    nr_apolice: str
    cpf: str
    nome: str
    codigo: str
    decisao: str  # LIBERADO ou BLOQUEADO
    id_usuario: str
    ds_justificativa: str
    ts_decisao: datetime


class ValidacaoCPFRequest(BaseModel):
    cpf: str = Field(..., description="CPF a validar (com ou sem máscara)")
    nm_segurado: str | None = Field(
        None, description="Nome para verificação na Receita"
    )
    verificar_receita: bool = Field(
        True, description="False = apenas valida dígito verificador"
    )


class ValidacaoCPFResponse(BaseModel):
    cpf: str
    cpf_formatado: str
    fl_valido: bool
    situacao_receita: str | None
    criticas: list[dict]
    mensagem: str


class CatalogoCriticaItem(BaseModel):
    codigo: str
    severidade: str
    descricao: str
    orientacao: str


class ParametrosIdadeResponse(BaseModel):
    idade_minima: int
    idade_maxima_operat: int
    idade_implementacao: int
    descricao: str


# ── Helper ────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def registrar_critica_pendente(
    nr_apolice: str,
    cpf: str,
    nome: str,
    codigo: str,
    severidade: SeveridadeCritica,
    descricao: str,
    orientacao: str,
    valor_informado: str | None,
    fl_liberavel: bool,
    payload_linha: dict | None = None,
) -> str:
    """Persiste uma crítica MANU no Supabase (fallback in-memory) e retorna o id_critica."""
    id_critica = str(uuid.uuid4())
    critica = {
        "id_critica": id_critica,
        "nr_apolice": nr_apolice,
        "cpf": cpf,
        "nome": nome,
        "codigo": codigo,
        "severidade": severidade.value,
        "descricao": descricao,
        "orientacao": orientacao,
        "valor_informado": valor_informado,
        "fl_liberavel": fl_liberavel,
        "fl_liberado": False,
        "status_liberacao": StatusLiberacao.PENDENTE.value,
        "payload_linha": payload_linha or {},
        "id_operador": None,
        "ds_justificativa": None,
        "cd_status": StatusLiberacao.PENDENTE.value,
        "id_usuario_lib": None,
        "dt_liberacao": None,
        "ts_critica": _now(),
    }
    _save_critica(critica)
    return id_critica


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router_util.get(
    "/criticas/catalogo",
    response_model=list[CatalogoCriticaItem],
    summary="Catálogo completo de códigos de crítica",
    tags=["Críticas · Catálogo"],
)
def catalogo_criticas():
    """Retorna todos os códigos de crítica com descrição e orientação de resolução."""
    return [
        CatalogoCriticaItem(
            codigo=c.codigo,
            severidade=c.severidade.value,
            descricao=c.descricao,
            orientacao=c.orientacao,
        )
        for c in CATALOGO.values()
    ]


@router_util.get(
    "/criticas/parametros-idade",
    response_model=ParametrosIdadeResponse,
    summary="Parâmetros de faixa etária do produto",
    tags=["Críticas · Catálogo"],
)
def parametros_idade():
    return ParametrosIdadeResponse(
        idade_minima=IDADE_MINIMA,
        idade_maxima_operat=IDADE_MAXIMA_OPERAT,
        idade_implementacao=IDADE_IMPLEMENTACAO,
        descricao=(
            f"Mínimo: {IDADE_MINIMA} anos (E012). "
            f"Máximo operacional: {IDADE_MAXIMA_OPERAT} anos (E013). "
            f"Implementação: {IDADE_IMPLEMENTACAO} anos (W025 — requer liberação manual). "
            "Faixa de atenção: 60–65 anos (W026 — alerta)."
        ),
    )


@router_util.post(
    "/criticas/cpf/validar",
    response_model=ValidacaoCPFResponse,
    summary="Valida um CPF antes da importação (formato + Receita Federal)",
    tags=["Críticas · Validação CPF"],
)
def validar_cpf(payload: ValidacaoCPFRequest):
    """
    Valida um CPF de forma isolada:
    1. Remove máscara
    2. Verifica dígitos verificadores (Receita Federal — algoritmo)
    3. Opcionalmente consulta situação cadastral na ReceitaWS

    Útil para o corretor verificar um CPF antes de montar a planilha.
    """
    cpf_limpo = re.sub(r"\D", "", payload.cpf or "")

    if len(cpf_limpo) != 11:
        return ValidacaoCPFResponse(
            cpf=payload.cpf,
            cpf_formatado=cpf_limpo,
            fl_valido=False,
            situacao_receita=None,
            criticas=[
                {
                    "codigo": "E002",
                    "severidade": "BLOQ",
                    "descricao": f"CPF deve ter 11 dígitos (encontrado: {len(cpf_limpo)}).",
                    "orientacao": "Informe 11 dígitos numéricos sem pontuação.",
                }
            ],
            mensagem="CPF inválido — formato incorreto.",
        )

    if len(set(cpf_limpo)) == 1:
        return ValidacaoCPFResponse(
            cpf=payload.cpf,
            cpf_formatado=cpf_limpo,
            fl_valido=False,
            situacao_receita=None,
            criticas=[
                {
                    "codigo": "E002",
                    "severidade": "BLOQ",
                    "descricao": "CPF com todos os dígitos iguais é inválido.",
                    "orientacao": "Informe o CPF correto do segurado.",
                }
            ],
            mensagem="CPF inválido — dígitos iguais.",
        )

    if not _validar_cpf_algoritmo(cpf_limpo):
        return ValidacaoCPFResponse(
            cpf=payload.cpf,
            cpf_formatado=f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}",
            fl_valido=False,
            situacao_receita=None,
            criticas=[
                {
                    "codigo": "E001",
                    "severidade": "BLOQ",
                    "descricao": "Dígito verificador inválido (algoritmo Receita Federal).",
                    "orientacao": "Corrija o CPF — um ou mais dígitos estão errados.",
                }
            ],
            mensagem="CPF inválido — dígito verificador incorreto.",
        )

    cpf_fmt = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
    criticas_list = []
    situacao = None

    if payload.verificar_receita:
        criticas_rf = _consultar_receita_federal(cpf_limpo, payload.nm_segurado or "")
        criticas_list = [c.to_dict() for c in criticas_rf]
        # Extrai situação do cache
        from app.services.criticas_segurado import _RECEITAWS_CACHE

        dados = _RECEITAWS_CACHE.get(cpf_limpo, {})
        situacao = dados.get("situacao") or dados.get("status") or "Não consultado"

    fl_valido = not any(c["severidade"] == "BLOQ" for c in criticas_list)

    if not criticas_list:
        mensagem = "CPF válido — dígito verificador correto. Situação Receita: Regular."
    elif fl_valido:
        mensagem = "CPF válido estruturalmente, mas com alertas. Verifique os detalhes."
    else:
        mensagem = (
            "CPF com restrição na Receita Federal. Verifique a situação cadastral."
        )

    return ValidacaoCPFResponse(
        cpf=payload.cpf,
        cpf_formatado=cpf_fmt,
        fl_valido=fl_valido,
        situacao_receita=situacao,
        criticas=criticas_list,
        mensagem=mensagem,
    )


@router.get(
    "/{nr_apolice}/movimentacao/criticas",
    response_model=list[CriticaDetalhe],
    summary="Lista críticas pendentes de liberação manual",
    tags=["Críticas · Liberação Manual"],
)
def listar_criticas(
    nr_apolice: str = Path(..., max_length=20),
    status_liberacao: str | None = Query(
        None, description="PENDENTE | LIBERADO | BLOQUEADO"
    ),
    codigo: str | None = Query(None, description="Filtrar por código ex: W025"),
):
    """Lista todas as críticas registradas para uma apólice, com filtro opcional por status e código."""
    try:
        if _sb_ok():
            from app.repositories import supabase_repo as sr
            filters: dict = {"nr_apolice": nr_apolice}
            if status_liberacao:
                filters["cd_status"] = status_liberacao.upper()
            rows = sr.get_all("criticas_pendentes", filters=filters, order="ts_criacao", desc=True)
            if codigo:
                rows = [r for r in rows if r["codigo"] == codigo.upper()]
            return rows
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Supabase listar_criticas falhou: %s", exc)
    result = [c for c in _CRITICAS_PENDENTES.values() if c["nr_apolice"] == nr_apolice]
    if status_liberacao:
        result = [c for c in result if c["status_liberacao"] == status_liberacao.upper()]
    if codigo:
        result = [c for c in result if c["codigo"] == codigo.upper()]
    return sorted(result, key=lambda c: c["ts_critica"], reverse=True)


@router.post(
    "/{nr_apolice}/movimentacao/criticas/{id_critica}/liberar",
    response_model=LiberacaoResponse,
    summary="Libera uma crítica manual (W025 etc.) — permite processamento do endosso",
    tags=["Críticas · Liberação Manual"],
)
def liberar_critica(
    payload: LiberacaoRequest,
    nr_apolice: str = Path(..., max_length=20),
    id_critica: str = Path(...),
):
    """
    O operador (analista) revisa a crítica W025 (ou outra MANU)
    e decide liberar o segurado para inclusão.

    Após liberação, o endosso que estava em PENDENTE_LIBERACAO
    é reprocessado automaticamente e a cobertura entra como ATIVA.
    """
    c = _get_critica(id_critica)
    if not c or c["nr_apolice"] != nr_apolice:
        raise HTTPException(404, detail=f"Crítica {id_critica} não encontrada.")
    if not c["fl_liberavel"]:
        raise HTTPException(409, detail="Esta crítica não é liberável (severidade BLOQ).")
    if c.get("status_liberacao", c.get("cd_status")) != StatusLiberacao.PENDENTE.value:
        raise HTTPException(409, detail=f"Crítica já processada: status={c.get('status_liberacao')}.")

    upd = {
        "fl_liberado": True,
        "status_liberacao": StatusLiberacao.LIBERADO.value,
        "cd_status": StatusLiberacao.LIBERADO.value,
        "id_usuario_lib": payload.id_usuario,
        "id_operador": payload.id_usuario,
        "ds_justificativa": payload.ds_justificativa,
        "dt_liberacao": datetime.now(UTC).strftime("%Y%m%d"),
        "ts_resolucao": datetime.now(UTC).isoformat(),
    }
    c.update(upd)
    _save_critica(c)
    _reprocessar_endosso_pendente(id_critica, nr_apolice, c["cpf"], payload.id_usuario)

    return LiberacaoResponse(
        id_critica=id_critica,
        nr_apolice=nr_apolice,
        cpf=c["cpf"],
        nome=c["nome"],
        codigo=c["codigo"],
        decisao="LIBERADO",
        id_usuario=payload.id_usuario,
        ds_justificativa=payload.ds_justificativa,
        ts_decisao=_now(),
    )


@router.post(
    "/{nr_apolice}/movimentacao/criticas/{id_critica}/bloquear",
    response_model=LiberacaoResponse,
    summary="Bloqueia definitivamente um segurado com crítica manual",
    tags=["Críticas · Liberação Manual"],
)
def bloquear_critica(
    payload: LiberacaoRequest,
    nr_apolice: str = Path(..., max_length=20),
    id_critica: str = Path(...),
):
    """
    O operador decide bloquear o segurado — a linha é rejeitada definitivamente.
    O endosso em PENDENTE_LIBERACAO é cancelado.
    """
    c = _get_critica(id_critica)
    if not c or c["nr_apolice"] != nr_apolice:
        raise HTTPException(404, detail=f"Crítica {id_critica} não encontrada.")
    if c.get("status_liberacao", c.get("cd_status")) != StatusLiberacao.PENDENTE.value:
        raise HTTPException(409, detail=f"Crítica já processada: status={c.get('status_liberacao')}.")

    upd = {
        "fl_liberado": False,
        "status_liberacao": StatusLiberacao.BLOQUEADO.value,
        "cd_status": StatusLiberacao.BLOQUEADO.value,
        "id_usuario_lib": payload.id_usuario,
        "id_operador": payload.id_usuario,
        "ds_justificativa": payload.ds_justificativa,
        "dt_liberacao": datetime.now(UTC).strftime("%Y%m%d"),
        "ts_resolucao": datetime.now(UTC).isoformat(),
    }
    c.update(upd)
    _save_critica(c)

    return LiberacaoResponse(
        id_critica=id_critica,
        nr_apolice=nr_apolice,
        cpf=c["cpf"],
        nome=c["nome"],
        codigo=c["codigo"],
        decisao="BLOQUEADO",
        id_usuario=payload.id_usuario,
        ds_justificativa=payload.ds_justificativa,
        ts_decisao=_now(),
    )


# ── Reprocessamento de endosso após liberação ─────────────────────────────────

_ENDOSSOS_PENDENTES_LIBERACAO: dict[str, dict] = {}
# key: id_critica → payload completo do endosso aguardando decisão


def registrar_endosso_pendente_liberacao(id_critica: str, endosso_payload: dict):
    """Guarda o endosso para reprocessar após a liberação manual."""
    _ENDOSSOS_PENDENTES_LIBERACAO[id_critica] = endosso_payload


def _reprocessar_endosso_pendente(
    id_critica: str,
    nr_apolice: str,
    cpf: str,
    id_usuario: str,
):
    """
    Após liberação manual, executa o endosso que estava suspenso.
    Importa os stores de faturamento dinamicamente para evitar circular import.
    """
    payload = _ENDOSSOS_PENDENTES_LIBERACAO.pop(id_critica, None)
    if not payload:
        return  # endosso já foi processado ou não encontrado

    try:
        from app.api.emissao.faturamento import (
            _APOLICES,
            _COBERTURAS,
            _ENDOSSOS,
            _calcular_capital,
            _calcular_premio,
            _gerar_nr_endosso,
            _taxa_mensal_vigente,
        )
        from app.api.emissao.faturamento import (
            _now as fat_now,
        )
        from app.schemas.lifecore import StatusCoberturaEnum, StatusEndossoEnum

        apolice = _APOLICES.get(nr_apolice)
        if not apolice:
            return

        taxa = _taxa_mensal_vigente()
        vl_cap = _calcular_capital(
            apolice,
            vl_capital=payload.get("vl_capital"),
            vl_salario=payload.get("vl_salario_base"),
            fator=payload.get("nr_fator_mult"),
        )
        cap_ajust = round(vl_cap * (1 + taxa / 100), 2)
        vl_brt, vl_liq = _calcular_premio(cap_ajust)
        chave = f"{nr_apolice}:{cpf}"

        _COBERTURAS[chave] = {
            "cd_cpf_segurado": cpf,
            "nm_segurado": payload.get("nm_segurado", ""),
            "nr_apolice": nr_apolice,
            "dt_nascimento": payload.get("_dt_nascimento"),
            "dt_admissao": payload.get("dt_inicio_vigencia"),
            "dt_inicio_cobertura": payload.get("dt_inicio_vigencia"),
            "dt_ultimo_pagamento": None,
            "nr_meses_inadimplente": 0,
            "cd_status_cobertura": StatusCoberturaEnum.ATIVA,
            "fl_em_carencia": False,
            "nr_dias_carencia": 0,
            "vl_capital_base": vl_cap,
            "vl_capital_atual": vl_cap,
            "vl_reajuste_ipca": 0.0,
            "vl_salario_base": payload.get("vl_salario_base"),
            "nr_fator_mult": payload.get("nr_fator_mult"),
            "vl_premio_bruto": vl_brt,
            "vl_premio_liquido": vl_liq,
            "vl_taxa_premio": 2.5,
            "fl_revalidado": False,
            "dt_revalidacao": None,
            "ds_status_detalhado": f"Liberado manualmente — crítica {id_critica}.",
        }

        nr_end = _gerar_nr_endosso()
        _ENDOSSOS[nr_end] = {
            **payload,
            "nr_endosso": nr_end,
            "nr_apolice": nr_apolice,
            "cd_status": StatusEndossoEnum.PROCESSADO,
            "vl_capital_calculado": vl_cap,
            "vl_premio_calculado": vl_brt,
            "ts_inclusao": fat_now(),
            "ds_observacao": f"Liberado via análise manual — crítica {id_critica}",
        }
    except Exception:
        pass  # falha silenciosa — o analista pode reenviar manualmente
