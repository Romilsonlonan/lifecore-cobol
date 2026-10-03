"""
Corretagem — Router
Corretoras, corretores e vínculo com empresas (estipulantes).
Uma empresa pode operar SEM corretora ou ter uma vinculada.

GET    /api/corretagem/corretoras              → lista corretoras
POST   /api/corretagem/corretoras              → cadastra corretora
GET    /api/corretagem/corretoras/{id}         → detalha
PUT    /api/corretagem/corretoras/{id}         → atualiza
PUT    /api/corretagem/corretoras/{id}/status  → ativa/inativa

GET    /api/corretagem/corretores              → lista corretores
POST   /api/corretagem/corretores              → cadastra corretor
GET    /api/corretagem/corretores/{id}         → detalha
PUT    /api/corretagem/corretores/{id}         → atualiza
PUT    /api/corretagem/corretores/{id}/status  → ativa/inativa

GET    /api/corretagem/vinculos                → lista vínculos empresa↔corretora
POST   /api/corretagem/vinculos                → vincula empresa a corretora
DELETE /api/corretagem/vinculos/{id}           → remove vínculo (empresa fica direta)
GET    /api/corretagem/empresas/{id}/corretora → corretora e corretor da empresa
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, EmailStr

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CorretoraNome(BaseModel):
    """Resumo de corretora para listagens."""
    cd_corretora:   int
    nm_razao_social: str
    cd_cnpj:        str
    cd_status:      str


class CorretoraCreate(BaseModel):
    nm_razao_social:    str     = Field(..., max_length=80)
    nm_nome_reduzido:   Optional[str] = Field(None, max_length=30)
    cd_cnpj:            str     = Field(..., min_length=14, max_length=14,
                                   description="CNPJ sem pontuação")
    nr_susep:           str     = Field(..., max_length=10,
                                   description="Código SUSEP da corretora")
    cd_email:           Optional[str] = Field(None, max_length=120)
    nr_telefone:        Optional[str] = Field(None, max_length=20)
    nr_celular:         Optional[str] = Field(None, max_length=20)
    ds_endereco:        Optional[str] = Field(None, max_length=200)
    cd_cep:             Optional[str] = Field(None, max_length=8)
    nm_cidade:          Optional[str] = Field(None, max_length=60)
    sg_estado:          Optional[str] = Field(None, min_length=2, max_length=2)
    ds_site:            Optional[str] = Field(None, max_length=100)
    ds_observacao:      Optional[str] = Field(None, max_length=300)


class CorretoraResponse(CorretoraCreate):
    cd_corretora:   int
    cd_status:      str
    nr_corretores_ativos: int = 0
    dt_inclusao:    str
    ts_inclusao:    datetime

    model_config = {"from_attributes": True}


class CorretorCreate(BaseModel):
    cd_corretora:       int     = Field(..., description="Corretora à qual pertence")
    nm_nome:            str     = Field(..., max_length=80)
    nr_cpf:             str     = Field(..., min_length=11, max_length=11,
                                   description="CPF sem pontuação")
    nr_susep:           str     = Field(..., max_length=10,
                                   description="Código SUSEP individual do corretor")
    cd_email_principal: str     = Field(..., max_length=120,
                                   description="E-mail principal para notificações")
    cd_email_secundario: Optional[str] = Field(None, max_length=120)
    nr_telefone:        Optional[str] = Field(None, max_length=20)
    nr_celular:         Optional[str] = Field(None, max_length=20,
                                   description="WhatsApp preferencial")
    ds_especialidade:   Optional[str] = Field(None, max_length=100,
                                   description="ex: Vida em Grupo, Previdência")
    dt_inicio_vigencia: Optional[str] = Field(None, pattern=r"^\d{8}$")
    dt_fim_vigencia:    Optional[str] = Field(None, pattern=r"^\d{8}$")
    ds_observacao:      Optional[str] = Field(None, max_length=300)


class CorretorResponse(CorretorCreate):
    cd_corretor:        int
    nm_corretora:       Optional[str] = None
    cd_status:          str
    nr_empresas_ativas: int = 0
    dt_inclusao:        str
    ts_inclusao:        datetime

    model_config = {"from_attributes": True}


class VinculoCreate(BaseModel):
    cd_empresa:         int     = Field(..., description="Empresa (estipulante)")
    cd_corretora:       int     = Field(..., description="Corretora responsável")
    cd_corretor:        Optional[int] = Field(None,
                            description="Corretor específico responsável (opcional)")
    pct_comissao:       Optional[float] = Field(None, ge=0, le=100,
                            description="% de comissão da corretora nesta conta")
    dt_inicio:          str     = Field(..., pattern=r"^\d{8}$",
                            description="Início da vigência do vínculo")
    dt_fim:             Optional[str] = Field(None, pattern=r"^\d{8}$")
    ds_observacao:      Optional[str] = Field(None, max_length=200)


class VinculoResponse(VinculoCreate):
    cd_vinculo:         int
    nm_empresa:         Optional[str] = None
    nm_corretora:       Optional[str] = None
    nm_corretor:        Optional[str] = None
    cd_email_corretor:  Optional[str] = None
    nr_celular_corretor: Optional[str] = None
    cd_status:          str
    dt_inclusao:        str
    ts_inclusao:        datetime

    model_config = {"from_attributes": True}


class EmpresaCorretoraSummary(BaseModel):
    """Resumo da corretagem de uma empresa — resposta de /empresas/{id}/corretora."""
    cd_empresa:         int
    nm_empresa:         str
    fl_tem_corretora:   bool
    cd_vinculo:         Optional[int]   = None
    cd_corretora:       Optional[int]   = None
    nm_corretora:       Optional[str]   = None
    nr_susep_corretora: Optional[str]   = None
    cd_email_corretora: Optional[str]   = None
    nr_telefone_corretora: Optional[str] = None
    cd_corretor:        Optional[int]   = None
    nm_corretor:        Optional[str]   = None
    nr_susep_corretor:  Optional[str]   = None
    cd_email_corretor:  Optional[str]   = None
    nr_celular_corretor: Optional[str]  = None
    ds_especialidade:   Optional[str]   = None
    pct_comissao:       Optional[float] = None
    dt_inicio_vinculo:  Optional[str]   = None


class AlterarStatusRequest(BaseModel):
    motivo: Optional[str] = Field(None, max_length=200)


# ── Stores em memória ─────────────────────────────────────────────────────────

_CORRETORAS: dict[int, dict] = {
    1: {
        "cd_corretora":     1,
        "nm_razao_social":  "Corretora Exemplo Ltda",
        "nm_nome_reduzido": "CORRETORA EX",
        "cd_cnpj":          "12345678000199",
        "nr_susep":         "J1234",
        "cd_email":         "contato@corretora.com.br",
        "nr_telefone":      "1133445566",
        "nr_celular":       "11987654321",
        "ds_endereco":      None,
        "cd_cep":           None,
        "nm_cidade":        "São Paulo",
        "sg_estado":        "SP",
        "ds_site":          "https://corretora.com.br",
        "ds_observacao":    None,
        "cd_status":        "AT",
        "dt_inclusao":      "20240101",
        "ts_inclusao":      datetime(2024, 1, 1, 8, 0, 0),
    }
}
_NEXT_CORRETORA = 2

_CORRETORES: dict[int, dict] = {
    1: {
        "cd_corretor":          1,
        "cd_corretora":         1,
        "nm_nome":              "João Corretor Silva",
        "nr_cpf":               "98765432100",
        "nr_susep":             "J12345",
        "cd_email_principal":   "joao@corretora.com.br",
        "cd_email_secundario":  "joao.silva@gmail.com",
        "nr_telefone":          "1133445567",
        "nr_celular":           "11976543210",
        "ds_especialidade":     "Vida em Grupo, VGC",
        "dt_inicio_vigencia":   "20240101",
        "dt_fim_vigencia":      None,
        "ds_observacao":        None,
        "cd_status":            "AT",
        "dt_inclusao":          "20240101",
        "ts_inclusao":          datetime(2024, 1, 1, 8, 0, 0),
    }
}
_NEXT_CORRETOR = 2

_VINCULOS: dict[int, dict] = {}
_NEXT_VINCULO = 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _corretora_nome(cd: int) -> Optional[str]:
    c = _CORRETORAS.get(cd)
    return c["nm_razao_social"] if c else None


def _corretor_nome(cd: int) -> Optional[str]:
    c = _CORRETORES.get(cd)
    return c["nm_nome"] if c else None


def _empresa_nome(cd: int) -> Optional[str]:
    # Importação tardia para evitar circular
    from app.api.cadastros.empresa import _DB
    e = _DB.get(cd)
    return e["nm_razao_social"] if e else None


def _vinculo_ativo_empresa(cd_empresa: int) -> Optional[dict]:
    for v in _VINCULOS.values():
        if v["cd_empresa"] == cd_empresa and v["cd_status"] == "AT":
            return v
    return None


# ── CORRETORAS ────────────────────────────────────────────────────────────────

@router.get("/corretoras", response_model=list[CorretoraResponse],
            summary="Lista corretoras")
def listar_corretoras(cd_status: Optional[str] = None):
    result = list(_CORRETORAS.values())
    if cd_status:
        result = [c for c in result if c["cd_status"] == cd_status]
    for c in result:
        c["nr_corretores_ativos"] = sum(
            1 for cr in _CORRETORES.values()
            if cr["cd_corretora"] == c["cd_corretora"] and cr["cd_status"] == "AT"
        )
    return result


@router.post("/corretoras", response_model=CorretoraResponse,
             status_code=status.HTTP_201_CREATED, summary="Cadastra corretora")
def criar_corretora(payload: CorretoraCreate):
    global _NEXT_CORRETORA
    for c in _CORRETORAS.values():
        if c["cd_cnpj"] == payload.cd_cnpj:
            raise HTTPException(409, detail=f"CNPJ {payload.cd_cnpj} já cadastrado.")
        if c["nr_susep"] == payload.nr_susep:
            raise HTTPException(409, detail=f"SUSEP {payload.nr_susep} já cadastrado.")
    corretora = {
        "cd_corretora":         _NEXT_CORRETORA,
        **payload.model_dump(),
        "cd_status":            "AT",
        "nr_corretores_ativos": 0,
        "dt_inclusao":          datetime.today().strftime("%Y%m%d"),
        "ts_inclusao":          datetime.utcnow(),
    }
    _CORRETORAS[_NEXT_CORRETORA] = corretora
    _NEXT_CORRETORA += 1
    return corretora


@router.get("/corretoras/{cd_corretora}", response_model=CorretoraResponse,
            summary="Detalha corretora")
def detalhar_corretora(cd_corretora: int):
    c = _CORRETORAS.get(cd_corretora)
    if not c:
        raise HTTPException(404, detail=f"Corretora {cd_corretora} não encontrada.")
    c["nr_corretores_ativos"] = sum(
        1 for cr in _CORRETORES.values()
        if cr["cd_corretora"] == cd_corretora and cr["cd_status"] == "AT"
    )
    return c


@router.put("/corretoras/{cd_corretora}", response_model=CorretoraResponse,
            summary="Atualiza dados da corretora")
def atualizar_corretora(cd_corretora: int, payload: CorretoraCreate):
    c = _CORRETORAS.get(cd_corretora)
    if not c:
        raise HTTPException(404, detail=f"Corretora {cd_corretora} não encontrada.")
    c.update(payload.model_dump())
    return c


@router.put("/corretoras/{cd_corretora}/status", response_model=CorretoraResponse,
            summary="Ativa / Inativa corretora")
def alterar_status_corretora(
    cd_corretora: int,
    cd_status: str,
    payload: AlterarStatusRequest,
):
    if cd_status not in ("AT", "IN"):
        raise HTTPException(422, detail="Status inválido. Use AT ou IN.")
    c = _CORRETORAS.get(cd_corretora)
    if not c:
        raise HTTPException(404, detail=f"Corretora {cd_corretora} não encontrada.")
    c["cd_status"] = cd_status
    return c


# ── CORRETORES ────────────────────────────────────────────────────────────────

@router.get("/corretores", response_model=list[CorretorResponse],
            summary="Lista corretores")
def listar_corretores(
    cd_corretora: Optional[int] = None,
    cd_status:    Optional[str] = None,
):
    result = list(_CORRETORES.values())
    if cd_corretora:
        result = [c for c in result if c["cd_corretora"] == cd_corretora]
    if cd_status:
        result = [c for c in result if c["cd_status"] == cd_status]
    return [_enrich_corretor(c) for c in result]


@router.post("/corretores", response_model=CorretorResponse,
             status_code=status.HTTP_201_CREATED, summary="Cadastra corretor")
def criar_corretor(payload: CorretorCreate):
    global _NEXT_CORRETOR
    if payload.cd_corretora not in _CORRETORAS:
        raise HTTPException(404, detail=f"Corretora {payload.cd_corretora} não encontrada.")
    for c in _CORRETORES.values():
        if c["nr_cpf"] == payload.nr_cpf:
            raise HTTPException(409, detail=f"CPF {payload.nr_cpf} já cadastrado.")
        if c["nr_susep"] == payload.nr_susep:
            raise HTTPException(409, detail=f"SUSEP {payload.nr_susep} já cadastrado.")
    corretor = {
        "cd_corretor":          _NEXT_CORRETOR,
        **payload.model_dump(),
        "cd_status":            "AT",
        "dt_inclusao":          datetime.today().strftime("%Y%m%d"),
        "ts_inclusao":          datetime.utcnow(),
    }
    _CORRETORES[_NEXT_CORRETOR] = corretor
    _NEXT_CORRETOR += 1
    return _enrich_corretor(corretor)


@router.get("/corretores/{cd_corretor}", response_model=CorretorResponse,
            summary="Detalha corretor")
def detalhar_corretor(cd_corretor: int):
    c = _CORRETORES.get(cd_corretor)
    if not c:
        raise HTTPException(404, detail=f"Corretor {cd_corretor} não encontrado.")
    return _enrich_corretor(c)


@router.put("/corretores/{cd_corretor}", response_model=CorretorResponse,
            summary="Atualiza dados do corretor")
def atualizar_corretor(cd_corretor: int, payload: CorretorCreate):
    c = _CORRETORES.get(cd_corretor)
    if not c:
        raise HTTPException(404, detail=f"Corretor {cd_corretor} não encontrado.")
    c.update(payload.model_dump())
    return _enrich_corretor(c)


@router.put("/corretores/{cd_corretor}/status", response_model=CorretorResponse,
            summary="Ativa / Inativa corretor")
def alterar_status_corretor(
    cd_corretor: int,
    cd_status:   str,
    payload:     AlterarStatusRequest,
):
    if cd_status not in ("AT", "IN"):
        raise HTTPException(422, detail="Status inválido. Use AT ou IN.")
    c = _CORRETORES.get(cd_corretor)
    if not c:
        raise HTTPException(404, detail=f"Corretor {cd_corretor} não encontrado.")
    c["cd_status"] = cd_status
    return _enrich_corretor(c)


def _enrich_corretor(c: dict) -> dict:
    return {
        **c,
        "nm_corretora":       _corretora_nome(c["cd_corretora"]),
        "nr_empresas_ativas": sum(
            1 for v in _VINCULOS.values()
            if v.get("cd_corretor") == c["cd_corretor"] and v["cd_status"] == "AT"
        ),
    }


# ── VÍNCULOS empresa ↔ corretora ──────────────────────────────────────────────

@router.get("/vinculos", response_model=list[VinculoResponse],
            summary="Lista vínculos empresa ↔ corretora")
def listar_vinculos(
    cd_empresa:   Optional[int] = None,
    cd_corretora: Optional[int] = None,
    cd_status:    Optional[str] = None,
):
    result = list(_VINCULOS.values())
    if cd_empresa:
        result = [v for v in result if v["cd_empresa"] == cd_empresa]
    if cd_corretora:
        result = [v for v in result if v["cd_corretora"] == cd_corretora]
    if cd_status:
        result = [v for v in result if v["cd_status"] == cd_status]
    return [_enrich_vinculo(v) for v in result]


@router.post("/vinculos", response_model=VinculoResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Vincula empresa a uma corretora")
def criar_vinculo(payload: VinculoCreate):
    global _NEXT_VINCULO

    # Verifica se corretora existe e está ativa
    corretora = _CORRETORAS.get(payload.cd_corretora)
    if not corretora:
        raise HTTPException(404, detail=f"Corretora {payload.cd_corretora} não encontrada.")
    if corretora["cd_status"] != "AT":
        raise HTTPException(409, detail="Corretora inativa.")

    # Verifica se corretor pertence à corretora
    if payload.cd_corretor:
        corretor = _CORRETORES.get(payload.cd_corretor)
        if not corretor:
            raise HTTPException(404, detail=f"Corretor {payload.cd_corretor} não encontrado.")
        if corretor["cd_corretora"] != payload.cd_corretora:
            raise HTTPException(
                409,
                detail=f"Corretor {payload.cd_corretor} não pertence à corretora {payload.cd_corretora}.",
            )

    # Encerra vínculo ativo anterior da empresa (se houver)
    vinculo_anterior = _vinculo_ativo_empresa(payload.cd_empresa)
    if vinculo_anterior:
        vinculo_anterior["cd_status"]    = "EN"   # Encerrado
        vinculo_anterior["dt_encerrado"] = datetime.today().strftime("%Y%m%d")

    vinculo = {
        "cd_vinculo":           _NEXT_VINCULO,
        **payload.model_dump(),
        "cd_status":            "AT",
        "dt_inclusao":          datetime.today().strftime("%Y%m%d"),
        "ts_inclusao":          datetime.utcnow(),
    }
    _VINCULOS[_NEXT_VINCULO] = vinculo
    _NEXT_VINCULO += 1
    return _enrich_vinculo(vinculo)


@router.delete("/vinculos/{cd_vinculo}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove vínculo — empresa fica sem corretora")
def remover_vinculo(cd_vinculo: int):
    v = _VINCULOS.get(cd_vinculo)
    if not v:
        raise HTTPException(404, detail=f"Vínculo {cd_vinculo} não encontrado.")
    v["cd_status"]    = "EN"   # Encerrado (mantém histórico)
    v["dt_encerrado"] = datetime.today().strftime("%Y%m%d")


# ── CONSULTA rápida por empresa ───────────────────────────────────────────────

@router.get("/empresas/{cd_empresa}/corretora",
            response_model=EmpresaCorretoraSummary,
            summary="Corretora e corretor vinculados à empresa")
def empresa_corretora(cd_empresa: int):
    """
    Retorna um resumo completo da corretagem de uma empresa.
    Se a empresa não tiver corretora vinculada, fl_tem_corretora = false.
    Ideal para o front-end carregar o painel da empresa.
    """
    nm_empresa = _empresa_nome(cd_empresa)
    if not nm_empresa:
        raise HTTPException(404, detail=f"Empresa {cd_empresa} não encontrada.")

    vinculo = _vinculo_ativo_empresa(cd_empresa)

    if not vinculo:
        return EmpresaCorretoraSummary(
            cd_empresa=cd_empresa,
            nm_empresa=nm_empresa,
            fl_tem_corretora=False,
        )

    corretora = _CORRETORAS.get(vinculo["cd_corretora"])
    corretor  = _CORRETORES.get(vinculo.get("cd_corretor")) if vinculo.get("cd_corretor") else None

    return EmpresaCorretoraSummary(
        cd_empresa=cd_empresa,
        nm_empresa=nm_empresa,
        fl_tem_corretora=True,
        cd_vinculo=vinculo["cd_vinculo"],
        cd_corretora=corretora["cd_corretora"]      if corretora else None,
        nm_corretora=corretora["nm_razao_social"]   if corretora else None,
        nr_susep_corretora=corretora["nr_susep"]    if corretora else None,
        cd_email_corretora=corretora["cd_email"]    if corretora else None,
        nr_telefone_corretora=corretora["nr_telefone"] if corretora else None,
        cd_corretor=corretor["cd_corretor"]         if corretor else None,
        nm_corretor=corretor["nm_nome"]             if corretor else None,
        nr_susep_corretor=corretor["nr_susep"]      if corretor else None,
        cd_email_corretor=corretor["cd_email_principal"] if corretor else None,
        nr_celular_corretor=corretor["nr_celular"]  if corretor else None,
        ds_especialidade=corretor["ds_especialidade"] if corretor else None,
        pct_comissao=vinculo.get("pct_comissao"),
        dt_inicio_vinculo=vinculo["dt_inicio"],
    )


def _enrich_vinculo(v: dict) -> dict:
    corretor = _CORRETORES.get(v.get("cd_corretor")) if v.get("cd_corretor") else None
    return {
        **v,
        "nm_empresa":           _empresa_nome(v["cd_empresa"]),
        "nm_corretora":         _corretora_nome(v["cd_corretora"]),
        "nm_corretor":          corretor["nm_nome"]             if corretor else None,
        "cd_email_corretor":    corretor["cd_email_principal"]  if corretor else None,
        "nr_celular_corretor":  corretor["nr_celular"]          if corretor else None,
    }
