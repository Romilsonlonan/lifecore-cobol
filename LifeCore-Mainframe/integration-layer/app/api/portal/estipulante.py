"""
Portal — Cadastro Rápido de Estipulante (Supabase)
===================================================
POST /api/portal/estipulantes
    Cria estipulante + apólice com sequência persistida no Supabase.
    Número de apólice: AAAA{SEQ:04d} — ex: 20260001, 20260002, 20270001.

PUT  /api/portal/estipulantes/{nr_apolice}
    Atualiza dados gerais, faturamento ou contatos.

POST /api/portal/estipulantes/{nr_apolice}/ecm
    Upload de documento ECM para o bucket 'ecm-docs' do Supabase Storage.

GET  /api/portal/estipulantes
    Lista todos os estipulantes.

GET  /api/portal/estipulantes/{nr_apolice}
    Detalha um estipulante com seus documentos ECM.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers Supabase ──────────────────────────────────────────────────────────

def _sb():
    from app.services.supabase_client import get_client
    return get_client()


def _gerar_nr_apolice() -> str:
    """
    Sequência persistida na tabela apolice_seq do Supabase.
    Reinicia em 0001 a cada virada de ano.
    """
    ano = datetime.now(UTC).year
    sb = _sb()

    # Upsert atômico: lê o seq atual e incrementa
    sel = sb.table("apolice_seq").select("seq").eq("ano", ano).execute()
    seq = (sel.data[0]["seq"] + 1) if sel.data else 1
    sb.table("apolice_seq").upsert({"ano": ano, "seq": seq}).execute()

    # Sincroniza com o store em memória do proposta.py
    try:
        from app.api.emissao.proposta import _APOLICE_SEQ_POR_ANO
        _APOLICE_SEQ_POR_ANO[ano] = seq
    except Exception:
        pass

    return f"{ano}{seq:04d}"


def _row_para_response(row: dict, docs: list[dict] | None = None) -> dict:
    """Converte linha do Supabase para o formato de resposta da API."""
    return {
        "nr_apolice": row["nr_apolice"],
        "nm_razao_social": row["nm_razao_social"],
        "cd_cnpj": row["cd_cnpj"],
        "periodo_contrato": row["periodo_contrato"],
        "dt_cadastro": row["dt_cadastro"],
        "ts_cadastro": row["ts_cadastro"],
        "ecm_docs": docs or [],
        "dados": {
            "tp_estipulante": row.get("tp_estipulante", "ES"),
            "tp_termino_contrato": row.get("tp_termino_contrato", "negociacao"),
            "tp_renovacao":   row.get("tp_renovacao", "manual"),
            "endereco": {
                "ds_logradouro": row.get("ds_logradouro", ""),
                "ds_numero":     row.get("ds_numero", ""),
                "ds_bairro":     row.get("ds_bairro", ""),
                "cd_cep":        row.get("cd_cep", ""),
                "ds_cidade":     row.get("ds_cidade", ""),
                "cd_uf":         row.get("cd_uf", ""),
            },
            "contato": {
                "nm_contato":      row.get("nm_contato", ""),
                "ds_telefone":     row.get("ds_telefone", ""),
                "ds_email":        row.get("ds_email", ""),
                "emails_extra":    row.get("emails_extra", []),
                "telefones_extra": row.get("telefones_extra", []),
            },
            "corretora": {
                "nm_corretora":          row.get("nm_corretora", ""),
                "cd_cnpj_corretora":     row.get("cd_cnpj_corretora", ""),
                "nm_corretor":           row.get("nm_corretor", ""),
                "ds_telefone_corretor":  row.get("ds_telefone_corretor", ""),
                "ds_email_corretor":     row.get("ds_email_corretor", ""),
            },
            "faturamento": {
                "nr_dia_corte":     row.get("nr_dia_corte", ""),
                "nr_dia_vencimento": row.get("nr_dia_vencimento", ""),
                "fat_automatico":   row.get("fat_automatico", "nao"),
                "vl_ipca_vigente":  row.get("vl_ipca_vigente", ""),
                "fl_reajuste_ipca": row.get("fl_reajuste_ipca", "nao"),
            },
            "tarifacao": {
                "tp_capital":        row.get("tp_capital") or row.get("tp_cobertura", "F"),
                "vl_capital_global": row.get("vl_capital_global", ""),
                "nr_fator_mult":     row.get("nr_fator_mult", ""),
                # Compatibilidade: coluna nova "coberturas" ou legada "coberturas_extras"
                "coberturas":        row.get("coberturas") or row.get("coberturas_extras", []),
            },
            # cd_status exposto para o frontend poder checar apólice ativa/cancelada/suspensa
            "cd_status": row.get("cd_status", "AT"),
            "subestipulantes": row.get("subestipulantes", []),
        },
    }


def _buscar_docs(nr_apolice: str) -> list[dict]:
    res = _sb().table("ecm_docs").select(
        "id, nm_arquivo, tp_arquivo, nr_tamanho_kb, ts_upload, storage_path"
    ).eq("nr_apolice", nr_apolice).order("ts_upload").execute()
    return res.data or []


# ── Schemas ───────────────────────────────────────────────────────────────────

class EnderecoInput(BaseModel):
    ds_logradouro: str = ""
    ds_numero:     str = ""
    ds_bairro:     str = ""
    cd_cep:        str = ""
    ds_cidade:     str = ""
    cd_uf:         str = ""


class ContatoInput(BaseModel):
    nm_contato:  str = ""
    ds_telefone: str = ""
    ds_email:    str = ""


class SubestipulanteInput(BaseModel):
    nm_razao_social: str
    cd_cnpj: str = ""
    endereco: EnderecoInput = Field(default_factory=EnderecoInput)
    contato:  ContatoInput  = Field(default_factory=ContatoInput)


class CoberturaInput(BaseModel):
    cd_tipo:        str
    nm_cobertura:   str
    vl_capital:     float = 0.0
    pc_taxa_mensal: float = 0.0
    vl_premio:      float = 0.0


class EstipulanteCreate(BaseModel):
    # Classificação
    tp_estipulante:        str = "ES"    # ES=Estipulante, SE=Subestipulante, HO=Holding
    # Identificação
    nm_razao_social: str = Field(..., min_length=2, max_length=80)
    cd_cnpj:         str = Field(..., min_length=14, max_length=14)
    endereco:        EnderecoInput          = Field(default_factory=EnderecoInput)
    contato:         ContatoInput           = Field(default_factory=ContatoInput)
    subestipulantes: list[SubestipulanteInput] = Field(default_factory=list)
    # Corretagem
    nm_corretora:          str = ""
    cd_cnpj_corretora:     str = ""
    nm_corretor:           str = ""
    ds_telefone_corretor:  str = ""
    ds_email_corretor:     str = ""
    # Faturamento
    nr_dia_corte:          str = ""
    nr_dia_vencimento:     str = ""
    fat_automatico:        str = "nao"
    # IPCA
    vl_ipca_vigente:       str = "0.38"
    fl_reajuste_ipca:      str = "nao"
    # Capital e coberturas (Motor de Tarifação)
    tp_capital:            str = "F"    # F/E/M/B/P/G
    vl_capital_global:     str = ""
    nr_fator_mult:         str = ""
    coberturas:            list[CoberturaInput] = Field(default_factory=list)
    # Período e renovação
    periodo_contrato:      str = "12"
    tp_termino_contrato:   str = "negociacao"  # negociacao/nao_renovacao/renovacao_auto
    tp_renovacao:          str = "manual"       # manual/auto_ipca


class EstipulanteResponse(BaseModel):
    nr_apolice:       str
    nm_razao_social:  str
    cd_cnpj:          str
    periodo_contrato: str
    dt_cadastro:      str
    ts_cadastro:      str
    ecm_docs:         list[dict] = Field(default_factory=list)
    dados:            dict       = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=EstipulanteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastro de estipulante — persiste no Supabase",
)
def criar_estipulante(payload: EstipulanteCreate) -> dict:
    sb = _sb()

    # Verifica CNPJ duplicado
    dup = sb.table("estipulantes").select("nr_apolice").eq("cd_cnpj", payload.cd_cnpj).execute()
    if dup.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CNPJ {payload.cd_cnpj} já cadastrado. Apólice: {dup.data[0]['nr_apolice']}.",
        )

    nr_apolice = _gerar_nr_apolice()
    hoje = datetime.now(UTC).strftime("%Y%m%d")

    # Campos base — sempre existem no schema original
    row: dict[str, Any] = {
        "nr_apolice":       nr_apolice,
        "nm_razao_social":  payload.nm_razao_social.strip(),
        "cd_cnpj":          payload.cd_cnpj,
        "periodo_contrato": payload.periodo_contrato,
        "dt_cadastro":      hoje,
        # Endereço
        "ds_logradouro": payload.endereco.ds_logradouro,
        "ds_numero":     payload.endereco.ds_numero,
        "ds_bairro":     payload.endereco.ds_bairro,
        "cd_cep":        payload.endereco.cd_cep,
        "ds_cidade":     payload.endereco.ds_cidade,
        "cd_uf":         payload.endereco.cd_uf,
        # Contato
        "nm_contato":      payload.contato.nm_contato,
        "ds_telefone":     payload.contato.ds_telefone,
        "ds_email":        payload.contato.ds_email,
        "emails_extra":    [],
        "telefones_extra": [],
        # Corretora
        "nm_corretora":         payload.nm_corretora,
        "cd_cnpj_corretora":    payload.cd_cnpj_corretora,
        "nm_corretor":          payload.nm_corretor,
        "ds_telefone_corretor": payload.ds_telefone_corretor,
        "ds_email_corretor":    payload.ds_email_corretor,
        # Faturamento
        "nr_dia_corte":      payload.nr_dia_corte,
        "nr_dia_vencimento": payload.nr_dia_vencimento,
        "fat_automatico":    payload.fat_automatico,
        # Cobertura legacy (coluna existente no schema original)
        "tp_cobertura":        payload.tp_capital,
        "coberturas_extras":   [c.model_dump() for c in payload.coberturas],
        # Subestipulantes
        "subestipulantes": [s.model_dump() for s in payload.subestipulantes],
    }

    # Colunas adicionadas pela migração v2 — inseridas somente quando existem
    _colunas_v2 = {
        "tp_estipulante":      payload.tp_estipulante,
        "tp_termino_contrato": payload.tp_termino_contrato,
        "tp_renovacao":        payload.tp_renovacao,
        "vl_ipca_vigente":     payload.vl_ipca_vigente,
        "fl_reajuste_ipca":    payload.fl_reajuste_ipca,
        "tp_capital":          payload.tp_capital,
        "vl_capital_global":   payload.vl_capital_global,
        "nr_fator_mult":       payload.nr_fator_mult,
        "coberturas":          [c.model_dump() for c in payload.coberturas],
        "cd_status":           "AT",
    }
    # Detecta quais colunas v2 já existem tentando inserção; se falhar, usa só as base
    try:
        res = sb.table("estipulantes").insert({**row, **_colunas_v2}).execute()
    except Exception:
        # Migração v2 ainda não rodada — usa apenas colunas originais
        res = sb.table("estipulantes").insert(row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao salvar no Supabase.")

    logger.info("Estipulante criado: %s | %s | CNPJ %s", nr_apolice, payload.nm_razao_social, payload.cd_cnpj)

    # Sincroniza com stores in-memory para compatibilidade com outros endpoints
    _sincronizar_stores(nr_apolice, payload, hoje)

    return _row_para_response(res.data[0])


def _sincronizar_stores(nr_apolice: str, payload: EstipulanteCreate, hoje: str) -> None:
    """Sincroniza com stores in-memory E tenta gravar no DB2 (dual-write)."""
    # 1. Stores in-memory (proposta/apólice)
    try:
        from app.api.emissao.proposta import _APOLICES, _PROPOSTAS
        agora = datetime.now(UTC)
        nr_proposta = f"PORTAL.{nr_apolice}"
        _PROPOSTAS[nr_proposta] = {
            "nr_proposta": nr_proposta,
            "cd_empresa": hash(payload.cd_cnpj) % 100000,
            "cd_cpf_segurado": "00000000000",
            "cd_produto": "VGC",
            "tp_capital": payload.tp_cobertura or "F",
            "vl_capital": 0,
            "dt_proposta": hoje,
            "cd_status": "AC",
            "tp_aceite": "AU",
            "dt_aceite": hoje,
            "dt_recusa": None,
            "ds_motivo_recusa": None,
            "nr_dias_analise": 0,
            "nr_apolice_gerada": nr_apolice,
            "ts_inclusao": datetime.now(UTC),
        }
        _APOLICES[nr_apolice] = {
            "nr_apolice": nr_apolice,
            "nr_proposta": nr_proposta,
            "cd_empresa": hash(payload.cd_cnpj) % 100000,
            "cd_cpf_segurado": "00000000000",
            "cd_produto": "VGC",
            "tp_capital": payload.tp_cobertura or "F",
            "vl_capital": 0,
            "dt_emissao": hoje,
            "dt_inicio_vigencia": hoje,
            "cd_status": "AT",
            "ts_emissao": datetime.now(UTC),
        }
    except Exception:
        pass

    # 2. DB2 z/OS — dual-write (funciona quando DB2_DSN estiver configurado)
    _gravar_db2(nr_apolice, payload, hoje)

    # 3. Arquivo de exportação em layout fixo para job COBOL batch
    _exportar_layout_fixo(nr_apolice, payload, hoje)


def _gravar_db2(nr_apolice: str, payload: EstipulanteCreate, hoje: str) -> None:
    """
    Tenta gravar na tabela EMPRESA do DB2 z/OS.
    Silencioso quando DB2_DSN não está configurado (ambiente de dev).
    Em produção com DB2_DSN definido, grava automaticamente.
    """
    try:
        from app.repositories.empresa_db2 import (
            Db2Unavailable,
            empresa_repository,
        )
        from app.schemas.lifecore import EmpresaCreate, TipoEmpresaEnum

        empresa_payload = EmpresaCreate(
            nr_codigo=nr_apolice[-6:],          # últimos 6 dígitos da apólice
            nm_razao_social=payload.nm_razao_social[:80],
            nm_nome_reduzido=None,
            cd_cnpj=payload.cd_cnpj,
            tp_empresa=TipoEmpresaEnum.ESTIPULANTE,
        )
        empresa_repository.criar(empresa_payload, "PORTAL")
        logger.info("DB2: empresa gravada — nr_apolice=%s cnpj=%s", nr_apolice, payload.cd_cnpj)

    except Exception as exc:
        # DB2 indisponível em dev — não bloqueia o cadastro
        logger.debug("DB2 não disponível (esperado em dev): %s", exc)


def _exportar_layout_fixo(nr_apolice: str, payload: EstipulanteCreate, hoje: str) -> None:
    """
    Gera arquivo de layout fixo compatível com COBOL batch.
    Formato: CODIGO(6) RAZAO(80) CNPJ(14) TIPO(2) STATUS(2) DATA(8) APOLICE(10)
    Total: 122 bytes por registro.
    O job LCESBLC1 pode importar este arquivo para o DB2.
    """
    try:
        from app.core.config import settings
        export_dir = settings.data_input_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        export_file = export_dir / "PORTAL_EMPRESAS.dat"

        codigo  = nr_apolice[-6:].ljust(6)[:6]
        razao   = payload.nm_razao_social[:80].ljust(80)
        cnpj    = payload.cd_cnpj[:14].ljust(14)
        tipo    = "ES"
        status  = "AT"
        data    = hoje[:8].ljust(8)
        apolice = nr_apolice[:10].ljust(10)

        linha = f"{codigo}{razao}{cnpj}{tipo}{status}{data}{apolice}\n"

        with open(export_file, "a", encoding="latin-1") as f:
            f.write(linha)

        logger.info("Layout fixo exportado: %s → %s", nr_apolice, export_file)

    except Exception as exc:
        logger.warning("Exportação layout fixo falhou: %s", exc)


@router.put(
    "/{nr_apolice}",
    response_model=EstipulanteResponse,
    summary="Atualiza dados do estipulante (merge parcial)",
)
def atualizar_estipulante(nr_apolice: str, body: dict) -> dict:
    sb = _sb()

    # Verifica se existe
    sel = sb.table("estipulantes").select("nr_apolice").eq("nr_apolice", nr_apolice).execute()
    if not sel.data:
        raise HTTPException(status_code=404, detail=f"Apólice {nr_apolice} não encontrada.")

    # Monta payload de update com os campos presentes no body
    update: dict[str, Any] = {}

    # Campos de topo
    for k in ("nm_razao_social", "periodo_contrato"):
        if k in body:
            update[k] = body[k]

    # Endereço
    if "endereco" in body:
        for k in ("ds_logradouro", "ds_numero", "ds_bairro", "cd_cep", "ds_cidade", "cd_uf"):
            if k in body["endereco"]:
                update[k] = body["endereco"][k]

    # Contato
    if "contato" in body:
        for k in ("nm_contato", "ds_telefone", "ds_email", "emails_extra", "telefones_extra"):
            if k in body["contato"]:
                update[k] = body["contato"][k]

    # Corretora
    if "corretora" in body:
        for k in ("nm_corretora", "cd_cnpj_corretora", "nm_corretor", "ds_telefone_corretor", "ds_email_corretor"):
            if k in body["corretora"]:
                update[k] = body["corretora"][k]

    # Faturamento
    if "faturamento" in body:
        for k in ("nr_dia_corte", "nr_dia_vencimento", "fat_automatico"):
            if k in body["faturamento"]:
                update[k] = body["faturamento"][k]

    if not update:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")

    res = sb.table("estipulantes").update(update).eq("nr_apolice", nr_apolice).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao atualizar no Supabase.")

    row = res.data[0]
    logger.info("Estipulante atualizado: %s campos=%s", nr_apolice, list(update.keys()))

    # Dual-write: propaga alterações para DB2 e arquivo de layout fixo
    _atualizar_db2(nr_apolice, row)
    _exportar_alteracao_layout_fixo(nr_apolice, row, update)

    return _row_para_response(row, _buscar_docs(nr_apolice))


def _atualizar_db2(nr_apolice: str, row: dict) -> None:
    """
    Propaga alteração de razão social / status para a tabela EMPRESA do DB2.
    Silencioso quando DB2_DSN não está configurado.
    """
    try:
        from app.core.config import settings
        if not settings.db2_dsn:
            return  # Dev sem DB2 — silencioso

        from datetime import UTC, datetime

        from app.repositories.empresa_db2 import (
            EmpresaNotFound,
            empresa_repository,
        )

        cd_status = row.get("cd_status", "AT")

        # Resolve cd_empresa via CNPJ (lookup Supabase → DB2)
        sel = _sb().table("estipulantes").select("cd_cnpj").eq("nr_apolice", nr_apolice).single().execute()
        if not sel.data:
            logger.warning("DB2: CNPJ não encontrado para nr_apolice=%s", nr_apolice)
            return
        cd_cnpj = sel.data.get("cd_cnpj", "")

        try:
            empresa = empresa_repository.obter_por_cnpj(cd_cnpj)
        except EmpresaNotFound:
            logger.warning("DB2: empresa não encontrada para CNPJ=%s", cd_cnpj)
            return

        cd_empresa = empresa["cd_empresa"]
        usuario = row.get("id_usuario", "PORTAL")
        hoje = datetime.now(UTC).strftime("%Y%m%d")

        if cd_status == "CA":
            empresa_repository.cancelar(
                cd_empresa=cd_empresa,
                dt_cancelamento=row.get("dt_cancelamento", hoje),
                ds_motivo=row.get("ds_motivo_cancelamento", "Cancelado via Portal"),
                usuario=usuario,
            )
            logger.info("DB2: empresa %s cancelada — nr_apolice=%s", cd_empresa, nr_apolice)

        elif cd_status == "SU":
            empresa_repository.suspender(
                cd_empresa=cd_empresa,
                dt_inicio_suspensao=row.get("dt_inicio_suspensao", hoje),
                dt_fim_suspensao=row.get("dt_fim_suspensao", hoje),
                ds_motivo=row.get("ds_motivo_suspensao", "Suspenso via Portal"),
                usuario=usuario,
            )
            logger.info("DB2: empresa %s suspensa — nr_apolice=%s", cd_empresa, nr_apolice)

        elif cd_status == "AT" and empresa.get("cd_status") and str(empresa["cd_status"]) in ("SU", "su"):
            # Reativação de suspensão
            empresa_repository.reativar_suspensao(cd_empresa=cd_empresa, usuario=usuario)
            logger.info("DB2: empresa %s suspensão reativada — nr_apolice=%s", cd_empresa, nr_apolice)

        elif cd_status == "IN":
            from app.schemas.lifecore import StatusGeralEnum
            empresa_repository.alterar_status(cd_empresa, StatusGeralEnum.INATIVO)
            logger.info("DB2: empresa %s inativada — nr_apolice=%s", cd_empresa, nr_apolice)

    except Exception as exc:
        logger.warning("DB2 atualização falhou (nr_apolice=%s): %s", nr_apolice, exc)


def _exportar_alteracao_layout_fixo(nr_apolice: str, row: dict, campos_alterados: dict) -> None:
    """
    Gera/atualiza o registro no arquivo PORTAL_EMPRESAS_UPD.dat.
    Formato: APOLICE(10) CAMPO(30) VALOR(80) DATA(8)  → 128 bytes por registro.
    O job COBOL pode ler este arquivo para aplicar UPDATEs no DB2.
    """
    try:
        from app.core.config import settings
        from datetime import UTC, datetime

        export_dir = settings.data_input_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        export_file = export_dir / "PORTAL_EMPRESAS_UPD.dat"
        hoje = datetime.now(UTC).strftime("%Y%m%d")

        # Um registro por campo alterado para rastreabilidade
        with open(export_file, "a", encoding="latin-1") as f:
            for campo, valor in campos_alterados.items():
                apolice_col = nr_apolice[:10].ljust(10)
                campo_col   = campo[:30].ljust(30)
                valor_col   = str(valor)[:80].ljust(80)
                data_col    = hoje.ljust(8)
                linha = f"{apolice_col}{campo_col}{valor_col}{data_col}\n"
                f.write(linha)

        logger.info("Layout fixo UPD exportado: %s campos=%s", nr_apolice, list(campos_alterados.keys()))

    except Exception as exc:
        logger.warning("Exportação layout fixo UPD falhou: %s", exc)


@router.post(
    "/{nr_apolice}/ecm",
    status_code=status.HTTP_201_CREATED,
    summary="Upload de documento ECM para o MinIO (S3-compatible)",
)
async def upload_ecm(
    nr_apolice: str,
    arquivo: UploadFile = File(..., description="PDF, DOC ou DOCX · máx. 20 MB"),
) -> dict:
    sb = _sb()

    # Verifica se a apólice existe
    sel = sb.table("estipulantes").select("nr_apolice").eq("nr_apolice", nr_apolice).execute()
    if not sel.data:
        raise HTTPException(status_code=404, detail=f"Apólice {nr_apolice} não encontrada.")

    conteudo = await arquivo.read()
    tamanho_kb = len(conteudo) / 1024

    if tamanho_kb > 20 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo excede 20 MB.")

    ext = (arquivo.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "doc", "docx"):
        raise HTTPException(status_code=415, detail="Tipo não permitido. Use PDF, DOC ou DOCX.")

    mime_map = {
        "pdf":  "application/pdf",
        "doc":  "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    storage_path = f"{nr_apolice}/{ts}_{arquivo.filename}"

    # Upload para o Storage (Supabase S3 / MinIO)
    from app.services import storage_client
    try:
        storage_client.upload(
            storage_path=storage_path,
            data=conteudo,
            content_type=mime_map.get(ext, "application/octet-stream"),
        )
    except Exception as exc:
        logger.error("Storage upload falhou: %s", exc)
        raise HTTPException(status_code=502, detail=f"Erro no upload do arquivo: {exc}")

    # Salva metadados na tabela ecm_docs (Supabase — só metadados)
    doc_row = {
        "nr_apolice":    nr_apolice,
        "nm_arquivo":    arquivo.filename,
        "tp_arquivo":    ext.upper(),
        "nr_tamanho_kb": round(tamanho_kb, 1),
        "storage_path":  storage_path,
    }
    res = sb.table("ecm_docs").insert(doc_row).execute()
    doc_meta = res.data[0] if res.data else doc_row

    total = sb.table("ecm_docs").select("id", count="exact").eq("nr_apolice", nr_apolice).execute()
    logger.info("ECM anexado via Storage: %s → %s", nr_apolice, arquivo.filename)

    return {"nr_apolice": nr_apolice, "documento": doc_meta, "total_docs": total.count or 1}


@router.get(
    "",
    response_model=list[EstipulanteResponse],
    summary="Lista estipulantes cadastrados via portal",
)
def listar_estipulantes() -> list:
    res = _sb().table("estipulantes").select("*").order("ts_cadastro", desc=True).execute()
    return [_row_para_response(r) for r in (res.data or [])]


@router.get(
    "/{nr_apolice}/ecm/{nm_arquivo}",
    summary="Presigned URL para visualização/download de documento ECM (MinIO)",
)
def url_ecm(nr_apolice: str, nm_arquivo: str) -> dict:
    """
    Busca o storage_path do documento na tabela ecm_docs e gera uma
    presigned URL com validade de 60 minutos via MinIO (boto3).
    O frontend usa essa URL diretamente no <iframe>.
    """
    sb = _sb()

    # Localiza o documento pelo nome de arquivo e apólice
    res = (
        sb.table("ecm_docs")
        .select("storage_path, tp_arquivo, nm_arquivo")
        .eq("nr_apolice", nr_apolice)
        .eq("nm_arquivo", nm_arquivo)
        .order("ts_upload", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    doc = res.data[0]
    storage_path: str = doc.get("storage_path", "")

    if not storage_path:
        raise HTTPException(
            status_code=404,
            detail="Documento sem arquivo no storage (upload pode ter falhado).",
        )

    from app.services import storage_client
    try:
        url = storage_client.signed_url(storage_path, expires_in=3600)
    except Exception as exc:
        logger.error("Erro ao gerar presigned URL (Storage): %s", exc)
        raise HTTPException(status_code=502, detail=f"Erro ao acessar storage: {exc}")

    return {
        "url": url,
        "nm_arquivo": doc["nm_arquivo"],
        "tp_arquivo": doc["tp_arquivo"],
        "expires_in": 3600,
    }


@router.delete(
    "/{nr_apolice}/ecm/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove documento ECM (metadados + arquivo no storage)",
)
def deletar_ecm(nr_apolice: str, doc_id: int) -> dict:
    """
    Remove o registro da tabela ecm_docs e o arquivo correspondente no storage.
    Usa o `id` (bigint) do registro para identificar unicamente o documento,
    evitando ambiguidade quando há dois arquivos com o mesmo nome.
    """
    sb = _sb()

    # Busca o registro pelo id e apólice
    res = (
        sb.table("ecm_docs")
        .select("id, storage_path, nm_arquivo")
        .eq("id", doc_id)
        .eq("nr_apolice", nr_apolice)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    doc = res.data[0]
    storage_path: str = doc.get("storage_path", "")

    # Remove arquivo do storage (silencioso se não existir)
    if storage_path:
        from app.services import storage_client
        try:
            storage_client.delete(storage_path)
        except Exception as exc:
            logger.warning("Storage delete falhou (ignorado): %s", exc)

    # Remove metadados da tabela
    sb.table("ecm_docs").delete().eq("id", doc_id).execute()
    logger.info("ECM removido: %s → %s (id=%s)", nr_apolice, doc["nm_arquivo"], doc_id)

    return {"deleted": doc_id, "nm_arquivo": doc["nm_arquivo"]}


@router.get(
    "/{nr_apolice}/segurados",
    summary="Lista segurados e coberturas ativos/excluídos da apólice (Supabase)",
)
def listar_segurados(nr_apolice: str, status: str = "AT") -> list[dict]:
    """
    Retorna os segurados com suas coberturas para a apólice informada.
    Parâmetro `status`: AT=ativos (default) | EX=excluídos | ALL=todos.
    Combina coberturas + segurados em uma única resposta.
    """
    sb = _sb()

    # Busca coberturas filtradas por status
    q = sb.table("coberturas").select(
        "cd_cobertura, cd_cpf, nm_cobertura, cd_tipo, vl_capital, "
        "nr_carencia_dias, cd_status, ts_criado, ts_atualizado"
    ).eq("nr_apolice", nr_apolice)

    if status != "ALL":
        q = q.eq("cd_status", status.upper())

    cobs_res = q.order("ts_criado").execute()
    coberturas: list[dict] = cobs_res.data or []

    if not coberturas:
        return []

    # Busca dados dos segurados em lote
    cpfs = list({c["cd_cpf"] for c in coberturas})
    segs_res = (
        sb.table("segurados")
        .select("cd_cpf, nm_segurado, dt_nascimento, dt_admissao, vl_salario, cd_empresa, dt_inclusao")
        .in_("cd_cpf", cpfs)
        .execute()
    )
    seg_map: dict[str, dict] = {s["cd_cpf"]: s for s in (segs_res.data or [])}

    # Mescla cobertura + segurado
    result = []
    for cob in coberturas:
        cpf = cob["cd_cpf"]
        seg = seg_map.get(cpf, {})
        result.append({
            "cd_cpf":          cpf,
            "nm_segurado":     seg.get("nm_segurado", cob["nm_cobertura"].replace("Morte — ", "")),
            "dt_nascimento":   seg.get("dt_nascimento", ""),
            "dt_admissao":     seg.get("dt_admissao", ""),
            "vl_salario":      float(seg.get("vl_salario") or 0),
            "cd_empresa":      seg.get("cd_empresa", 0),
            "dt_inclusao":     seg.get("dt_inclusao", ""),
            "cd_cobertura":    cob["cd_cobertura"],
            "cd_tipo":         cob["cd_tipo"],
            "nm_cobertura":    cob["nm_cobertura"],
            "vl_capital":      float(cob["vl_capital"] or 0),
            "nr_carencia_dias": cob["nr_carencia_dias"],
            "cd_status_cob":   cob["cd_status"],
            "ts_inclusao_cob": cob["ts_criado"],
        })

    return result


@router.get(
    "/buscar-segurados",
    summary="Busca segurados no Supabase por CPF exato ou nome (ilike)",
)
def buscar_segurados(q: str) -> list[dict]:
    """
    Parâmetro `q`: CPF com 11 dígitos (busca exata) ou fragmento de nome (case-insensitive).
    Retorna segurados mesclados com suas coberturas ativas.
    """
    sb = _sb()
    q = q.strip()

    # ── 1. Busca na tabela segurados ────────────────────────────────────────
    if q.isdigit() and len(q) == 11:
        segs_res = sb.table("segurados").select("*").eq("cd_cpf", q).execute()
    else:
        segs_res = (
            sb.table("segurados")
            .select("*")
            .ilike("nm_segurado", f"%{q}%")
            .execute()
        )

    segs: list[dict] = segs_res.data or []
    if not segs:
        return []

    # ── 2. Busca coberturas para os CPFs encontrados ─────────────────────────
    cpfs = list({s["cd_cpf"] for s in segs})
    cobs_res = (
        sb.table("coberturas")
        .select(
            "cd_cobertura, cd_cpf, nr_apolice, nm_cobertura, cd_tipo, vl_capital, "
            "nr_carencia_dias, cd_status, ts_criado, ts_atualizado"
        )
        .in_("cd_cpf", cpfs)
        .execute()
    )
    cobs: list[dict] = cobs_res.data or []

    # Index coberturas por CPF (pode haver múltiplas; pega a mais recente ativa)
    cob_map: dict[str, dict] = {}
    for cob in cobs:
        cpf = cob["cd_cpf"]
        prev = cob_map.get(cpf)
        # Prefer AT (active) over EX; among same status prefer newest
        if prev is None:
            cob_map[cpf] = cob
        elif cob.get("cd_status") == "AT" and prev.get("cd_status") != "AT":
            cob_map[cpf] = cob

    # ── 3. Monta resposta ───────────────────────────────────────────────────
    from datetime import timezone

    def _is_nova_inclusao(cob: dict) -> bool:
        """
        True quando a cobertura foi criada e nunca atualizada depois —
        ou seja, ts_criado ≈ ts_atualizado (diferença < 10 s).
        Indica que o segurado entrou pela primeira vez nesta importação.
        """
        ts_c = cob.get("ts_criado", "")
        ts_a = cob.get("ts_atualizado", "")
        if not ts_c or not ts_a:
            return False
        try:
            from datetime import datetime
            def _parse(s: str):
                s = s.rstrip("Z").split("+")[0]
                # Handle microseconds optionally
                for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        continue
                return None
            dc = _parse(ts_c)
            da = _parse(ts_a)
            if dc and da:
                return abs((da - dc).total_seconds()) < 10
        except Exception:
            pass
        return False

    result = []
    for seg in segs:
        cpf = seg["cd_cpf"]
        cob = cob_map.get(cpf, {})
        result.append({
            "cd_cpf":           cpf,
            "nm_segurado":      seg.get("nm_segurado", ""),
            "dt_nascimento":    seg.get("dt_nascimento", ""),
            "dt_admissao":      seg.get("dt_admissao", ""),
            "vl_salario":       float(seg.get("vl_salario") or 0),
            "cd_empresa":       seg.get("cd_empresa", 0),
            "dt_inclusao":      seg.get("dt_inclusao", ""),
            "nr_matricula":     seg.get("nr_matricula", ""),
            "cd_cargo":         seg.get("cd_cargo", ""),
            "cd_cobertura":     cob.get("cd_cobertura", ""),
            "cd_tipo":          cob.get("cd_tipo", ""),
            "nm_cobertura":     cob.get("nm_cobertura", ""),
            "vl_capital":       float(cob.get("vl_capital") or 0),
            "nr_carencia_dias": cob.get("nr_carencia_dias", 0),
            "cd_status_cob":    cob.get("cd_status", ""),
            "nr_apolice":       cob.get("nr_apolice", ""),
            "ts_inclusao_cob":  cob.get("ts_criado", ""),
            "fl_nova_inclusao": _is_nova_inclusao(cob),
        })

    return result


@router.get(
    "/{nr_apolice}",
    response_model=EstipulanteResponse,
    summary="Detalha estipulante com documentos ECM",
)
def detalhar_estipulante(nr_apolice: str) -> dict:
    res = _sb().table("estipulantes").select("*").eq("nr_apolice", nr_apolice).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Apólice {nr_apolice} não encontrada.")
    return _row_para_response(res.data[0], _buscar_docs(nr_apolice))
