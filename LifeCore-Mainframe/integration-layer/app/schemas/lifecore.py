"""
Schemas Pydantic v2 — Módulos completos do LifeCore-Mainframe
Baseado na análise do I4Pro (Prudential) + extensões futuras.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, date

# ── Enums globais ─────────────────────────────────────────────────

class TipoEmpresaEnum(str, Enum):
    SEGURADORA  = "SE"
    ESTIPULANTE = "ES"
    CORRETORA   = "CO"
    CONGENERE   = "CN"
    RESSEGURADOR = "RE"

class TipoPessoaEnum(str, Enum):
    FISICA   = "PF"
    JURIDICA = "PJ"

class StatusGeralEnum(str, Enum):
    ATIVO   = "AT"
    INATIVO = "IN"

class StatusPropostaEnum(str, Enum):
    EM_ANALISE       = "AN"
    ACEITACAO_AUTO   = "AA"
    PENDENTE_DOC     = "PD"
    ACEITA           = "AC"
    RECUSADA         = "RC"
    CANCELADA        = "CA"

class StatusApoliceEnum(str, Enum):
    ATIVA     = "AT"
    CANCELADA = "CA"
    SUSPENSA  = "SU"
    EXPIRADA  = "EX"

class StatusEndossoEnum(str, Enum):
    PENDENTE   = "PE"
    PROCESSADO = "PR"
    REJEITADO  = "RJ"
    CANCELADO  = "CA"

class TipoEndossoEnum(str, Enum):
    INCLUSAO       = "INC"   # inclusão de segurado
    EXCLUSAO       = "EXC"   # exclusão de segurado
    ALTERACAO_CAP  = "CAP"   # alteração de capital
    ALTERACAO_SAL  = "SAL"   # alteração de salário base
    SUSPENSAO      = "SUS"   # suspensão de cobertura
    REATIVACAO     = "REA"   # reativação após inadimplência

class StatusCoberturaEnum(str, Enum):
    ATIVA          = "AT"   # coberto normalmente
    CARENCIA       = "CA"   # em carência (não indeniza)
    SEM_COBERTURA  = "SC"   # >3 meses sem pagamento, sem retroativo
    SUSPENSA       = "SU"   # suspensa por solicitação
    CANCELADA      = "CL"   # cancelada definitivamente

class FormaCobrancaEnum(str, Enum):
    BOLETO  = "BO"
    CARTAO  = "CC"
    DEBITO  = "DB"
    PIX     = "PI"

class PeriodicidadeEnum(str, Enum):
    MENSAL      = "MN"
    BIMESTRAL   = "BM"
    TRIMESTRAL  = "TR"
    SEMESTRAL   = "SM"
    ANUAL       = "AN"

class StatusSinistroEnum(str, Enum):
    ABERTO     = "AB"
    EM_ANALISE = "AN"
    PAGO       = "PG"
    ENCERRADO  = "EN"
    RECUSADO   = "RC"

class TipoEventoSinistroEnum(str, Enum):
    MORTE       = "MORT"
    INVALIDEZ   = "INVA"
    DIT         = "DIT"
    VIAGEM      = "VIAG"
    DESP_MED    = "DMH"

class ModuloAuditoriaEnum(str, Enum):
    EMISSAO    = "Emissão"
    SINISTRO   = "Sinistro"
    ACEITACAO  = "Aceitação"
    CADASTRO   = "Cadastro"
    COBRANCA   = "Cobrança"
    ROTINA     = "Rotina"
    ECM        = "ECM"
    COSSEGURO  = "Cosseguro"
    IMPRESSAO  = "Impressão"

# ── Empresa ───────────────────────────────────────────────────────

class EmpresaBase(BaseModel):
    nr_codigo:              str     = Field(..., max_length=6)
    nm_razao_social:        str     = Field(..., max_length=80)
    nm_nome_reduzido:       Optional[str] = Field(None, max_length=30)
    cd_cnpj:                str     = Field(..., min_length=14, max_length=14)
    tp_empresa:             TipoEmpresaEnum
    nr_susep:               Optional[str] = Field(None, max_length=10)
    vl_capital_vinculado:   Optional[float] = None
    vl_capital_subscrito:   Optional[float] = None
    vl_aceite_cobranca:     Optional[float] = None

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaResponse(EmpresaBase):
    cd_empresa:     int
    cd_status:      StatusGeralEnum
    dt_inclusao:    str
    ts_inclusao:    datetime

    class Config:
        from_attributes = True

# ── Congênere ─────────────────────────────────────────────────────

class CongenereBase(BaseModel):
    nr_susep:       str     = Field(..., max_length=10)
    nm_congenere:   str     = Field(..., max_length=80)
    tp_pessoa:      TipoPessoaEnum
    cd_empresa:     Optional[int] = None
    cd_cnpj_cpf:    Optional[str] = Field(None, max_length=14)

class CongenereCreate(CongenereBase):
    pass

class CongenereResponse(CongenereBase):
    cd_congenere:   int
    cd_status:      StatusGeralEnum
    ts_inclusao:    datetime

    class Config:
        from_attributes = True

# ── Proposta ──────────────────────────────────────────────────────

class PropostaCreate(BaseModel):
    nr_proposta:        str     = Field(..., max_length=20, description="ex: 2026.PROP.007109")
    cd_empresa:         int
    cd_cpf_segurado:    str     = Field(..., min_length=11, max_length=11)
    cd_produto:         str     = Field(..., pattern=r'^(VGC|GLB)$')
    tp_capital:         str     = Field(..., pattern=r'^[FEMBP]$')
    vl_capital:         float   = Field(..., ge=0)
    vl_salario_base:    Optional[float] = None
    nr_fator_mult:      Optional[float] = None
    vl_premio_liquido:  Optional[float] = None
    vl_premio_bruto:    Optional[float] = None
    dt_proposta:        str     = Field(..., pattern=r'^\d{8}$')

class PropostaResponse(PropostaCreate):
    cd_status:          StatusPropostaEnum
    tp_aceite:          Optional[str] = None
    dt_aceite:          Optional[str] = None
    dt_recusa:          Optional[str] = None
    ds_motivo_recusa:   Optional[str] = None
    nr_dias_analise:    int = 15
    nr_apolice_gerada:  Optional[str] = None
    ts_inclusao:        datetime

    model_config = {"from_attributes": True}

class AceitePropostaRequest(BaseModel):
    nr_proposta:        str
    tp_aceite:          str     = Field(..., pattern=r'^(AU|MA)$',
                                  description="AU=Automático, MA=Manual")
    id_usuario:         str     = Field(..., max_length=8)
    observacao:         Optional[str] = None

class RecusaPropostaRequest(BaseModel):
    nr_proposta:        str
    cd_motivo:          str     = Field(..., max_length=4)
    ds_motivo:          str     = Field(..., max_length=100)
    id_usuario:         str     = Field(..., max_length=8)

# ── Sinistro ──────────────────────────────────────────────────────

class SinistroCreate(BaseModel):
    nr_sinistro:        str     = Field(..., max_length=20, description="ex: 2026.SIN.008420")
    nr_apolice:         str     = Field(..., max_length=20)
    cd_cpf_segurado:    str     = Field(..., min_length=11, max_length=11)
    cd_empresa:         int
    cd_tipo_evento:     TipoEventoSinistroEnum
    nm_tipo_evento:     Optional[str] = None
    dt_evento:          str     = Field(..., pattern=r'^\d{8}$')
    dt_abertura:        str     = Field(..., pattern=r'^\d{8}$')
    vl_capital_averbado: Optional[float] = None
    vl_indenizacao:     Optional[float] = None
    ds_observacao:      Optional[str] = Field(None, max_length=200)
    id_usuario_incl:    str     = Field(..., max_length=8)

class SinistroResponse(SinistroCreate):
    cd_status:          StatusSinistroEnum
    vl_pago:            float = 0
    dt_encerramento:    Optional[str] = None
    ts_inclusao:        datetime

    class Config:
        from_attributes = True

# ── Parâmetros ────────────────────────────────────────────────────

class ParametroInterfaceResponse(BaseModel):
    cd_parametro:   int
    cd_empresa:     int
    cd_codigo:      str
    ds_descricao:   str
    vl_valor:       str
    tp_parametro:   str
    fl_ativo:       str

    class Config:
        from_attributes = True

class ParametroRotinaResponse(BaseModel):
    cd_empresa:                 int
    fl_apenas_dias_uteis:       str
    nr_dias_aceitacao_auto:     int
    cd_status_aceitacao:        str
    ds_motivo_aceit_auto:       Optional[str]
    nr_dias_recusa_legal:       int
    nr_dias_recusa_auto:        int
    cd_status_recusa_auto:      str
    ds_motivo_recusa_auto:      Optional[str]
    tp_periodo_xml:             Optional[str]

    class Config:
        from_attributes = True

# ── ECM ───────────────────────────────────────────────────────────

class DocECMResponse(BaseModel):
    cd_doc_ecm:     int
    nm_grupo:       str
    nm_tipo:        str
    nr_ref:         Optional[str]
    nm_arquivo:     str
    ds_observacao:  Optional[str]
    dt_gravacao:    str
    hr_gravacao:    Optional[str]
    id_usuario_incl: str
    fl_selecionado: str

    class Config:
        from_attributes = True

# ── Controle Impressão ────────────────────────────────────────────

class ControleImpressaoResponse(BaseModel):
    cd_controle:            int
    cd_empresa:             int
    nm_modulo:              str
    dt_movimento_contabil:  str
    nr_pendentes:           int
    nr_gerados:             int
    nr_nao_gerados:         int
    fl_fechado:             str = "N"

    model_config = {"from_attributes": True}

# ── Auditoria ─────────────────────────────────────────────────────

class AuditoriaAcaoResponse(BaseModel):
    cd_auditoria:   int
    id_usuario:     str
    dt_hora_acao:   datetime
    nm_modulo:      ModuloAuditoriaEnum
    nm_acao:        str
    nr_referencia:  Optional[str]
    ds_detalhe:     Optional[str]

    class Config:
        from_attributes = True

# ── Faturamento / Endosso ─────────────────────────────────────────

class TaxaIPCAVigente(BaseModel):
    """Taxa IPCA vigente por competência."""
    cd_competencia:     str     = Field(..., pattern=r'^\d{6}$', description="AAAAMM ex: 202601")
    vl_taxa_ipca:       float   = Field(..., description="Taxa mensal %, ex: 0.52")
    vl_taxa_acumulada:  float   = Field(..., description="Acumulado 12 meses %, ex: 4.83")
    dt_divulgacao:      str     = Field(..., pattern=r'^\d{8}$')
    ds_fonte:           str     = "IBGE/IPCA"
    fl_vigente:         bool    = True

class TaxaIPCAResponse(TaxaIPCAVigente):
    cd_taxa: int

    model_config = {"from_attributes": True}


class EndossoSeguradorRequest(BaseModel):
    """Inclusão ou alteração de um segurado via endosso."""
    cd_cpf_segurado:    str     = Field(..., min_length=11, max_length=11)
    nm_segurado:        str     = Field(..., max_length=80)
    tp_endosso:         TipoEndossoEnum
    dt_inicio_vigencia: str     = Field(..., pattern=r'^\d{8}$', description="AAAAMMDD")
    vl_capital:         Optional[float]  = Field(None, ge=0)
    vl_salario_base:    Optional[float]  = Field(None, ge=0)
    nr_fator_mult:      Optional[float]  = Field(None, ge=0)
    cd_motivo:          Optional[str]    = Field(None, max_length=4)
    ds_observacao:      Optional[str]    = Field(None, max_length=200)
    id_usuario:         str              = Field(..., max_length=20)


class EndossoResponse(EndossoSeguradorRequest):
    nr_endosso:         str
    nr_apolice:         str
    cd_status:          StatusEndossoEnum
    vl_capital_calculado: Optional[float]  = None
    vl_premio_calculado:  Optional[float]  = None
    ts_inclusao:        datetime

    model_config = {"from_attributes": True}


class FaturaItemSeguro(BaseModel):
    """Linha de segurado na fatura (endosso faturado)."""
    cd_cpf_segurado:    str
    nm_segurado:        str
    vl_capital_coberto: float
    vl_premio_bruto:    float
    vl_premio_liquido:  float
    vl_reajuste_ipca:   float   = 0.0
    cd_status_cobertura: StatusCoberturaEnum
    dt_inicio_cobertura: str
    dt_fim_cobertura:   Optional[str] = None
    fl_revalidado:      bool    = False
    ds_observacao:      Optional[str] = None


class FaturaApoliceCreate(BaseModel):
    """Geração de fatura por competência."""
    nr_apolice:         str     = Field(..., max_length=20)
    cd_competencia:     str     = Field(..., pattern=r'^\d{6}$', description="AAAAMM")
    dt_vencimento:      str     = Field(..., pattern=r'^\d{8}$')
    forma_cobranca:     FormaCobrancaEnum
    id_usuario:         str     = Field(..., max_length=20)


class FaturaApoliceResponse(BaseModel):
    nr_fatura:          str
    nr_apolice:         str
    cd_empresa:         int
    cd_competencia:     str
    dt_emissao:         str
    dt_vencimento:      str
    forma_cobranca:     FormaCobrancaEnum
    vl_total_bruto:     float
    vl_total_liquido:   float
    vl_reajuste_ipca:   float
    nr_segurados:       int
    itens:              List[FaturaItemSeguro]
    cd_status:          str     = "EM_ABERTO"
    ts_geracao:         datetime

    model_config = {"from_attributes": True}


# ── Coberturas e Revalidação ──────────────────────────────────────

class CoberturaSeguro(BaseModel):
    """Cobertura individual de um segurado em uma apólice."""
    cd_cpf_segurado:    str
    nm_segurado:        str
    dt_nascimento:      Optional[str]   = None
    dt_admissao:        Optional[str]   = None
    dt_inicio_cobertura: str
    dt_ultimo_pagamento: Optional[str]  = None
    nr_meses_inadimplente: int          = 0
    cd_status_cobertura: StatusCoberturaEnum
    fl_em_carencia:     bool            = False
    nr_dias_carencia:   int             = 0
    # Valores de capital
    vl_capital_base:    float
    vl_capital_atual:   float           = Field(..., description="Após IPCA e escalonamento")
    vl_reajuste_ipca:   float           = 0.0
    vl_salario_base:    Optional[float] = None
    nr_fator_mult:      Optional[float] = None
    # Prêmio
    vl_premio_bruto:    float
    vl_premio_liquido:  float
    vl_taxa_premio:     float           = Field(..., description="Taxa ‰ do capital")
    # Revalidação (regra de inadimplência)
    fl_revalidado:      bool            = False
    dt_revalidacao:     Optional[str]   = None
    ds_status_detalhado: str            = ""


class RevalidacaoRequest(BaseModel):
    """Revalidação manual de cobertura de segurado."""
    cd_cpf_segurado:    str     = Field(..., min_length=11, max_length=11)
    dt_reativacao:      str     = Field(..., pattern=r'^\d{8}$')
    fl_cobrar_retroativo: bool  = Field(False, description="Sempre False — regra: sem retroativo")
    id_usuario:         str     = Field(..., max_length=20)
    ds_justificativa:   str     = Field(..., max_length=200)


class RevalidacaoResponse(BaseModel):
    nr_apolice:         str
    cd_cpf_segurado:    str
    nm_segurado:        str
    cd_status_anterior: StatusCoberturaEnum
    cd_status_novo:     StatusCoberturaEnum
    nr_meses_inadimplente: int
    fl_cobertura_retroativa: bool   = False
    vl_premio_devido:   float       = 0.0
    ds_mensagem:        str
    ts_revalidacao:     datetime

    model_config = {"from_attributes": True}


# ── Consulta Detalhada de Apólice ─────────────────────────────────

class DetalheApoliceCompleto(BaseModel):
    """Visão consolidada: apólice + config + coberturas + faturas recentes."""
    # Identificação
    nr_apolice:         str
    nr_proposta:        str
    cd_empresa:         int
    nm_empresa:         Optional[str]   = None
    cd_produto:         str
    nm_produto:         str
    cd_status:          StatusApoliceEnum
    dt_emissao:         str
    dt_inicio_vigencia: str
    dt_fim_vigencia:    Optional[str]   = None
    dt_cancelamento:    Optional[str]   = None
    ds_motivo_cancel:   Optional[str]   = None
    # Capital e prêmio
    tp_capital:         str
    vl_capital_base:    float
    vl_capital_atual:   float
    vl_premio_bruto:    Optional[float] = None
    vl_premio_liquido:  Optional[float] = None
    # Config faturamento
    periodicidade:      Optional[PeriodicidadeEnum]   = None
    forma_cobranca:     Optional[FormaCobrancaEnum]   = None
    dia_vencimento:     Optional[int]   = None
    # Totalizadores
    nr_segurados_ativos:    int         = 0
    nr_segurados_sem_cobertura: int     = 0
    vl_folha_total:         float       = 0.0
    vl_reajuste_ipca_acum:  float       = 0.0
    # Última taxa IPCA aplicada
    taxa_ipca_vigente:      Optional[TaxaIPCAResponse] = None
    # Coberturas individuais
    coberturas:             List[CoberturaSeguro]       = []
    # Histórico de faturas (resumo)
    ultimas_faturas:        List[dict]                  = []
    # Timestamps
    ts_consulta:            datetime

    model_config = {"from_attributes": True}

# ── Painel Interativo (KPIs + Pipeline + Últimas Ações) ───────────

class KPICard(BaseModel):
    titulo:         str
    valor:          int | float
    variacao_pct:   float   = Field(description="% vs mês anterior, positivo=alta")
    tendencia:      str     = Field(description="ALTA / BAIXA / ESTAVEL")

class PipelineAceitacao(BaseModel):
    em_analise:          int
    em_analise_pct:      float
    aceitacao_auto:      int
    aceitacao_auto_pct:  float
    pendente_doc:        int
    pendente_doc_pct:    float
    recusadas:           int
    recusadas_pct:       float

class UltimaAcao(BaseModel):
    hora:           str
    usuario:        str
    descricao:      str
    modulo:         str
    nr_referencia:  Optional[str] = None

class PainelResponse(BaseModel):
    kpis:               list[KPICard]
    pipeline_aceitacao: PipelineAceitacao
    ultimas_acoes:      list[UltimaAcao]
    impressoes_hoje:    int
    data_hora:          datetime

    class Config:
        from_attributes = True
