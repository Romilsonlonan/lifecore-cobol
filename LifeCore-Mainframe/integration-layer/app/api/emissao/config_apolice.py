"""
Configuração de Apólice — Router
Gerencia todas as configurações operacionais de uma apólice:
faturamento, subestipulantes, contatos, endereço, renovação,
transferência de CNPJ, cancelamento e histórico de alterações.

Prefixo: /api/emissao/apolices/{nr_apolice}/config
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()

# ── Stores em memória ─────────────────────────────────────────────────────────
# Chave: nr_apolice

_CONFIG: dict[str, dict]              = {}   # configurações de faturamento
_SUBESTIPULANTES: dict[str, list]     = {}   # subestipulantes por apólice
_CONTATOS: dict[str, list]            = {}   # contatos por apólice
_HISTORICO: dict[str, list]           = {}   # log de alterações

_NEXT_SUBESTIP = 1
_NEXT_CONTATO  = 1


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

# ── Faturamento ───────────────────────────────────────────────────────────────

class ConfigFaturamentoRequest(BaseModel):
    # Competência e datas
    dia_vencimento:     int     = Field(..., ge=1, le=31,
                                    description="Dia do mês para vencimento da fatura")
    dia_corte:          int     = Field(..., ge=1, le=31,
                                    description="Dia de corte para inclusão de vidas no mês")
    mes_competencia_ini: str    = Field(..., pattern=r"^\d{6}$",
                                    description="Competência inicial AAAAMM")
    periodicidade:      str     = Field(...,
                                    pattern=r"^(MN|BM|TR|SM|AN)$",
                                    description="MN=Mensal BM=Bimestral TR=Trimestral SM=Semestral AN=Anual")

    # Repetição de faturamento
    fl_repetir_sem_movimento: str = Field("N",
                                    pattern=r"^[SN]$",
                                    description="S=repete fatura anterior quando não há movimentação de vidas")
    ds_obs_repeticao:   Optional[str] = Field(None, max_length=200,
                                    description="Observação sobre a regra de repetição")

    # Forma de cobrança
    forma_cobranca:     str     = Field(...,
                                    pattern=r"^(BO|CC|DB|PI)$",
                                    description="BO=Boleto CC=Cartão DB=Débito PI=PIX")
    fl_nf_eletronica:   str     = Field("S", pattern=r"^[SN]$",
                                    description="Emite NF-e automaticamente ao faturar")

    # E-mail de fatura
    cd_email_fatura:    Optional[str] = Field(None, max_length=120,
                                    description="E-mail que recebe a fatura (padrão: contato da apólice)")
    cd_email_copia:     Optional[str] = Field(None, max_length=120,
                                    description="CC para cópia da fatura")

    # Observações gerais
    ds_observacao:      Optional[str] = Field(None, max_length=300)


class ConfigFaturamentoResponse(ConfigFaturamentoRequest):
    nr_apolice:             str
    dt_proximo_vencimento:  Optional[str] = None
    dt_ultima_atualizacao:  Optional[str] = None
    id_usuario_atualizacao: Optional[str] = None
    model_config = {"from_attributes": True}


# ── Mudança de vencimento ──────────────────────────────────────────────────────

class MudancaVencimentoRequest(BaseModel):
    dia_vencimento_novo: int   = Field(..., ge=1, le=31)
    dt_vigencia:         str   = Field(..., pattern=r"^\d{8}$",
                                    description="A partir de qual competência (AAAAMMDD)")
    ds_motivo:           str   = Field(..., max_length=200)
    id_usuario:          str   = Field(..., max_length=20)


# ── Subestipulante ─────────────────────────────────────────────────────────────

class SubestipulanteCreate(BaseModel):
    cd_cnpj:            str     = Field(..., min_length=14, max_length=14)
    nm_razao_social:    str     = Field(..., max_length=80)
    nm_nome_reduzido:   Optional[str] = Field(None, max_length=30)
    cd_email:           Optional[str] = Field(None, max_length=120)
    nr_telefone:        Optional[str] = Field(None, max_length=20)
    nm_responsavel:     Optional[str] = Field(None, max_length=80,
                                    description="Nome do responsável de RH")
    cd_email_responsavel: Optional[str] = Field(None, max_length=120)
    dt_inclusao_apolice:  str   = Field(..., pattern=r"^\d{8}$",
                                    description="Data de inclusão na apólice")
    ds_observacao:      Optional[str] = Field(None, max_length=200)
    id_usuario:         str     = Field(..., max_length=20)


class SubestipulanteResponse(SubestipulanteCreate):
    cd_subestipulante:  int
    nr_apolice:         str
    cd_status:          str    # AT=Ativo CA=Cancelado SU=Suspenso
    dt_cancelamento:    Optional[str] = None
    ds_motivo_cancel:   Optional[str] = None
    model_config = {"from_attributes": True}


class AlterarSubestipulanteRequest(BaseModel):
    cd_motivo:  str = Field(..., max_length=4,
                    description="Código do motivo (ex: R001=desligamento)")
    ds_motivo:  str = Field(..., max_length=200)
    dt_vigencia: str = Field(..., pattern=r"^\d{8}$",
                    description="Data de vigência da alteração")
    id_usuario:  str = Field(..., max_length=20)


# ── Contatos e Endereço ───────────────────────────────────────────────────────

class ContatoCreate(BaseModel):
    tp_contato:     str     = Field(...,
                                pattern=r"^(RH|FIN|DIR|TEC|OUT)$",
                                description="RH=Recursos Humanos FIN=Financeiro DIR=Diretoria TEC=TI OUT=Outro")
    nm_contato:     str     = Field(..., max_length=80)
    cd_cargo:       Optional[str] = Field(None, max_length=60)
    cd_email:       str     = Field(..., max_length=120)
    cd_email_copia: Optional[str] = Field(None, max_length=120)
    nr_telefone:    Optional[str] = Field(None, max_length=20)
    nr_celular:     Optional[str] = Field(None, max_length=20)
    fl_recebe_fatura: str   = Field("N", pattern=r"^[SN]$")
    fl_recebe_apolice: str  = Field("N", pattern=r"^[SN]$")
    fl_recebe_certificado: str = Field("N", pattern=r"^[SN]$")
    ds_observacao:  Optional[str] = Field(None, max_length=200)


class ContatoResponse(ContatoCreate):
    cd_contato:     int
    nr_apolice:     str
    cd_status:      str
    model_config = {"from_attributes": True}


class EnderecoRequest(BaseModel):
    ds_logradouro:  str     = Field(..., max_length=100)
    nr_numero:      str     = Field(..., max_length=10)
    ds_complemento: Optional[str] = Field(None, max_length=50)
    nm_bairro:      str     = Field(..., max_length=60)
    nm_cidade:      str     = Field(..., max_length=60)
    sg_estado:      str     = Field(..., min_length=2, max_length=2)
    cd_cep:         str     = Field(..., min_length=8, max_length=8)
    id_usuario:     str     = Field(..., max_length=20)


# ── Operações especiais ───────────────────────────────────────────────────────

class RenovacaoRequest(BaseModel):
    dt_inicio_nova_vigencia: str  = Field(..., pattern=r"^\d{8}$")
    dt_fim_nova_vigencia:    str  = Field(..., pattern=r"^\d{8}$")
    fl_manter_config:        str  = Field("S", pattern=r"^[SN]$",
                                    description="S=copia toda a configuração atual para a renovação")
    ds_observacao:           Optional[str] = Field(None, max_length=200)
    id_usuario:              str  = Field(..., max_length=20)


class AlteracaoProdutoRequest(BaseModel):
    cd_produto_novo: str = Field(..., pattern=r"^(VGC|GLB)$")
    dt_vigencia:     str = Field(..., pattern=r"^\d{8}$")
    ds_motivo:       str = Field(..., max_length=200)
    id_usuario:      str = Field(..., max_length=20)


class TransferenciaCnpjRequest(BaseModel):
    cd_cnpj_novo:       str  = Field(..., min_length=14, max_length=14)
    nm_razao_social_novo: str = Field(..., max_length=80)
    dt_vigencia:        str  = Field(..., pattern=r"^\d{8}$")
    ds_motivo:          str  = Field(..., max_length=200)
    id_usuario:         str  = Field(..., max_length=20)


class CancelamentoRequest(BaseModel):
    cd_motivo:      str  = Field(..., max_length=4,
                            description="Código do motivo de cancelamento")
    ds_motivo:      str  = Field(..., max_length=300)
    dt_cancelamento: str = Field(..., pattern=r"^\d{8}$")
    fl_devolver_premio: str = Field("N", pattern=r"^[SN]$",
                            description="S=gerar crédito do prêmio proporcional")
    id_usuario:     str  = Field(..., max_length=20)


class HistoricoItem(BaseModel):
    dt_hora_acao:   datetime
    tp_acao:        str
    ds_descricao:   str
    id_usuario:     str
    ds_valor_antes: Optional[str] = None
    ds_valor_depois: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_apolice(nr_apolice: str) -> dict:
    from app.api.emissao.proposta import _APOLICES
    a = _APOLICES.get(nr_apolice)
    if not a:
        raise HTTPException(404, detail=f"Apólice {nr_apolice} não encontrada.")
    return a


def _registrar(nr_apolice: str, tp_acao: str, descricao: str,
               usuario: str, antes: str = None, depois: str = None):
    _HISTORICO.setdefault(nr_apolice, []).append({
        "dt_hora_acao":    datetime.utcnow(),
        "tp_acao":         tp_acao,
        "ds_descricao":    descricao,
        "id_usuario":      usuario,
        "ds_valor_antes":  antes,
        "ds_valor_depois": depois,
    })


def _proximo_vencimento(dia: int, competencia_ini: str) -> str:
    """Calcula a data do próximo vencimento."""
    from calendar import monthrange
    try:
        ano  = int(competencia_ini[:4])
        mes  = int(competencia_ini[4:6])
        _, ultimo_dia = monthrange(ano, mes)
        dia_real = min(dia, ultimo_dia)
        return f"{ano:04d}{mes:02d}{dia_real:02d}"
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG FATURAMENTO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/config/faturamento",
            response_model=ConfigFaturamentoResponse,
            summary="Consulta configuração de faturamento")
def get_config_faturamento(nr_apolice: str):
    _get_apolice(nr_apolice)
    cfg = _CONFIG.get(nr_apolice)
    if not cfg:
        raise HTTPException(404, detail=f"Apólice {nr_apolice} ainda não tem configuração de faturamento.")
    return cfg


@router.put("/config/faturamento",
            response_model=ConfigFaturamentoResponse,
            summary="Salva / atualiza configuração de faturamento")
def set_config_faturamento(nr_apolice: str, payload: ConfigFaturamentoRequest,
                           id_usuario: str = "SISTEMA"):
    _get_apolice(nr_apolice)
    anterior = _CONFIG.get(nr_apolice, {}).copy()
    cfg = {
        "nr_apolice":               nr_apolice,
        **payload.model_dump(),
        "dt_proximo_vencimento":    _proximo_vencimento(
                                        payload.dia_vencimento,
                                        payload.mes_competencia_ini),
        "dt_ultima_atualizacao":    datetime.today().strftime("%Y%m%d"),
        "id_usuario_atualizacao":   id_usuario,
    }
    _CONFIG[nr_apolice] = cfg
    _registrar(nr_apolice, "CONFIG_FATURAMENTO",
               "Configuração de faturamento atualizada",
               id_usuario,
               str(anterior) if anterior else None,
               f"dia_venc={payload.dia_vencimento} "
               f"corte={payload.dia_corte} "
               f"per={payload.periodicidade} "
               f"repete={payload.fl_repetir_sem_movimento}")
    return cfg


@router.put("/config/faturamento/vencimento",
            response_model=ConfigFaturamentoResponse,
            summary="Muda dia de vencimento com vigência futura")
def mudar_vencimento(nr_apolice: str, payload: MudancaVencimentoRequest):
    _get_apolice(nr_apolice)
    cfg = _CONFIG.get(nr_apolice)
    if not cfg:
        raise HTTPException(404, detail="Configure o faturamento antes de alterar o vencimento.")
    antes = cfg["dia_vencimento"]
    cfg["dia_vencimento"]            = payload.dia_vencimento_novo
    cfg["dt_ultima_atualizacao"]     = datetime.today().strftime("%Y%m%d")
    cfg["id_usuario_atualizacao"]    = payload.id_usuario
    cfg["dt_proximo_vencimento"]     = payload.dt_vigencia
    _registrar(nr_apolice, "MUDANCA_VENCIMENTO",
               f"Dia de vencimento alterado de {antes} para {payload.dia_vencimento_novo}",
               payload.id_usuario, str(antes), str(payload.dia_vencimento_novo))
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# SUBESTIPULANTES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/subestipulantes",
            response_model=list[SubestipulanteResponse],
            summary="Lista subestipulantes da apólice")
def listar_subestipulantes(nr_apolice: str, cd_status: Optional[str] = None):
    _get_apolice(nr_apolice)
    result = _SUBESTIPULANTES.get(nr_apolice, [])
    if cd_status:
        result = [s for s in result if s["cd_status"] == cd_status]
    return result


@router.post("/subestipulantes",
             response_model=SubestipulanteResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Adiciona subestipulante à apólice")
def adicionar_subestipulante(nr_apolice: str, payload: SubestipulanteCreate):
    global _NEXT_SUBESTIP
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.setdefault(nr_apolice, [])
    for s in lista:
        if s["cd_cnpj"] == payload.cd_cnpj and s["cd_status"] != "CA":
            raise HTTPException(
                409, detail=f"CNPJ {payload.cd_cnpj} já está ativo nesta apólice.")
    subestip = {
        "cd_subestipulante": _NEXT_SUBESTIP,
        "nr_apolice":        nr_apolice,
        **payload.model_dump(),
        "cd_status":         "AT",
        "dt_cancelamento":   None,
        "ds_motivo_cancel":  None,
    }
    lista.append(subestip)
    _NEXT_SUBESTIP += 1
    _registrar(nr_apolice, "SUBESTIP_INCLUS",
               f"Subestipulante {payload.nm_razao_social} ({payload.cd_cnpj}) incluído",
               payload.id_usuario)
    return subestip


@router.put("/subestipulantes/{cd_subestipulante}/cancelar",
            response_model=SubestipulanteResponse,
            summary="Cancela subestipulante da apólice")
def cancelar_subestipulante(nr_apolice: str, cd_subestipulante: int,
                            payload: AlterarSubestipulanteRequest):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next((s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None)
    if not subestip:
        raise HTTPException(404, detail=f"Subestipulante {cd_subestipulante} não encontrado.")
    if subestip["cd_status"] == "CA":
        raise HTTPException(409, detail="Subestipulante já cancelado.")
    subestip["cd_status"]        = "CA"
    subestip["dt_cancelamento"]  = payload.dt_vigencia
    subestip["ds_motivo_cancel"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    _registrar(nr_apolice, "SUBESTIP_CANCEL",
               f"Subestipulante {subestip['nm_razao_social']} cancelado",
               payload.id_usuario,
               "AT", "CA")
    return subestip


@router.put("/subestipulantes/{cd_subestipulante}/suspender",
            response_model=SubestipulanteResponse,
            summary="Suspende subestipulante temporariamente")
def suspender_subestipulante(nr_apolice: str, cd_subestipulante: int,
                             payload: AlterarSubestipulanteRequest):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next((s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None)
    if not subestip:
        raise HTTPException(404, detail=f"Subestipulante {cd_subestipulante} não encontrado.")
    if subestip["cd_status"] != "AT":
        raise HTTPException(409, detail=f"Status {subestip['cd_status']} não permite suspensão.")
    subestip["cd_status"]        = "SU"
    subestip["ds_motivo_cancel"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    _registrar(nr_apolice, "SUBESTIP_SUSPEN",
               f"Subestipulante {subestip['nm_razao_social']} suspenso",
               payload.id_usuario, "AT", "SU")
    return subestip


@router.put("/subestipulantes/{cd_subestipulante}/reativar",
            response_model=SubestipulanteResponse,
            summary="Reativa subestipulante suspenso")
def reativar_subestipulante(nr_apolice: str, cd_subestipulante: int, id_usuario: str):
    _get_apolice(nr_apolice)
    lista = _SUBESTIPULANTES.get(nr_apolice, [])
    subestip = next((s for s in lista if s["cd_subestipulante"] == cd_subestipulante), None)
    if not subestip:
        raise HTTPException(404, detail=f"Subestipulante {cd_subestipulante} não encontrado.")
    if subestip["cd_status"] != "SU":
        raise HTTPException(409, detail="Somente subestipulantes suspensos podem ser reativados.")
    subestip["cd_status"] = "AT"
    _registrar(nr_apolice, "SUBESTIP_REATIV",
               f"Subestipulante {subestip['nm_razao_social']} reativado",
               id_usuario, "SU", "AT")
    return subestip


# ══════════════════════════════════════════════════════════════════════════════
# CONTATOS E ENDEREÇO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/contatos",
            response_model=list[ContatoResponse],
            summary="Lista contatos da apólice")
def listar_contatos(nr_apolice: str):
    _get_apolice(nr_apolice)
    return _CONTATOS.get(nr_apolice, [])


@router.post("/contatos",
             response_model=ContatoResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Adiciona contato à apólice")
def adicionar_contato(nr_apolice: str, payload: ContatoCreate):
    global _NEXT_CONTATO
    _get_apolice(nr_apolice)
    lista = _CONTATOS.setdefault(nr_apolice, [])
    contato = {
        "cd_contato": _NEXT_CONTATO,
        "nr_apolice": nr_apolice,
        **payload.model_dump(),
        "cd_status":  "AT",
    }
    lista.append(contato)
    _NEXT_CONTATO += 1
    _registrar(nr_apolice, "CONTATO_INCLUS",
               f"Contato {payload.nm_contato} ({payload.tp_contato}) incluído",
               "SISTEMA")
    return contato


@router.put("/contatos/{cd_contato}",
            response_model=ContatoResponse,
            summary="Atualiza contato (e-mail, telefone, celular)")
def atualizar_contato(nr_apolice: str, cd_contato: int, payload: ContatoCreate):
    _get_apolice(nr_apolice)
    lista  = _CONTATOS.get(nr_apolice, [])
    contato = next((c for c in lista if c["cd_contato"] == cd_contato), None)
    if not contato:
        raise HTTPException(404, detail=f"Contato {cd_contato} não encontrado.")
    antes_email = contato.get("cd_email")
    contato.update(payload.model_dump())
    if antes_email != payload.cd_email:
        _registrar(nr_apolice, "EMAIL_ALTERADO",
                   f"E-mail do contato {contato['nm_contato']} alterado",
                   "SISTEMA", antes_email, payload.cd_email)
    return contato


@router.delete("/contatos/{cd_contato}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove contato da apólice")
def remover_contato(nr_apolice: str, cd_contato: int, id_usuario: str = "SISTEMA"):
    _get_apolice(nr_apolice)
    lista = _CONTATOS.get(nr_apolice, [])
    contato = next((c for c in lista if c["cd_contato"] == cd_contato), None)
    if not contato:
        raise HTTPException(404, detail=f"Contato {cd_contato} não encontrado.")
    lista.remove(contato)
    _registrar(nr_apolice, "CONTATO_REMOVIDO",
               f"Contato {contato['nm_contato']} removido", id_usuario)


@router.put("/endereco",
            summary="Atualiza endereço da apólice / estipulante")
def atualizar_endereco(nr_apolice: str, payload: EnderecoRequest):
    apolice = _get_apolice(nr_apolice)
    antes = apolice.get("ds_endereco")
    apolice["ds_endereco"] = (
        f"{payload.ds_logradouro}, {payload.nr_numero}"
        + (f" {payload.ds_complemento}" if payload.ds_complemento else "")
        + f" - {payload.nm_bairro} - {payload.nm_cidade}/{payload.sg_estado} - CEP {payload.cd_cep}"
    )
    _registrar(nr_apolice, "ENDERECO_ALTERADO",
               "Endereço da apólice atualizado",
               payload.id_usuario, antes, apolice["ds_endereco"])
    return {"nr_apolice": nr_apolice, "ds_endereco": apolice["ds_endereco"]}


# ══════════════════════════════════════════════════════════════════════════════
# OPERAÇÕES ESPECIAIS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/renovar",
             summary="Renova apólice — gera nova vigência")
def renovar_apolice(nr_apolice: str, payload: RenovacaoRequest):
    from app.api.emissao.proposta import _APOLICES, _APOLICE_SEQ
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(409, detail=f"Apólice {nr_apolice} está {apolice['cd_status']} — não pode ser renovada.")
    if payload.dt_fim_nova_vigencia <= payload.dt_inicio_nova_vigencia:
        raise HTTPException(422, detail="Data fim deve ser maior que data início.")

    # Gera número da nova apólice
    import datetime as _dt
    nr_nova = f"{_dt.datetime.today().year}.APO.R{len(_APOLICES)+1:05d}"

    nova_apolice = {**apolice,
        "nr_apolice":           nr_nova,
        "dt_emissao":           datetime.today().strftime("%Y%m%d"),
        "dt_inicio_vigencia":   payload.dt_inicio_nova_vigencia,
        "dt_fim_vigencia":      payload.dt_fim_nova_vigencia,
        "cd_status":            "AT",
        "nr_apolice_origem":    nr_apolice,
        "ts_emissao":           datetime.utcnow(),
    }
    _APOLICES[nr_nova] = nova_apolice

    # Copia config de faturamento se solicitado
    if payload.fl_manter_config == "S" and nr_apolice in _CONFIG:
        _CONFIG[nr_nova] = {**_CONFIG[nr_apolice], "nr_apolice": nr_nova}

    _registrar(nr_apolice, "RENOVACAO",
               f"Apólice renovada → {nr_nova} ({payload.dt_inicio_nova_vigencia} a {payload.dt_fim_nova_vigencia})",
               payload.id_usuario)

    return {
        "nr_apolice_origem": nr_apolice,
        "nr_apolice_nova":   nr_nova,
        "dt_inicio":         payload.dt_inicio_nova_vigencia,
        "dt_fim":            payload.dt_fim_nova_vigencia,
        "fl_config_copiada": payload.fl_manter_config,
    }


@router.put("/produto",
            summary="Altera produto da apólice (VGC ↔ GLB)")
def alterar_produto(nr_apolice: str, payload: AlteracaoProdutoRequest):
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(409, detail="Apólice não está ativa.")
    antes = apolice["cd_produto"]
    if antes == payload.cd_produto_novo:
        raise HTTPException(409, detail=f"Apólice já é do produto {antes}.")
    apolice["cd_produto"] = payload.cd_produto_novo
    _registrar(nr_apolice, "PRODUTO_ALTERADO",
               f"Produto alterado de {antes} para {payload.cd_produto_novo}",
               payload.id_usuario, antes, payload.cd_produto_novo)
    return {"nr_apolice": nr_apolice,
            "cd_produto_anterior": antes,
            "cd_produto_novo": payload.cd_produto_novo,
            "dt_vigencia": payload.dt_vigencia}


@router.put("/transferir-cnpj",
            summary="Transferência de CNPJ do estipulante")
def transferir_cnpj(nr_apolice: str, payload: TransferenciaCnpjRequest):
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] != "AT":
        raise HTTPException(409, detail="Apólice não está ativa.")
    antes_cnpj = apolice.get("cd_cnpj_estipulante", "N/A")
    antes_nome = apolice.get("nm_estipulante", "N/A")
    apolice["cd_cnpj_estipulante"] = payload.cd_cnpj_novo
    apolice["nm_estipulante"]      = payload.nm_razao_social_novo
    _registrar(nr_apolice, "TRANSF_CNPJ",
               f"CNPJ transferido de {antes_cnpj} ({antes_nome}) "
               f"para {payload.cd_cnpj_novo} ({payload.nm_razao_social_novo})",
               payload.id_usuario,
               f"{antes_cnpj} / {antes_nome}",
               f"{payload.cd_cnpj_novo} / {payload.nm_razao_social_novo}")
    return {
        "nr_apolice":           nr_apolice,
        "cd_cnpj_anterior":     antes_cnpj,
        "nm_razao_anterior":    antes_nome,
        "cd_cnpj_novo":         payload.cd_cnpj_novo,
        "nm_razao_nova":        payload.nm_razao_social_novo,
        "dt_vigencia":          payload.dt_vigencia,
    }


@router.put("/cancelar",
            summary="Cancela a apólice")
def cancelar_apolice(nr_apolice: str, payload: CancelamentoRequest):
    from app.api.emissao.apolice import StatusApoliceEnum
    apolice = _get_apolice(nr_apolice)
    if apolice["cd_status"] == "CA":
        raise HTTPException(409, detail="Apólice já cancelada.")
    apolice["cd_status"]              = "CA"
    apolice["dt_cancelamento"]        = payload.dt_cancelamento
    apolice["ds_motivo_cancelamento"] = f"[{payload.cd_motivo}] {payload.ds_motivo}"
    apolice["id_usuario_cancel"]      = payload.id_usuario
    _registrar(nr_apolice, "CANCELAMENTO",
               f"Apólice cancelada. Motivo: [{payload.cd_motivo}] {payload.ds_motivo}",
               payload.id_usuario,
               "AT", "CA")
    return {
        "nr_apolice":       nr_apolice,
        "cd_status":        "CA",
        "dt_cancelamento":  payload.dt_cancelamento,
        "ds_motivo":        f"[{payload.cd_motivo}] {payload.ds_motivo}",
        "fl_devolucao_premio": payload.fl_devolver_premio,
    }


# ══════════════════════════════════════════════════════════════════════════════
# HISTÓRICO DE ALTERAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/historico",
            response_model=list[HistoricoItem],
            summary="Histórico completo de alterações da apólice")
def historico_apolice(
    nr_apolice: str,
    tp_acao:    Optional[str] = None,
    limit:      int = 50,
):
    _get_apolice(nr_apolice)
    result = _HISTORICO.get(nr_apolice, [])
    if tp_acao:
        result = [h for h in result if h["tp_acao"] == tp_acao]
    return result[-limit:]
