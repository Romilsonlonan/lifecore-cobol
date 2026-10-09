"""
Endpoint — Importação de Vidas via Planilha

POST /api/emissao/apolices/{nr_apolice}/importar-vidas
  Lê o arquivo .xlsx/.csv OU uma planilha Google Sheets no formato:
    Sub | Modulos | Nomes | Data de Nascimento | CPF |
    Data de Admissao | Salario | Cargos
  e persiste SEGURADO + COBERTURA no DB2 e no Supabase,
  disponível em tempo real para consulta via CICS (transação LCVD).

  Lógica de reconciliação automática (a partir da 2ª importação):
    • Segurados presentes na planilha → incluídos/atualizados normalmente.
    • Segurados ATIVOS na apólice que NÃO aparecem na nova planilha →
      cobertura marcada como 'EX' (excluída) com dt_saida = competência atual.
      O segurado não é removido do cadastro, apenas a cobertura é desativada.

Parâmetros de query:
  cd_empresa      int    — CD_EMPRESA do estipulante principal
  cd_sub1         int    — CD_EMPRESA do substipulante Sub=1
  cd_sub2         int    — CD_EMPRESA do substipulante Sub=2
  dry_run         bool   — apenas valida sem gravar (default: false)
  gsheet_url      str    — URL do Google Sheets (alternativa ao arquivo)
"""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.importacao_vidas import (
    ResultadoImportacaoVidas,
    gravar_vidas_db2,
    parse_planilha_vidas,
)
from app.repositories.empresa_db2 import Db2Unavailable, Db2OperationFailed

logger = logging.getLogger(__name__)
router = APIRouter()
_MAX_BYTES = 10 * 1024 * 1024


def _gsheet_url_to_csv(url: str) -> str:
    """
    Converte qualquer URL do Google Sheets para a URL de exportação CSV.
    Aceita:
      - https://docs.google.com/spreadsheets/d/{ID}/edit#gid={GID}
      - https://docs.google.com/spreadsheets/d/{ID}/edit?gid={GID}
      - https://docs.google.com/spreadsheets/d/{ID}/pub?...
    """
    m = re.search(r"/spreadsheets/d/([^/]+)", url)
    if not m:
        raise ValueError("URL do Google Sheets inválida — não foi possível extrair o ID.")
    sheet_id = m.group(1)

    # Extrai gid (aba específica) se presente
    gid_match = re.search(r"[#?&]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


async def _baixar_gsheet(url: str) -> tuple[str, bytes]:
    """Faz download do Google Sheets como CSV. Retorna (filename, content)."""
    csv_url = _gsheet_url_to_csv(url)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(csv_url)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=422,
                    detail=f"Não foi possível baixar a planilha Google Sheets "
                           f"(HTTP {resp.status_code}). Verifique se está compartilhada publicamente.",
                )
            content = resp.content
            if len(content) > _MAX_BYTES:
                raise HTTPException(status_code=413, detail="Planilha excede 10 MB.")
            return "gsheet.csv", content
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao conectar ao Google Sheets: {exc}",
        ) from exc


@router.post(
    "/{nr_apolice}/importar-vidas",
    summary="Importa planilha de vidas e grava no DB2 + Supabase (SEGURADO + COBERTURA)",
    tags=["Movimentação · Importação"],
)
async def importar_vidas(
    nr_apolice: str,
    arquivo: UploadFile = File(None, description="Planilha .xlsx ou .csv (opcional se gsheet_url fornecida)"),
    cd_empresa: int = Query(10, description="CD_EMPRESA do estipulante principal"),
    cd_sub1: int = Query(11, description="CD_EMPRESA do substipulante Sub=1"),
    cd_sub2: int = Query(12, description="CD_EMPRESA do substipulante Sub=2"),
    id_usuario: str = Query("CORRETOR", description="Identificador do operador"),
    dry_run: bool = Query(False, description="Se true, só valida sem gravar"),
    gsheet_url: str = Query(None, description="URL do Google Sheets (alternativa ao arquivo)"),
    competencia: str = Query("", description="Competência AAAAMM"),
    dt_importacao: str = Query("", description="Data de importação AAAA-MM-DD"),
):
    """
    Fluxo completo:
      1. Lê e valida a planilha (parse_planilha_vidas)
      2. Se dry_run=true → retorna preview sem gravar
      3. Grava SEGURADO, COBERTURA e IMPORTACAO_VIDAS no DB2
      4. O COBOL LCVIDAS01 (batch) aplica VGCCAP01 e finaliza
      5. O CICS (transação LCVD) consulta os resultados em tempo real

    Formato da planilha:
      Sub | Modulos | Nomes | Data de Nascimento | CPF |
      Data de Admissao | Salario | Cargos
    """
    # ── Resolve a fonte: arquivo local ou Google Sheets ───────────────────────
    if gsheet_url:
        filename, content = await _baixar_gsheet(gsheet_url)
        logger.info("Google Sheets baixado: %s → %d bytes", gsheet_url[:60], len(content))
    elif arquivo and arquivo.filename:
        filename = arquivo.filename
        if not filename.lower().endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(status_code=422, detail="Use arquivo .xlsx, .xls ou .csv")
        content = await arquivo.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="Arquivo excede 10 MB.")
    else:
        raise HTTPException(
            status_code=422,
            detail="Forneça um arquivo ou uma URL do Google Sheets (parâmetro gsheet_url).",
        )

    # ── Parse da planilha ─────────────────────────────────────────────────────
    try:
        resultado: ResultadoImportacaoVidas = parse_planilha_vidas(
            filename, content, nr_apolice
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Amostra para retorno ──────────────────────────────────────────────────
    amostra = [
        {
            "linha": v.linha,
            "cpf": f"***{v.cpf[-4:]}",
            "nome": v.nome,
            "subestipulante": v.subestipulante,
            "cargo": v.cargo,
            "vl_salario": v.vl_salario,
            "nr_fator_mult": v.nr_fator_mult,
            "vl_capital": v.vl_capital,
            "dt_admissao": v.dt_admissao,
            "status": "OK" if v.sucesso else "ERRO",
            "erros": v.erros,
        }
        for v in resultado.vidas[:10]
    ]

    if dry_run:
        return {
            "dry_run": True,
            "nr_apolice": nr_apolice,
            "total_linhas": resultado.total_linhas,
            "total_validos": resultado.total_sucesso,
            "total_erros": resultado.total_erros,
            "sumario_sub": resultado.sumario_sub,
            "amostra": amostra,
            "erros": resultado.erros[:20],
        }

    # ── Grava no DB2 ─────────────────────────────────────────────────────────
    resumo: dict = {}
    db2_ok = False
    try:
        resumo = gravar_vidas_db2(
            resultado=resultado,
            cd_empresa=cd_empresa,
            cd_empresa_sub1=cd_sub1,
            cd_empresa_sub2=cd_sub2,
            usuario=id_usuario,
        )
        db2_ok = True
    except Db2Unavailable:
        # DB2 não configurado em dev — continua para Supabase
        logger.warning("DB2 indisponível — gravando apenas no Supabase.")
        resumo = {
            "id_importacao": resultado.id_importacao,
            "nr_apolice": nr_apolice,
            "cd_status": "OK",
            "total_linhas": resultado.total_linhas,
            "total_gravados": resultado.total_sucesso,
            "total_erros_planilha": resultado.total_erros,
            "total_erros_db2": 0,
            "sumario_sub": resultado.sumario_sub,
            "erros_db2": [],
        }
    except Db2OperationFailed as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Grava no Supabase (dual-write) + reconciliação ────────────────────────
    from datetime import UTC, datetime

    # CPFs válidos na planilha atual (somente linhas sem erro)
    cpfs_planilha: set[str] = {
        v.cpf for v in resultado.vidas if v.sucesso
    }

    excluidos_supabase: list[dict] = []
    cpfs_saindo: set[str] = set()   # preenchido pela reconciliação Supabase

    try:
        import app.services.supabase_client as sc
        sb = sc.get_client()
        dt_hoje = datetime.now(UTC).strftime("%Y%m%d")
        dt_saida = competencia or dt_hoje[:6]  # AAAAMM da competência atual

        # ── Lote de importação ─────────────────────────────────────────────
        sb.table("importacao_vidas").upsert({
            "id_importacao": resultado.id_importacao,
            "nr_apolice": nr_apolice,
            "cd_empresa": cd_empresa,
            "qt_registros": resultado.total_linhas,
            "qt_validos": resultado.total_sucesso,
            "qt_gravados": resumo.get("total_gravados", resultado.total_sucesso),
            "qt_erros": resultado.total_erros,
            "cd_status": resumo.get("cd_status", "OK"),
            "dt_importacao": dt_importacao.replace("-", "") or dt_hoje,
            "id_usuario": id_usuario,
            "dry_run": False,
        }).execute()

        # ── Itens individuais ──────────────────────────────────────────────
        itens = []
        for v in resultado.vidas:
            itens.append({
                "id_importacao": resultado.id_importacao,
                "nr_linha": v.linha,
                "cd_cpf": v.cpf,
                "nm_segurado": v.nome,
                "dt_nascimento": v.dt_nascimento or "",
                "dt_admissao": v.dt_admissao or "",
                "cd_subestipulante": v.subestipulante or "",
                "cd_modulo": v.modulo or "",
                "cd_cargo": v.cargo or "",
                "vl_salario": float(v.vl_salario or 0),
                "nr_fator_mult": float(v.nr_fator_mult or 1),
                "vl_capital": float(v.vl_capital or 0),
                "cd_status": "OK" if v.sucesso else "ERRO",
                "ds_erros": "; ".join(v.erros) if v.erros else "",
            })
        if itens:
            sb.table("importacao_vidas_item").insert(itens).execute()

        # ── Reconciliação: busca coberturas ATIVAS desta apólice ───────────
        # Qualquer CPF ativo que não apareça na nova planilha é excluído.
        resp_ativas = (
            sb.table("coberturas")
            .select("cd_cobertura, cd_cpf, nm_cobertura")
            .eq("nr_apolice", nr_apolice)
            .eq("cd_status", "AT")
            .execute()
        )
        coberturas_ativas: list[dict] = resp_ativas.data or []
        cpfs_ativos: set[str] = {r["cd_cpf"] for r in coberturas_ativas}

        # CPFs que estavam ativos mas saíram da planilha
        cpfs_saindo = cpfs_ativos - cpfs_planilha
        for row in coberturas_ativas:
            if row["cd_cpf"] not in cpfs_saindo:
                continue
            # Desativa cobertura (tenta incluir campos de auditoria; tolera colunas ausentes)
            try:
                sb.table("coberturas").update({
                    "cd_status": "EX",
                    "dt_saida": dt_saida,
                    "id_importacao_saida": resultado.id_importacao,
                }).eq("cd_cobertura", row["cd_cobertura"]).execute()
            except Exception:
                # Fallback: colunas dt_saida/id_importacao_saida podem não existir
                # se a migração supabase_reconciliacao.sql ainda não foi executada.
                sb.table("coberturas").update({
                    "cd_status": "EX",
                }).eq("cd_cobertura", row["cd_cobertura"]).execute()
            excluidos_supabase.append({
                "cpf": f"***{row['cd_cpf'][-4:]}",
                "cd_cobertura": row["cd_cobertura"],
                "nm_segurado": row.get("nm_cobertura", ""),
            })
            logger.info(
                "Reconciliação: cobertura %s excluída (CPF não consta na planilha de %s)",
                row["cd_cobertura"], competencia,
            )

        # ── Upsert segurados + coberturas ativas ──────────────────────────
        for v in resultado.vidas:
            if not v.sucesso:
                continue
            sub_num = str(v.subestipulante or "").strip()
            cd_sub = cd_sub1 if sub_num == "1" else (cd_sub2 if sub_num == "2" else cd_empresa)

            sb.table("segurados").upsert({
                "cd_cpf": v.cpf,
                "nm_segurado": v.nome,
                "dt_nascimento": v.dt_nascimento or "",
                "cd_empresa": cd_sub,
                "vl_salario": float(v.vl_salario or 0),
                "dt_admissao": v.dt_admissao or "",
                "dt_inclusao": dt_hoje,
                "id_usuario_incl": id_usuario,
            }).execute()

            cd_cob = f"COB{v.cpf[:11]}"[:16]
            sb.table("coberturas").upsert({
                "cd_cobertura": cd_cob,
                "nr_apolice": nr_apolice,
                "cd_cpf": v.cpf,
                "cd_tipo": "MORT",
                "nm_cobertura": f"Morte — {v.nome[:40]}",
                "vl_capital": float(v.vl_capital or 0),
                "nr_carencia_dias": 0,
                "cd_status": "AT",
                "dt_saida": None,
                "id_importacao_saida": None,
            }).execute()

        logger.info(
            "Supabase: %d segurados gravados, %d excluídos — apólice %s importação %s",
            resultado.total_sucesso, len(excluidos_supabase), nr_apolice, resultado.id_importacao,
        )
    except Exception as exc:
        # Supabase não bloqueia — loga e continua
        logger.warning("Supabase dual-write/reconciliação falhou (não bloqueia): %s", exc)

    # ── Reconciliação no DB2 (se disponível) ──────────────────────────────────
    if db2_ok and cpfs_saindo:
        try:
            from app.repositories.empresa_db2 import _close, _connect, _prepare
            ibm_db, conn = _connect()
            try:
                for cpf_ex in cpfs_saindo:
                    cd_cob_ex = f"COB{cpf_ex[:11]}"[:16]
                    try:
                        _prepare(
                            ibm_db, conn,
                            "UPDATE LIFECORE.COBERTURA "
                            "SET CD_STATUS='EX', DT_SAIDA=? "
                            "WHERE CD_COBERTURA=? AND NR_APOLICE=?",
                            (dt_saida, cd_cob_ex, nr_apolice),
                        )
                    except Exception as exc_upd:
                        logger.warning("DB2 reconciliação ignorou CPF %s: %s", cpf_ex[-4:], exc_upd)
                ibm_db.commit(conn)
            finally:
                _close(ibm_db, conn)
        except Exception as exc_db2:
            logger.warning("DB2 reconciliação falhou (não bloqueia): %s", exc_db2)

    return {
        **resumo,
        "total_excluidos": len(excluidos_supabase),
        "exclusoes": excluidos_supabase[:50],
        "amostra": amostra,
        "fonte": "gsheet" if gsheet_url else "arquivo",
    }


@router.get(
    "/{nr_apolice}/importar-vidas",
    summary="Lista lotes de importação de vidas da apólice",
)
def listar_importacoes_vidas(
    nr_apolice: str,
    limite: int = Query(20, ge=1, le=100),
):
    """
    Lista os lotes de importação de vidas já processados para a apólice.
    Disponível também via CICS (transação LCVD).
    """
    try:
        from app.repositories.empresa_db2 import _close, _connect, _prepare

        ibm_db, conn = _connect()
        try:
            stmt = _prepare(
                ibm_db, conn,
                "SELECT ID_IMPORTACAO, CD_STATUS, QT_REGISTROS, QT_GRAVADOS, "
                "QT_ERROS, DT_IMPORTACAO, ID_USUARIO, TS_INCLUSAO "
                "FROM LIFECORE.IMPORTACAO_VIDAS "
                "WHERE NR_APOLICE = ? "
                "ORDER BY TS_INCLUSAO DESC "
                f"FETCH FIRST {limite} ROWS ONLY",
                (nr_apolice,),
            )
            rows = []
            while (raw := ibm_db.fetch_assoc(stmt)) not in (None, False):
                rows.append(
                    {k.lower(): v.rstrip() if isinstance(v, str) else v
                     for k, v in raw.items()}
                )
            return rows
        finally:
            _close(ibm_db, conn)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível consultar o DB2: {exc}",
        ) from exc
