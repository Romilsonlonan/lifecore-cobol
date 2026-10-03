"""
Configurações da Integration Layer via variáveis de ambiente.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── Caminhos dos datasets (ajuste para z/OS via Zowe ou local) ──
    data_input_dir: Path = Path("/tmp/lifecore/DATA/INPUT")
    data_output_dir: Path = Path("/tmp/lifecore/DATA/OUTPUT")
    data_quarantine_dir: Path = Path("/tmp/lifecore/DATA/QUARANTINE")
    load_dir: Path = Path("/tmp/lifecore/LOAD")

    # ── Banco de dados (PostgreSQL / DB2 emulado) ──
    database_url: str = "postgresql://postgres:lifecore@localhost:5432/lifecore"

    # ── Conector batch ──
    # Opções: "local" (GnuCOBOL subprocess) | "zowe" (z/OS real) | "stub" (simulação)
    batch_connector: str = "stub"

    # ── Zowe CLI (somente se batch_connector = "zowe") ──
    zowe_profile: str = "zos-dev"
    zos_hlq: str = "LIFECORE"
    zos_db2_system: str = "DB2P"

    # ── Raiz do projeto (para localizar binários COBOL) ──
    project_root: Path = Path(__file__).resolve().parents[3]

    @property
    def cobol_load_dir(self) -> Path:
        return self.project_root / "LOAD"

    @property
    def cobol_copylib_dir(self) -> Path:
        return self.project_root / "COPYLIB"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Garante que os diretórios existam ao subir a aplicação
for _dir in (
    settings.data_input_dir,
    settings.data_output_dir,
    settings.data_quarantine_dir,
):
    _dir.mkdir(parents=True, exist_ok=True)
