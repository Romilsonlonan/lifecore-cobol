"""
Configuração de Apólice — Router
Gerencia todas as configurações operacionais de uma apólice:
faturamento, subestipulantes, contatos, endereço, renovação,
transferência de CNPJ, cancelamento e histórico de alterações.

Prefixo: /api/emissao/apolices/{nr_apolice}/config
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# Tipo anotado: nr_apolice lido do path param do router pai

router = APIRouter()

# ── Stores em memória ─────────────────────────────────────────────────────────
# Chave: nr_apolice

_CONFIG: dict[str, dict] = {}  # configurações de faturamento
_SUBESTIPULANTES: dict[str, list] = {}  # subestipulantes por apólice
_CONTATOS: dict[str, list] = {}  # contatos por apólice
_HISTORICO: dict[str, list] = {}  # log de alterações

_NEXT_SUBESTIP = 1
_NEXT_CONTATO = 1


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

# ── Faturamento ───────────────────────────────────────────────────────────────


class ConfigFaturamentoRequest(BaseModel):
    # Competência e datas
    dia_vencimento: int = Field(
        ..., ge=1, le=31, description="Dia do mês para vencimento da fatura"
    )
    dia_corte: int = Field(
        ..., ge=1, le=31, description="Dia de corte para inclusão de vidas no mês"
    )
    mes_competencia_ini: str = Field(
        ..., pattern=r"^\d{6}$", description="Competência inicial AAAAMM"
    )
    periodicidade: str = Field(
        ...,
        pattern=r"^(MN|BM|TR|SM|AN)$",
        description="MN=Mensal BM=Bimestral TR=Trimestral SM=Semestral AN=Anual",
    )

    # Repetição de faturamento
    fl_repetir_sem_movimento: str = Field(
        "N",
        pattern=r"^[SN]$",
        description="S=repete fatura anterior quando não há movimentação de vidas",
    )
    ds_obs_repeticao: str | None = Field(
        None, max_length=200, description="Observação sobre a regra de repetição"
    )

    # Forma de cobrança
    forma_cobranca: str = Field(
        ...,
        pattern=r"^(BO|CC|DB|PI)$",
        description="BO=Boleto CC=Cartão DB=Débito PI=PIX",
    )
    fl_nf_eletronica: str = Field(
        "S", pattern=r"^[SN]$", description="Emite NF-e automaticamente ao faturar"
    )

    # E-mail de fatura
    cd_email_fatura: str | None = Field(
        None,
        max_length=120,
        description="E-mail que recebe a fatura (padrão: contato da apólice)",
    )
    cd_email_copia: str | None = Field(
        None, max_length=120, description="CC para cópia da fatura"
    )

    # Observações gerais
    ds_observacao: str | None = Field(None, max_length=300)


class ConfigFaturamentoResponse(ConfigFaturamentoRequest):
    nr_apolice: str
    dt_proximo_vencimento: str | None = None
    dt_ultima_atualizacao: str | None = None
    id_usuario_atualizacao: str | None = None
    model_config = {"from_attributes": True}


# ── Mudança de vencimento ──────────────────────────────────────────────────────


class MudancaVencimentoRequest(BaseModel):
    dia_vencimento_novo: int = Field(..., ge=1, le=31)
    dt_vigencia: str = Field(
        ..., pattern=r"^\d{8}$", description="A partir de qual competência (AAAAMMDD)"
    )
    ds_motivo: str = Field(..., max_length=200)
    id_usuario: str = Field(..., max_length=20)


# ── Subestipulante ─────────────────────────────────────────────────────────────


class SubestipulanteCreate(BaseModel):
    cd_cnpj: str = Field(..., min_length=14, max_length=14)
    nm_razao_social: str = Field(..., max_length=80)
    nm_nome_reduzido: str | None = Field(None, max_length=30)
    cd_email: str | None = Field(None, max_length=120)
    nr_telefone: str | None = Field(None, max_length=20)
    nm_responsavel: str | None = Field(
        None, max_length=80, description="Nome do responsável de RH"
    )
    cd_email_responsavel: str | None = Field(None, max_length=120)
    dt_inclusao_apolice: str = Field(
        ..., pattern=r"^\d{8}$", description="Data de inclusão na apólice"
    )
    ds_observacao: str | None = Field(None, max_length=200)
    id_usuario: str = Field(..., max_length=20)


class SubestipulanteResponse(SubestipulanteCreate):
    cd_subestipulante: int
    nr_apolice: str
    cd_status: str  # AT=Ativo CA=Cancelado SU=Suspenso
    dt_cancelamento: str | None = None
    ds_motivo_cancel: str | None = None
    model_config = {"from_attributes": True}


class AlterarSubestipulanteRequest(BaseModel):
    cd_motivo: str = Field(
        ..., max_length=4, description="Código do motivo (ex: R001=desligamento)"
    )
    ds_motivo: str = Field(..., max_length=200)
    dt_vigencia: str = Field(
        ..., pattern=r"^\d{8}$", description="Data de vigência da alteração"
    )
    id_usuario: str = Field(..., max_length=20)


# ── Contatos e Endereço ───────────────────────────────────────────────────────


class ContatoCreate(BaseModel):
    tp_contato: str = Field(
        ...,
        pattern=r"^(RH|FIN|DIR|TEC|OUT)$",
        description="RH=Recursos Humanos FIN=Financeiro DIR=Diretoria TEC=TI OUT=Outro",
    )
    nm_contato: str = Field(..., max_length=80)
    cd_cargo: str | None = Field(None, max_length=60)
    cd_email: str = Field(..., max_length=120)
    cd_email_copia: str | None = Field(None, max_length=120)
    nr_telefone: str | None = Field(None, max_length=20)
    nr_celular: str | None = Field(None, max_length=20)
    fl_recebe_fatura: str = Field("N", pattern=r"^[SN]$")
    fl_recebe_apolice: str = Field("N", pattern=r"^[SN]$")
    fl_recebe_certificado: str = Field("N", pattern=r"^[SN]$")
    ds_observacao: str | None = Field(None, max_length=200)


class ContatoResponse(ContatoCreate):
    cd_contato: int
    nr_apolice: str
    cd_status: str
    model_config = {"from_attributes": True}


class EnderecoRequest(BaseModel):
    ds_logradouro: str = Field(..., max_length=100)
    nr_numero: str = Field(..., max_length=10)
    ds_complemento: str | None = Field(None, max_length=50)
    nm_bairro: str = Field(..., max_length=60)
    nm_cidade: str = Field(..., max_length=60)
    sg_estado: str = Field(..., min_length=2, max_length=2)
    cd_cep: str = Field(..., min_length=8, max_length=8)
    id_usuario: str = Field(..., max_length=20)


# ── Operações especiais ───────────────────────────────────────────────────────


class RenovacaoRequest(BaseModel):
    dt_inicio_nova_vigencia: str = Field(..., pattern=r"^\d{8}$")
    dt_fim_nova_vigencia: str = Field(..., pattern=r"^\d{8}$")
    fl_manter_config: str = Field(
        "S",
        pattern=r"^[SN]$",
        description="S=copia toda a configuração atual para a renovação",
    )
    ds_observacao: str | None = Field(None, max_length=200)
    id_usuario: str = Field(..., max_length=20)


class AlteracaoProdutoRequest(BaseModel):
    cd_produto_novo: str = Field(..., pattern=r"^(VGC|GLB)$")
    dt_vigencia: str = Field(..., pattern=r"^\d{8}$")
    ds_motivo: str = Field(..., max_length=200)
    id_usuario: str = Field(..., max_length=20)


class TransferenciaCnpjRequest(BaseModel):
    cd_cnpj_novo: str = Field(..., min_length=14, max_length=14)
    nm_razao_social_novo: str = Field(..., max_length=80)
    dt_vigencia: str = Field(..., pattern=r"^\d{8}$")
    ds_motivo: str = Field(..., max_length=200)
    id_usuario: str = Field(..., max_length=20)


class CancelamentoRequest(BaseModel):
    cd_motivo: str = Field(
        ..., max_length=4, description="Código do motivo de cancelamento"
    )
    ds_motivo: str = Field(..., max_length=300)
    dt_cancelamento: str = Field(..., pattern=r"^\d{8}$")
    fl_devolver_premio: str = Field(
        "N", pattern=r"^[SN]$", description="S=gerar crédito do prêmio proporcional"
    )
    id_usuario: str = Field(..., max_length=20)


class CancelamentoTransferenciaRequest(BaseModel):
    """Cancela apólice principal transferindo responsabilidade a um subestipulante."""

    cd_subestipulante_sucessor: int = Field(
        ..., description="ID do subestipulante que assume como apólice principal"
    )
    cd_motivo: str = Field(..., max_length=4)
    ds_motivo: str = Field(..., max_length=300)
    dt_cancelamento: str = Field(..., pattern=r"^\d{8}$")
    fl_devolver_premio: str = Field("N", pattern=r"^[SN]$")
    id_usuario: str = Field(..., max_length=20)


class SuspensaoTemporariaRequest(BaseModel):
    """Suspende temporariamente a apólice e todos os subestipulantes sem gerar cobrança."""

    tp_origem: str = Field(
        ...,
        pattern=r"^(CLIENTE|JUDICIAL)$",
        description="CLIENTE=a pedido do cliente · JUDICIAL=ordem judicial (prêmio pago pela empresa)",
    )
    ds_motivo: str = Field(..., max_length=300)
    dt_inicio_suspensao: str = Field(..., pattern=r"^\d{8}$")
    dt_prev_reativacao: str | None = Field(
        None,
        pattern=r"^\d{8}$",
        description="Data prevista para reativação (obrigatória para JUDICIAL)",
    )
    nr_processo_judicial: str | None = Field(
        None, max_length=30, description="Número do processo (apenas para JUDICIAL)"
    )
    nm_orgao_judicial: str | None = Field(
        None, max_length=80, description="Órgão/vara responsável (apenas para JUDICIAL)"
    )
    id_usuario: str = Field(..., max_length=20)


class ReativacaoSuspensaoRequest(BaseModel):
    """Reativa apólice que estava em suspensão temporária."""

    ds_motivo: str = Field(..., max_length=300)
    dt_reativacao: str = Field(..., pattern=r"^\d{8}$")
    id_usuario: str = Field(..., max_length=20)


class HistoricoItem(BaseModel):
    dt_hora_acao: datetime
    tp_acao: str
    ds_descricao: str
    id_usuario: str
    ds_valor_antes: str | None = None
    ds_valor_depois: str | None = None


class HistoricoRequest(BaseModel):
    tp_acao: str = Field(..., max_length=40)
    ds_descricao: str = Field(..., max_length=200)
    id_usuario: str = Field("PORTAL", max_length=20)
    ds_valor_antes: str | None = None
    ds_valor_depois: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _get_apolice(nr_apolice: str) -> dict:
    """Busca apólice em memória; se não encontrar, hidrata a partir do Supabase."""
    import logging as _log
    _logger = _log.getLogger(__name__)

    from app.api.emissao.proposta import _APOLICES

    a = _APOLICES.get(nr_apolice)
    if a:
        return a

    # Fallback: hidrata a partir do Supabase (apólices criadas pelo Portal do Corretor)
    try:
        from app.core.config import settings
        from supabase import create_client

        url = str(settings.supabase_url or "")
        key = str(settings.supabase_service_key or settings.supabase_anon_key or "")
        _logger.warning("_get_apolice: buscando %s no Supabase (url=%s…)", nr_apolice, url[:30])

        if url and "SEU-PROJETO" not in url and key:
            sb = create_client(url, key)
            res = sb.table("estipulantes").select("*").eq("nr_apolice", nr_apolice).execute()
            _logger.warning("_get_apolice Supabase: %d rows para %s", len(res.data or []), nr_apolice)
            if res.data:
                row = res.data[0]
                hydrated = {
                    "nr_apolice": row["nr_apolice"],
                    "cd_empresa": 0,
                    "cd_cpf_segurado": "00000000000",
                    "cd_produto": "VGC",
                    "tp_capital": row.get("tp_capital") or row.get("tp_cobertura", "F"),
                    "vl_capital": 0,
                    "dt_emissao": row.get("dt_cadastro", ""),
                    "dt_inicio_vigencia": row.get("dt_cadastro", ""),
                    "cd_status": row.get("cd_status", "AT"),
                    "nm_razao_social": row.get("nm_razao_social", ""),
                    "cd_cnpj_estipulante": row.get("cd_cnpj", ""),
                    "ts_emissao": datetime.utcnow(),
                    "dt_cancelamento": row.get("dt_cancelamento"),
                    "ds_motivo_cancelamento": row.get("ds_motivo_cancelamento"),
                    "tp_suspensao": row.get("tp_suspensao"),
                    "dt_inicio_suspensao": row.get("dt_inicio_suspensao"),
                    "fl_cobranca_suspensa": row.get("fl_cobranca_suspensa", "N"),
                    "_supabase_row": row,
                }
                _APOLICES[nr_apolice] = hydrated
                _logger.warning("_get_apolice hydrated OK: %s status=%s", nr_apolice, hydrated["cd_status"])
                return hydrated
        else:
            _logger.error("_get_apolice: Supabase não configurado! url=%r key_len=%d", url, len(key))
    except Exception as _e:
        _logger.error("_get_apolice fallback falhou para %s: %s", nr_apolice, _e, exc_info=True)

    raise HTTPException(404, detail=f"Apólice {nr_apolice} não encontrada.")


def _persistir_status_supabase(nr_apolice: str, apolice: dict) -> None:
    """Persiste alterações de status/cancelamento no Supabase para apólices do Portal."""
    if "_supabase_row" not in apolice:
        return  # apólice criada em memória pura, sem registro Supabase
    try:
        from app.core.config import settings
        from supabase import create_client

        url = str(settings.supabase_url)
        key = settings.supabase_service_key or settings.supabase_anon_key
        if not (url and url != "https://SEU-PROJETO.supabase.co" and key):
            return
        sb = create_client(url, key)
        update: dict = {}
        # Campos de status — só envia se a coluna existir (migração v2)
        for campo in (
            "cd_status", "dt_cancelamento", "ds_motivo_cancelamento",
            "tp_suspensao", "dt_inicio_suspensao", "dt_prev_reativacao",
            "nr_processo_judicial", "nm_orgao_judicial", "fl_cobranca_suspensa",
            "cd_subestipulante_suc",
        ):
            if campo in apolice and apolice[campo] is not None:
                update[campo] = apolice[campo]
        if update:
            sb.table("estipulantes").update(update).eq("nr_apolice", nr_apolice).execute()
    except Exception:
        pass  # silencioso — não impede operação se Supabase estiver indisponível


def _registrar(
    nr_apolice: str,
    tp_acao: str,
    descricao: str,
    usuario: str,
    antes: str = None,
    depois: str = None,
):
    _HISTORICO.setdefault(nr_apolice, []).append(
        {
            "dt_hora_acao": datetime.utcnow(),
            "tp_acao": tp_acao,
            "ds_descricao": descricao,
            "id_usuario": usuario,
            "ds_valor_antes": antes,
            "ds_valor_depois": depois,
        }
    )


def _proximo_vencimento(dia: int, competencia_ini: str) -> str:
    """Calcula a data do próximo vencimento."""
    from calendar import monthrange

    try:
        ano = int(competencia_ini[:4])
        mes = int(competencia_ini[4:6])
        _, ultimo_dia = monthrange(ano, mes)
        dia_real = min(dia, ultimo_dia)
        return f"{ano:04d}{mes:02d}{dia_real:02d}"
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG FATURAMENTO
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/config/faturamento",
    response_model=ConfigFaturamentoResponse,
    summary="Consulta configuração de faturamento",
)
def get_config_faturamento(nr_apolice: str):
    _get_apolice(nr_apolice)
    cfg = _CONFIG.get(nr_apolice)
    if not cfg:
        raise HTTPException(
            404,
            detail=f"Apólice {nr_apolice} ainda não tem configuração de faturamento.",
        )
    return cfg


@router.put(
    "/config/faturamento",
    response_model=ConfigFaturamentoResponse,
    summary="Salva / atualiza configuração de faturamento",
)
def set_config_faturamento(
    nr_apolice: str, payload: ConfigFaturamentoRequest, id_usuario: str = "SISTEMA"
):
    _get_apolice(nr_apolice)
    anterior = _CONFIG.get(nr_apolice, {}).copy()
    cfg = {
        "nr_apolice": nr_apolice,
        **payload.model_dump(),
        "dt_proximo_vencimento": _proximo_vencimento(
            payload.dia_vencimento, payload.mes_competencia_ini
        ),
        "dt_ultima_atualizacao": datetime.today().strftime("%Y%m%d"),
        "id_usuario_atualizacao": id_usuario,
    }
    _CONFIG[nr_apolice] = cfg
    _registrar(
        nr_apolice,
        "CONFIG_FATURAMENTO",
        "Configuração de faturamento atualizada",
        id_usuario,
        str(anterior) if anterior else None,
        f"dia_venc={payload.dia_vencimento} "
        f"corte={payload.dia_corte} "
        f"per={payload.periodicidade} "
        f"repete={payload.fl_repetir_sem_movimento}",
    )
    return cfg


@router.put(
    "/config/faturamento/vencimento",
    response_model=ConfigFaturamentoResponse,
    summary="Muda dia de vencimento com vigência futura",
)
def mudar_vencimento(nr_apolice: str, payload: MudancaVencimentoRequest):
    _get_apolice(nr_apolice)
    cfg = _CONFIG.get(nr_apolice)
    if not cfg:
        raise HTTPException(
            404, detail="Configure o faturamento antes de alterar o vencimento."
        )
    antes = cfg["dia_vencimento"]
    cfg["dia_vencimento"] = payload.dia_vencimento_novo
    cfg["dt_ultima_atualizacao"] = datetime.today().strftime("%Y%m%d")
    cfg["id_usuario_atualizacao"] = payload.id_usuario
    cfg["dt_proximo_vencimento"] = payload.dt_vigencia
    _registrar(
        nr_apolice,
        "MUDANCA_VENCIMENTO",
        f"Dia de vencimento alterado de {antes} para {payload.dia_vencimento_novo}",
        payload.id_usuario,
        str(antes),
        str(payload.dia_vencimento_novo),
    )
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# SUBESTIPULANTES
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/subestipulantes",
    response_model=list[SubestipulanteResponse],
    summary="Lista subestipulantes da apólice",
)
def listar_subestipulantes(nr_apolice: str, cd_status: str | None = None):
    _get_apolice(nr_apolice)
    result = _SUBESTIPULANTES.get(nr_apolice, [])
    if cd_status:
        result = [s for s in result if s["cd_status"] == cd_status]
    return result


@router.post(
    "/subestipulantes",
    response_model=SubestipulanteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona subestipulante à apólice",
)
def adicionar_subestipulante(nr_apolice: str, payload: SubestipulanteCreate):
    global _NEXT_SUBESTIP
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.setdefault(nr_apolice, [])
    for s in lista:
        if s["cd_cnpj"] == payload.cd_cnpj and s["cd_status"] != "CA":
            raise HTTPException(
                409, detail=f"CNPJ {payload.cd_cnpj} já está ativo nesta apólice."
            )
    subestip = {
        "cd_subestipulante": _NEXT_SUBESTIP,
        "nr_apolice": nr_apolice,
        **payload.model_dump(),
        "cd_status": "AT",
        "dt_cancelamento": None,
        "ds_motivo_cancel": None,
    }
    lista.append(subestip)
    _NEXT_SUBESTIP += 1
    _registrar(
        nr_apolice,
        "SUBESTIP_INCLUS",
        f"Subestipulante {payload.nm_razao_social} ({payload.cd_cnpj}) incluído",
        payload.id_usuario,
    )
    return subestip


@router.put(
    "/subestipulantes/{cd_subestipulante}/cancelar",
    response_model=SubestipulanteResponse,
    summary="Cancela subestipulante da apólice",
)
def cancelar_subestipulante(
    nr_apolice: str, cd_subestipulante: int, payload: AlterarSubestipulanteRequest
):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next(
        (s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None
    )
    if not subestip:
        raise HTTPException(
            404, detail=f"Subestipulante {cd_subestipulante} não encontrado."
        )
    if subestip["cd_status"] == "CA":
        raise HTTPException(409, detail="Subestipulante já cancelado.")
    subestip["cd_status"] = "CA"
    subestip["dt_cancelamento"] = payload.dt_vigencia
    subestip["ds_motivo_cancel"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    _registrar(
        nr_apolice,
        "SUBESTIP_CANCEL",
        f"Subestipulante {subestip['nm_razao_social']} cancelado",
        payload.id_usuario,
        "AT",
        "CA",
    )
    return subestip


@router.put(
    "/subestipulantes/{cd_subestipulante}/suspender",
    response_model=SubestipulanteResponse,
    summary="Suspende subestipulante temporariamente",
)
def suspender_subestipulante(
    nr_apolice: str, cd_subestipulante: int, payload: AlterarSubestipulanteRequest
):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next(
        (s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None
    )
    if not subestip:
        raise HTTPException(
            404, detail=f"Subestipulante {cd_subestipulante} não encontrado."
        )
    if subestip["cd_status"] != "AT":
        raise HTTPException(
            409, detail=f"Status {subestip['cd_status']} não permite suspensão."
        )
    subestip["cd_status"] = "SU"
    subestip["ds_motivo_cancel"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    _registrar(
        nr_apolice,
        "SUBESTIP_SUSPEN",
        f"Subestipulante {subestip['nm_razao_social']} suspenso",
        payload.id_usuario,
        "AT",
        "SU",
    )
    return subestip


@router.put(
    "/subestipulantes/{cd_subestipulante}/reativar",
    response_model=SubestipulanteResponse,
    summary="Reativa subestipulante suspenso",
)
def reativar_subestipulante(nr_apolice: str, cd_subestipulante: int, id_usuario: str):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next(
        (s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None
    )
    if not subestip:
        raise HTTPException(
            404, detail=f"Subestipulante {cd_subestipulante} não encontrado."
        )
    if subestip["cd_status"] != "SU":
        raise HTTPException(
            409, detail="Somente subestipulantes suspensos podem ser reativados."
        )
    subestip["cd_status"] = "AT"
    _registrar(
        nr_apolice,
        "SUBESTIP_REATIV",
        f"Subestipulante {subestip['nm_razao_social']} reativado",
        id_usuario,
        "SU",
        "AT",
    )
    return subestip


# ══════════════════════════════════════════════════════════════════════════════
# CONTATOS E ENDEREÇO
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/contatos",
    response_model=list[ContatoResponse],
    summary="Lista contatos da apólice",
)
def listar_contatos(nr_apolice: str):
    _get_apolice(nr_apolice)
    return _CONTATOS.get(nr_apolice, [])


@router.post(
    "/contatos",
    response_model=ContatoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona contato à apólice",
)
def adicionar_contato(nr_apolice: str, payload: ContatoCreate):
    global _NEXT_CONTATO
    _get_apolice(nr_apolice)
    lista = _CONTATOS.setdefault(nr_apolice, [])
    contato = {
        "cd_contato": _NEXT_CONTATO,
        "nr_apolice": nr_apolice,
        **payload.model_dump(),
        "cd_status": "AT",
    }
    lista.append(contato)
    _NEXT_CONTATO += 1
    _registrar(
        nr_apolice,
        "CONTATO_INCLUS",
        f"Contato {payload.nm_contato} ({payload.tp_contato}) incluído",
        "SISTEMA",
    )
    return contato


@router.put(
    "/contatos/{cd_contato}",
    response_model=ContatoResponse,
    summary="Atualiza contato (e-mail, telefone, celular)",
)
def atualizar_contato(nr_apolice: str, cd_contato: int, payload: ContatoCreate):
    _get_apolice(nr_apolice)
    lista = _CONTATOS.get(nr_apolice, [])
    contato = next((c for c in lista if c["cd_contato"] == cd_contato), None)
    if not contato:
        raise HTTPException(404, detail=f"Contato {cd_contato} não encontrado.")
    antes_email = contato.get("cd_email")
    contato.update(payload.model_dump())
    if antes_email != payload.cd_email:
        _registrar(
            nr_apolice,
            "EMAIL_ALTERADO",
            f"E-mail do contato {contato['nm_contato']} alterado",
            "SISTEMA",
            antes_email,
            payload.cd_email,
        )
    return contato


@router.delete(
    "/contatos/{cd_contato}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove contato da apólice",
)
def remover_contato(nr_apolice: str, cd_contato: int, id_usuario: str = "SISTEMA"):
    _get_apolice(nr_apolice)
    lista = _CONTATOS.get(nr_apolice, [])
    contato = next((c for c in lista if c["cd_contato"] == cd_contato), None)
    if not contato:
        raise HTTPException(404, detail=f"Contato {cd_contato} não encontrado.")
    lista.remove(contato)
    _registrar(
        nr_apolice,
        "CONTATO_REMOVIDO",
        f"Contato {contato['nm_contato']} removido",
        id_usuario,
    )


@router.put("/endereco", summary="Atualiza endereço da apólice / estipulante")
def atualizar_endereco(nr_apolice: str, payload: EnderecoRequest):
    apolice = _get_apolice(nr_apolice)
    antes = apolice.get("ds_endereco")
    apolice["ds_endereco"] = (
        f"{payload.ds_logradouro}, {payload.nr_numero}"
        + (f" {payload.ds_complemento}" if payload.ds_complemento else "")
        + f" - {payload.nm_bairro} - {payload.nm_cidade}/{payload.sg_estado} - CEP {payload.cd_cep}"
    )
    _registrar(
        nr_apolice,
        "ENDERECO_ALTERADO",
        "Endereço da apólice atualizado",
        payload.id_usuario,
        antes,
        apolice["ds_endereco"],
    )
    return {"nr_apolice": nr_apolice, "ds_endereco": apolice["ds_endereco"]}


# ══════════════════════════════════════════════════════════════════════════════
# OPERAÇÕES ESPECIAIS
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/renovar", summary="Renova apólice — gera nova vigência")
def renovar_apolice(nr_apolice: str, payload: RenovacaoRequest):
    from app.api.emissao.proposta import _APOLICES

    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(
            409,
            detail=f"Apólice {nr_apolice} está {apolice['cd_status']} — não pode ser renovada.",
        )
    if payload.dt_fim_nova_vigencia <= payload.dt_inicio_nova_vigencia:
        raise HTTPException(422, detail="Data fim deve ser maior que data início.")

    # Gera número da nova apólice
    import datetime as _dt

    nr_nova = f"{_dt.datetime.today().year}.APO.R{len(_APOLICES)+1:05d}"

    nova_apolice = {
        **apolice,
        "nr_apolice": nr_nova,
        "dt_emissao": datetime.today().strftime("%Y%m%d"),
        "dt_inicio_vigencia": payload.dt_inicio_nova_vigencia,
        "dt_fim_vigencia": payload.dt_fim_nova_vigencia,
        "cd_status": "AT",
        "nr_apolice_origem": nr_apolice,
        "ts_emissao": datetime.utcnow(),
    }
    _APOLICES[nr_nova] = nova_apolice

    # Copia config de faturamento se solicitado
    if payload.fl_manter_config == "S" and nr_apolice in _CONFIG:
        _CONFIG[nr_nova] = {**_CONFIG[nr_apolice], "nr_apolice": nr_nova}

    _registrar(
        nr_apolice,
        "RENOVACAO",
        f"Apólice renovada → {nr_nova} ({payload.dt_inicio_nova_vigencia} a {payload.dt_fim_nova_vigencia})",
        payload.id_usuario,
    )

    return {
        "nr_apolice_origem": nr_apolice,
        "nr_apolice_nova": nr_nova,
        "dt_inicio": payload.dt_inicio_nova_vigencia,
        "dt_fim": payload.dt_fim_nova_vigencia,
        "fl_config_copiada": payload.fl_manter_config,
    }


@router.put("/produto", summary="Altera produto da apólice (VGC ↔ GLB)")
def alterar_produto(nr_apolice: str, payload: AlteracaoProdutoRequest):
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(409, detail="Apólice não está ativa.")
    antes = apolice["cd_produto"]
    if antes == payload.cd_produto_novo:
        raise HTTPException(409, detail=f"Apólice já é do produto {antes}.")
    apolice["cd_produto"] = payload.cd_produto_novo
    _registrar(
        nr_apolice,
        "PRODUTO_ALTERADO",
        f"Produto alterado de {antes} para {payload.cd_produto_novo}",
        payload.id_usuario,
        antes,
        payload.cd_produto_novo,
    )
    return {
        "nr_apolice": nr_apolice,
        "cd_produto_anterior": antes,
        "cd_produto_novo": payload.cd_produto_novo,
        "dt_vigencia": payload.dt_vigencia,
    }


@router.put("/transferir-cnpj", summary="Transferência de CNPJ do estipulante")
def transferir_cnpj(nr_apolice: str, payload: TransferenciaCnpjRequest):
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(409, detail="Apólice não está ativa.")
    antes_cnpj = apolice.get("cd_cnpj_estipulante", "N/A")
    antes_nome = apolice.get("nm_estipulante", "N/A")
    apolice["cd_cnpj_estipulante"] = payload.cd_cnpj_novo
    apolice["nm_estipulante"] = payload.nm_razao_social_novo
    _registrar(
        nr_apolice,
        "TRANSF_CNPJ",
        f"CNPJ transferido de {antes_cnpj} ({antes_nome}) "
        f"para {payload.cd_cnpj_novo} ({payload.nm_razao_social_novo})",
        payload.id_usuario,
        f"{antes_cnpj} / {antes_nome}",
        f"{payload.cd_cnpj_novo} / {payload.nm_razao_social_novo}",
    )
    return {
        "nr_apolice": nr_apolice,
        "cd_cnpj_anterior": antes_cnpj,
        "nm_razao_anterior": antes_nome,
        "cd_cnpj_novo": payload.cd_cnpj_novo,
        "nm_razao_nova": payload.nm_razao_social_novo,
        "dt_vigencia": payload.dt_vigencia,
    }


@router.put("/cancelar", summary="Cancela a apólice")
def cancelar_apolice(nr_apolice: str, payload: CancelamentoRequest):
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] == "CA":
        raise HTTPException(409, detail="Apólice já cancelada.")
    apolice["cd_status"] = "CA"
    apolice["dt_cancelamento"] = payload.dt_cancelamento
    apolice["ds_motivo_cancelamento"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    apolice["id_usuario_cancel"] = payload.id_usuario
    # Cancela também todos os subestipulantes ativos/suspensos
    for s in _SUBESTIPULANTES.get(nr_apolice, []):
        if s["cd_status"] != "CA":
            s["cd_status"] = "CA"
            s["dt_cancelamento"] = payload.dt_cancelamento
            s["ds_motivo_cancel"] = f"[CANCEL_TOTAL] {payload.ds_motivo}"
    _registrar(
        nr_apolice,
        "CANCELAMENTO",
        f"Cancelamento total da apólice e subestipulantes. Motivo: [{payload.cd_motivo}] {payload.ds_motivo}",
        payload.id_usuario,
        "AT",
        "CA",
    )
    _persistir_status_supabase(nr_apolice, apolice)
    return {
        "nr_apolice": nr_apolice,
        "cd_status": "CA",
        "tp_cancelamento": "TOTAL",
        "dt_cancelamento": payload.dt_cancelamento,
        "ds_motivo": f"[{payload.cd_motivo}] {payload.ds_motivo}",
        "fl_devolucao_premio": payload.fl_devolver_premio,
    }


@router.put(
    "/cancelar/transferencia",
    summary="Cancela apólice principal transferindo para subestipulante",
)
def cancelar_com_transferencia(
    nr_apolice: str, payload: CancelamentoTransferenciaRequest
):
    """Cancela a apólice principal mantendo a cobertura via um subestipulante sucessor.
    A apólice original fica com status CA e permanece no histórico para consultas."""
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] == "CA":
        raise HTTPException(409, detail="Apólice já cancelada.")

    lista_sub = _SUBESTIPULANTES.get(nr_apolice, [])
    sucessor = next(
        (s for s in lista_sub if s["cd_subestipulante"] == payload.cd_subestipulante_sucessor),
        None,
    )
    if not sucessor:
        raise HTTPException(
            404,
            detail=f"Subestipulante {payload.cd_subestipulante_sucessor} não encontrado na apólice.",
        )
    if sucessor["cd_status"] != "AT":
        raise HTTPException(
            409,
            detail=f"Subestipulante {payload.cd_subestipulante_sucessor} não está ativo (status={sucessor['cd_status']}).",
        )

    # Demais subestipulantes (exceto o sucessor) são cancelados
    for s in lista_sub:
        if s["cd_subestipulante"] != payload.cd_subestipulante_sucessor and s["cd_status"] != "CA":
            s["cd_status"] = "CA"
            s["dt_cancelamento"] = payload.dt_cancelamento
            s["ds_motivo_cancel"] = f"[TRANSF_SUBESTIP] Transferência para subestipulante {payload.cd_subestipulante_sucessor}"

    # Marca a apólice principal como cancelada (permanece em histórico)
    apolice["cd_status"] = "CA"
    apolice["dt_cancelamento"] = payload.dt_cancelamento
    apolice["ds_motivo_cancelamento"] = (
        f"[{payload.cd_motivo}] {payload.ds_motivo} "
        f"— transferida para subestipulante {payload.cd_subestipulante_sucessor} ({sucessor['nm_razao_social']})"
    )
    apolice["cd_subestipulante_sucessor"] = payload.cd_subestipulante_sucessor
    apolice["id_usuario_cancel"] = payload.id_usuario

    _registrar(
        nr_apolice,
        "CANCEL_TRANSF",
        (
            f"Apólice principal cancelada. Cobertura transferida para subestipulante "
            f"{payload.cd_subestipulante_sucessor} ({sucessor['nm_razao_social']}). "
            f"Motivo: [{payload.cd_motivo}] {payload.ds_motivo}"
        ),
        payload.id_usuario,
        "AT",
        f"CA→SUBESTIP_{payload.cd_subestipulante_sucessor}",
    )
    apolice["cd_subestipulante_suc"] = payload.cd_subestipulante_sucessor
    _persistir_status_supabase(nr_apolice, apolice)
    return {
        "nr_apolice": nr_apolice,
        "cd_status": "CA",
        "tp_cancelamento": "TRANSFERENCIA",
        "dt_cancelamento": payload.dt_cancelamento,
        "ds_motivo": f"[{payload.cd_motivo}] {payload.ds_motivo}",
        "cd_subestipulante_sucessor": payload.cd_subestipulante_sucessor,
        "nm_subestipulante_sucessor": sucessor["nm_razao_social"],
        "fl_devolucao_premio": payload.fl_devolver_premio,
        "ds_obs": "Apólice principal mantida em histórico para consultas.",
    }


@router.put(
    "/cancelar/suspensao-temporaria",
    summary="Suspende temporariamente a apólice (sem cobrança)",
)
def suspender_temporariamente_apolice(
    nr_apolice: str, payload: SuspensaoTemporariaRequest
):
    """Suspende a apólice e todos os subestipulantes sem gerar cobrança durante o período.
    - CLIENTE: a pedido do cliente.
    - JUDICIAL: ordem judicial — prêmio pago pela empresa (não pelo estipulante contratante)."""
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] not in ("AT",):
        raise HTTPException(
            409,
            detail=f"Apólice está {apolice['cd_status']} — somente apólices ativas podem ser suspensas.",
        )
    if payload.tp_origem == "JUDICIAL":
        if not payload.dt_prev_reativacao:
            raise HTTPException(
                422,
                detail="Para suspensão JUDICIAL, dt_prev_reativacao é obrigatória.",
            )

    # Suspende todos os subestipulantes ativos
    for s in _SUBESTIPULANTES.get(nr_apolice, []):
        if s["cd_status"] == "AT":
            s["cd_status"] = "SU"
            s["ds_motivo_cancel"] = f"[SUSP_TEMP_{payload.tp_origem}] {payload.ds_motivo}"

    apolice["cd_status"] = "SU"
    apolice["tp_suspensao"] = payload.tp_origem
    apolice["dt_inicio_suspensao"] = payload.dt_inicio_suspensao
    apolice["dt_prev_reativacao"] = payload.dt_prev_reativacao
    apolice["nr_processo_judicial"] = payload.nr_processo_judicial
    apolice["nm_orgao_judicial"] = payload.nm_orgao_judicial
    apolice["fl_cobranca_suspensa"] = "S"
    apolice["id_usuario_suspensao"] = payload.id_usuario

    descricao = (
        f"Suspensão temporária ({payload.tp_origem}): {payload.ds_motivo}"
        + (f" | Processo: {payload.nr_processo_judicial}" if payload.nr_processo_judicial else "")
        + (f" | Órgão: {payload.nm_orgao_judicial}" if payload.nm_orgao_judicial else "")
        + (f" | Prev. reativação: {payload.dt_prev_reativacao}" if payload.dt_prev_reativacao else "")
    )
    _registrar(
        nr_apolice,
        "SUSP_TEMPORARIA",
        descricao,
        payload.id_usuario,
        "AT",
        f"SU_{payload.tp_origem}",
    )
    _persistir_status_supabase(nr_apolice, apolice)
    return {
        "nr_apolice": nr_apolice,
        "cd_status": "SU",
        "tp_cancelamento": "SUSPENSAO_TEMPORARIA",
        "tp_origem": payload.tp_origem,
        "dt_inicio_suspensao": payload.dt_inicio_suspensao,
        "dt_prev_reativacao": payload.dt_prev_reativacao,
        "fl_cobranca_suspensa": "S",
        "nr_processo_judicial": payload.nr_processo_judicial,
        "nm_orgao_judicial": payload.nm_orgao_judicial,
        "ds_obs": (
            "Prêmio pago pela empresa contratante, sem cobrança ao estipulante."
            if payload.tp_origem == "JUDICIAL"
            else "Suspensão temporária a pedido do cliente."
        ),
    }


@router.put(
    "/cancelar/reativar-suspensao",
    summary="Reativa apólice em suspensão temporária",
)
def reativar_suspensao_apolice(nr_apolice: str, payload: ReativacaoSuspensaoRequest):
    """Reativa a apólice e todos os subestipulantes suspensos."""
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "SU":
        raise HTTPException(
            409,
            detail=f"Apólice está {apolice['cd_status']} — somente apólices suspensas podem ser reativadas aqui.",
        )

    for s in _SUBESTIPULANTES.get(nr_apolice, []):
        if s["cd_status"] == "SU":
            s["cd_status"] = "AT"

    apolice["cd_status"] = "AT"
    apolice["dt_reativacao_suspensao"] = payload.dt_reativacao
    apolice["fl_cobranca_suspensa"] = "N"

    _registrar(
        nr_apolice,
        "REATIV_SUSPENSAO",
        f"Apólice reativada após suspensão temporária. Motivo: {payload.ds_motivo}",
        payload.id_usuario,
        "SU",
        "AT",
    )
    _persistir_status_supabase(nr_apolice, apolice)
    return {
        "nr_apolice": nr_apolice,
        "cd_status": "AT",
        "dt_reativacao": payload.dt_reativacao,
        "ds_obs": "Apólice e subestipulantes reativados. Cobrança retomada.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# HISTÓRICO DE ALTERAÇÕES
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/historico",
    response_model=list[HistoricoItem],
    summary="Histórico completo de alterações da apólice",
)
def historico_apolice(
    nr_apolice: str,
    tp_acao: str | None = None,
    limit: int = 50,
):
    _get_apolice(nr_apolice)
    result = _HISTORICO.get(nr_apolice, [])
    if tp_acao:
        result = [h for h in result if h["tp_acao"] == tp_acao]
    return result[-limit:]


@router.post(
    "/historico",
    response_model=HistoricoItem,
    status_code=status.HTTP_201_CREATED,
    summary="Registra entrada manual no histórico da apólice",
)
def registrar_historico(nr_apolice: str, payload: HistoricoRequest):
    _get_apolice(nr_apolice)
    _registrar(
        nr_apolice,
        payload.tp_acao,
        payload.ds_descricao,
        payload.id_usuario,
        payload.ds_valor_antes,
        payload.ds_valor_depois,
    )
    return _HISTORICO[nr_apolice][-1]
