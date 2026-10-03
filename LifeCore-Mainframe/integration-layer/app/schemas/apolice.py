"""
Schemas Pydantic — Importação de Apólices e Jobs Batch.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── Enums espelhando os 88-levels dos copybooks ────────────────────────────

class ProdutoEnum(str, Enum):
    VGC = "VGC"
    GLB = "GLB"


class TipoCapitalEnum(str, Enum):
    FIXO             = "F"
    ESCALONADO       = "E"
    MULT_SALARIAL    = "M"
    POR_FAIXA        = "B"
    PARAMETRICO      = "P"


class FormaPagamentoEnum(str, Enum):
    BOLETO = "BO"
    CARTAO = "CC"
    DEBITO = "DB"


class PeriodicidadeEnum(str, Enum):
    MENSAL = "MN"
    ANUAL  = "AN"
    UNICO  = "UN"


class StatusJobEnum(str, Enum):
    PENDENTE    = "PENDENTE"
    EXECUTANDO  = "EXECUTANDO"
    CONCLUIDO   = "CONCLUIDO"
    ERRO        = "ERRO"


# ── Linha de apólice vinda do corretor (CSV / XLSX) ─────────────────────────

class ApoliceInput(BaseModel):
    """Uma linha do arquivo enviado pelo corretor."""
    numero_apolice:      str  = Field(..., max_length=12,  description="Número da apólice")
    produto:             ProdutoEnum
    cnpj_estipulante:    str  = Field(..., min_length=14, max_length=14)
    cpf_segurado:        str  = Field(..., min_length=11, max_length=11)
    nome_segurado:       str  = Field(..., max_length=40)
    vigencia_ini:        str  = Field(..., pattern=r"^\d{8}$", description="AAAAMMDD")
    vigencia_fim:        str  = Field(..., pattern=r"^\d{8}$")
    tipo_capital:        TipoCapitalEnum
    capital_segurado:    float = Field(..., ge=0)
    salario_base:        Optional[float] = Field(None, ge=0)
    fator_multiplicador: Optional[float] = Field(None, ge=0)
    premio_liquido:      float = Field(..., ge=0)
    premio_bruto:        float = Field(..., ge=0)
    iof:                 Optional[float] = Field(None, ge=0)
    forma_pagamento:     FormaPagamentoEnum
    periodicidade:       PeriodicidadeEnum


# ── Resposta de importação ──────────────────────────────────────────────────

class ImportacaoResponse(BaseModel):
    job_id:             str
    status:             StatusJobEnum
    arquivo_gerado:     str           = Field(..., description="Caminho do flat file criado")
    total_registros:    int
    mensagem:           str
    timestamp:          datetime      = Field(default_factory=datetime.utcnow)


# ── Status de job batch ─────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id:             str
    status:             StatusJobEnum
    return_code:        Optional[int] = None
    etapa_atual:        Optional[str] = None
    inicio:             Optional[datetime] = None
    fim:                Optional[datetime] = None
    log_resumo:         Optional[str] = None


# ── Resultado de apolices processadas ──────────────────────────────────────

class ApoliceResultado(BaseModel):
    numero_apolice:     str
    status:             str
    capital_calculado:  Optional[float] = None
    erro:               Optional[str]   = None


class ResultadoImportacaoResponse(BaseModel):
    job_id:             str
    total_validos:      int
    total_erros:        int
    apolices:           list[ApoliceResultado]
