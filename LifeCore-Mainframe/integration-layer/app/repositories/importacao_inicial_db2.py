"""Persistência DB2 para lotes de cadastro inicial aguardando vínculo contratual."""

from __future__ import annotations

import uuid
from typing import Any

from app.repositories.empresa_db2 import _close, _connect, _identifier, _prepare
from app.core.config import settings


class Db2ImportacaoInicialRepository:
    def __init__(self) -> None:
        self._schema = _identifier(settings.db2_schema)

    def criar(self, rows: list[dict[str, Any]], usuario: str) -> dict[str, Any]:
        importacao_id = str(uuid.uuid4())
        ibm_db, connection = _connect()
        try:
            _prepare(
                ibm_db,
                connection,
                f"INSERT INTO {self._schema}.IMPORTACAO_INICIAL "
                "(ID_IMPORTACAO, CD_STATUS, QT_REGISTROS, ID_USUARIO, TS_INCLUSAO) "
                "VALUES (?, 'RV', ?, ?, CURRENT TIMESTAMP)",
                (importacao_id, len(rows), usuario[:8].upper().ljust(8)),
            )
            for row in rows:
                errors = "; ".join(row["erros"])[:1000]
                _prepare(
                    ibm_db,
                    connection,
                    f"INSERT INTO {self._schema}.IMPORTACAO_INICIAL_ITEM "
                    "(ID_IMPORTACAO, NR_LINHA, CD_SUBESTIPULANTE, CD_MODULO, "
                    "NM_SEGURADO, CD_CPF, DT_NASCIMENTO, DT_ADMISSAO, "
                    "DS_ERROS, CD_STATUS) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        importacao_id,
                        row["linha_planilha"],
                        row["subestipulante"],
                        row["modulo"],
                        row["nome_segurado"],
                        row["cpf"],
                        row["dt_nascimento"],
                        row["dt_admissao"],
                        errors or None,
                        "ER" if errors else "RV",
                    ),
                )
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            _close(ibm_db, connection)
        return {
            "id_importacao": importacao_id,
            "cd_status": "RV",
            "total_registros": len(rows),
            "total_validos": sum(not row["erros"] for row in rows),
            "total_erros": sum(bool(row["erros"]) for row in rows),
        }

    def listar(self, limite: int = 50) -> list[dict[str, Any]]:
        ibm_db, connection = _connect()
        try:
            safe_limit = max(1, min(limite, 100))
            statement = _prepare(
                ibm_db,
                connection,
                f"SELECT ID_IMPORTACAO, CD_STATUS, QT_REGISTROS, "
                "ID_USUARIO, TS_INCLUSAO "
                f"FROM {self._schema}.IMPORTACAO_INICIAL "
                f"ORDER BY TS_INCLUSAO DESC FETCH FIRST {safe_limit} ROWS ONLY",
            )
            rows = []
            while (raw := ibm_db.fetch_assoc(statement)) is not None and raw is not False:
                rows.append(self._normalize_row(raw))
            return rows
        finally:
            _close(ibm_db, connection)

    def obter(self, importacao_id: str) -> dict[str, Any] | None:
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                f"SELECT ID_IMPORTACAO, CD_STATUS, QT_REGISTROS, "
                "ID_USUARIO, TS_INCLUSAO "
                f"FROM {self._schema}.IMPORTACAO_INICIAL "
                "WHERE ID_IMPORTACAO = ?",
                (importacao_id,),
            )
            raw = ibm_db.fetch_assoc(statement)
            if raw is None or raw is False:
                return None
            result = self._normalize_row(raw)
            statement = _prepare(
                ibm_db,
                connection,
                f"SELECT NR_LINHA, CD_SUBESTIPULANTE, CD_MODULO, NM_SEGURADO, "
                "CD_CPF, DT_NASCIMENTO, DT_ADMISSAO, DS_ERROS, CD_STATUS "
                f"FROM {self._schema}.IMPORTACAO_INICIAL_ITEM "
                "WHERE ID_IMPORTACAO = ? ORDER BY NR_LINHA",
                (importacao_id,),
            )
            items = []
            while (row := ibm_db.fetch_assoc(statement)) is not None and row is not False:
                item = {key.lower(): value for key, value in row.items()}
                for key in ("cd_subestipulante", "cd_modulo", "nm_segurado", "cd_cpf", "ds_erros"):
                    if isinstance(item.get(key), str):
                        item[key] = item[key].rstrip()
                item["erros"] = (
                    [item["ds_erros"]] if item.get("ds_erros") else []
                )
                items.append(item)
            result["itens"] = items
            return result
        finally:
            _close(ibm_db, connection)

    @staticmethod
    def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            key.lower(): value.rstrip() if isinstance(value, str) else value
            for key, value in raw.items()
        }


importacao_inicial_repository = Db2ImportacaoInicialRepository()
