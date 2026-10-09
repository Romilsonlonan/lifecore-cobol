"""DB2 z/OS repository for the shared EMPRESA master record."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from app.core.config import settings
from app.schemas.lifecore import EmpresaCreate, StatusGeralEnum


class Db2Unavailable(RuntimeError):
    """The DB2 repository is not configured or could not be reached."""


class EmpresaNotFound(LookupError):
    """No EMPRESA row exists for the requested key."""


class EmpresaAlreadyExists(ValueError):
    """The EMPRESA code or CNPJ is already present in DB2."""


class Db2OperationFailed(RuntimeError):
    """A DB2 command failed for a reason other than a duplicate key."""


def _identifier(value: str) -> str:
    normalized = value.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", normalized):
        raise Db2Unavailable("O schema DB2 configurado não é válido.")
    return normalized


def _connect() -> tuple[Any, Any]:
    if not settings.db2_dsn:
        raise Db2Unavailable("DB2_DSN não foi configurado.")
    try:
        import ibm_db
    except ImportError as exc:
        raise Db2Unavailable("O driver IBM Db2 não está instalado.") from exc
    try:
        connection = ibm_db.connect(settings.db2_dsn, "", "")
    except ibm_db.IBM_DBException as exc:
        raise Db2Unavailable("Não foi possível conectar ao DB2 configurado.") from exc
    if not connection:
        raise Db2Unavailable("Não foi possível conectar ao DB2 configurado.")
    return ibm_db, connection


def _prepare(
    ibm_db: Any, connection: Any, sql: str, values: tuple[Any, ...] = ()
) -> Any:
    statement = ibm_db.prepare(connection, sql)
    if not statement:
        raise Db2OperationFailed("O DB2 não preparou a operação solicitada.")
    if not ibm_db.execute(statement, values):
        error_code = ibm_db.stmt_error(statement) or ""
        if "-803" in error_code or "23505" in error_code or "SQL0803" in error_code:
            raise EmpresaAlreadyExists("Código ou CNPJ já cadastrado.")
        raise Db2OperationFailed("O DB2 não concluiu a operação solicitada.")
    return statement


def _row(ibm_db: Any, statement: Any) -> dict[str, Any] | None:
    raw_row = ibm_db.fetch_assoc(statement)
    if raw_row is None or raw_row is False:
        return None
    row = {key.lower(): value for key, value in raw_row.items()}
    for key, value in row.items():
        if isinstance(value, str):
            row[key] = value.rstrip()
    if "cd_status" in row:
        row["cd_status"] = StatusGeralEnum(row["cd_status"])
    if isinstance(row.get("dt_inclusao"), date):
        row["dt_inclusao"] = row["dt_inclusao"].strftime("%Y%m%d")
    return row


def _close(ibm_db: Any, connection: Any) -> None:
    ibm_db.close(connection)


class Db2EmpresaRepository:
    """Reads and writes the EMPRESA table used by both API and CICS."""

    def __init__(self) -> None:
        self._table = f"{_identifier(settings.db2_schema)}.EMPRESA"

    @staticmethod
    def _close(ibm_db: Any, connection: Any) -> None:
        _close(ibm_db, connection)

    def listar(self, status: StatusGeralEnum | None = None) -> list[dict[str, Any]]:
        ibm_db, connection = _connect()
        try:
            sql = (
                "SELECT CD_EMPRESA, NR_CODIGO, NM_RAZAO_SOCIAL, "
                "NM_NOME_REDUZIDO, CD_CNPJ, TP_EMPRESA, NR_SUSEP, "
                "VL_CAPITAL_VINCULADO, VL_CAPITAL_SUBSCRITO, "
                "VL_ACEITE_COBRANCA, CD_STATUS, DT_INCLUSAO, TS_INCLUSAO "
                f"FROM {self._table}"
            )
            values: tuple[Any, ...] = ()
            if status:
                sql += " WHERE CD_STATUS = ?"
                values = (status.value,)
            sql += " ORDER BY CD_EMPRESA"
            statement = _prepare(ibm_db, connection, sql, values)
            result = []
            while (row := _row(ibm_db, statement)) is not None:
                result.append(row)
            return result
        finally:
            self._close(ibm_db, connection)

    def obter(self, cd_empresa: int) -> dict[str, Any]:
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                "SELECT CD_EMPRESA, NR_CODIGO, NM_RAZAO_SOCIAL, "
                "NM_NOME_REDUZIDO, CD_CNPJ, TP_EMPRESA, NR_SUSEP, "
                "VL_CAPITAL_VINCULADO, VL_CAPITAL_SUBSCRITO, "
                "VL_ACEITE_COBRANCA, CD_STATUS, DT_INCLUSAO, TS_INCLUSAO "
                f"FROM {self._table} WHERE CD_EMPRESA = ?",
                (cd_empresa,),
            )
            row = _row(ibm_db, statement)
            if row is None:
                raise EmpresaNotFound
            return row
        finally:
            self._close(ibm_db, connection)

    def criar(self, payload: EmpresaCreate, usuario: str) -> dict[str, Any]:
        ibm_db, connection = _connect()
        try:
            _prepare(
                ibm_db,
                connection,
                f"INSERT INTO {self._table} "
                "(NR_CODIGO, NM_RAZAO_SOCIAL, NM_NOME_REDUZIDO, CD_CNPJ, "
                "TP_EMPRESA, NR_SUSEP, VL_CAPITAL_VINCULADO, "
                "VL_CAPITAL_SUBSCRITO, VL_ACEITE_COBRANCA, CD_STATUS, "
                "DT_INCLUSAO, ID_USUARIO_INCL) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AT', ?, ?)",
                (
                    payload.nr_codigo,
                    payload.nm_razao_social,
                    payload.nm_nome_reduzido,
                    payload.cd_cnpj,
                    payload.tp_empresa.value,
                    payload.nr_susep,
                    payload.vl_capital_vinculado,
                    payload.vl_capital_subscrito,
                    payload.vl_aceite_cobranca,
                    datetime.now(UTC).strftime("%Y%m%d"),
                    usuario[:8].upper().ljust(8),
                ),
            )
            statement = _prepare(
                ibm_db,
                connection,
                "SELECT IDENTITY_VAL_LOCAL() AS CD_EMPRESA "
                "FROM SYSIBM.SYSDUMMY1",
            )
            row = _row(ibm_db, statement)
            if row is None:
                raise Db2Unavailable("O DB2 não retornou o código criado.")
            created_id = int(row["cd_empresa"])
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            self._close(ibm_db, connection)
        return self.obter(created_id)

    def alterar_status(
        self, cd_empresa: int, status: StatusGeralEnum
    ) -> dict[str, Any]:
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                f"UPDATE {self._table} SET CD_STATUS = ?, "
                "TS_ALTERACAO = CURRENT TIMESTAMP WHERE CD_EMPRESA = ?",
                (status.value, cd_empresa),
            )
            if ibm_db.num_rows(statement) == 0:
                raise EmpresaNotFound
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            self._close(ibm_db, connection)
        return self.obter(cd_empresa)

    def obter_por_cnpj(self, cd_cnpj: str) -> dict[str, Any]:
        """Return the EMPRESA row whose CD_CNPJ matches exactly."""
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                "SELECT CD_EMPRESA, NR_CODIGO, NM_RAZAO_SOCIAL, "
                "NM_NOME_REDUZIDO, CD_CNPJ, TP_EMPRESA, NR_SUSEP, "
                "VL_CAPITAL_VINCULADO, VL_CAPITAL_SUBSCRITO, "
                "VL_ACEITE_COBRANCA, CD_STATUS, DT_INCLUSAO, TS_INCLUSAO "
                f"FROM {self._table} WHERE CD_CNPJ = ?",
                (cd_cnpj,),
            )
            row = _row(ibm_db, statement)
            if row is None:
                raise EmpresaNotFound
            return row
        finally:
            self._close(ibm_db, connection)

    def cancelar(
        self,
        cd_empresa: int,
        dt_cancelamento: str,
        ds_motivo: str,
        usuario: str,
    ) -> dict[str, Any]:
        """Set CD_STATUS='CA' and record the cancellation metadata."""
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                f"UPDATE {self._table} SET "
                "CD_STATUS = 'CA', "
                "DT_CANCELAMENTO = ?, "
                "DS_MOTIVO_CANCELAMENTO = ?, "
                "ID_USUARIO_CANCEL = ?, "
                "TS_ALTERACAO = CURRENT TIMESTAMP "
                "WHERE CD_EMPRESA = ?",
                (
                    dt_cancelamento,
                    ds_motivo[:200],
                    usuario[:8].upper().ljust(8),
                    cd_empresa,
                ),
            )
            if ibm_db.num_rows(statement) == 0:
                raise EmpresaNotFound
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            self._close(ibm_db, connection)
        return self.obter(cd_empresa)

    def suspender(
        self,
        cd_empresa: int,
        dt_inicio_suspensao: str,
        dt_fim_suspensao: str,
        ds_motivo: str,
        usuario: str,
    ) -> dict[str, Any]:
        """Set CD_STATUS='SU' and record the suspension window."""
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                f"UPDATE {self._table} SET "
                "CD_STATUS = 'SU', "
                "DT_INICIO_SUSPENSAO = ?, "
                "DT_FIM_SUSPENSAO = ?, "
                "DS_MOTIVO_SUSPENSAO = ?, "
                "ID_USUARIO_CANCEL = ?, "
                "TS_ALTERACAO = CURRENT TIMESTAMP "
                "WHERE CD_EMPRESA = ?",
                (
                    dt_inicio_suspensao,
                    dt_fim_suspensao,
                    ds_motivo[:200],
                    usuario[:8].upper().ljust(8),
                    cd_empresa,
                ),
            )
            if ibm_db.num_rows(statement) == 0:
                raise EmpresaNotFound
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            self._close(ibm_db, connection)
        return self.obter(cd_empresa)

    def reativar_suspensao(self, cd_empresa: int, usuario: str) -> dict[str, Any]:
        """Clear suspension: set CD_STATUS back to 'AT'."""
        ibm_db, connection = _connect()
        try:
            statement = _prepare(
                ibm_db,
                connection,
                f"UPDATE {self._table} SET "
                "CD_STATUS = 'AT', "
                "DT_FIM_SUSPENSAO = CURRENT DATE, "
                "ID_USUARIO_CANCEL = ?, "
                "TS_ALTERACAO = CURRENT TIMESTAMP "
                "WHERE CD_EMPRESA = ? AND CD_STATUS = 'SU'",
                (usuario[:8].upper().ljust(8), cd_empresa),
            )
            if ibm_db.num_rows(statement) == 0:
                raise EmpresaNotFound
            ibm_db.commit(connection)
        except Exception:
            ibm_db.rollback(connection)
            raise
        finally:
            self._close(ibm_db, connection)
        return self.obter(cd_empresa)


empresa_repository = Db2EmpresaRepository()
