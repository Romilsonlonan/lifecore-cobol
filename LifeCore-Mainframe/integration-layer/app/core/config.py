"""
Configurações da Integration Layer via variáveis de ambiente.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Caminhos dos datasets (ajuste para z/OS via Zowe ou local) ──
    data_input_dir: Path = Path("/tmp/lifecore/DATA/INPUT")
    data_output_dir: Path = Path("/tmp/lifecore/DATA/OUTPUT")
    data_quarantine_dir: Path = Path("/tmp/lifecore/DATA/QUARANTINE")
    load_dir: Path = Path("/tmp/lifecore/LOAD")

    # ── Banco de dados (PostgreSQL / DB2 emulado) ──
    database_url: str = "postgresql://postgres:lifecore@localhost:5432/lifecore"

    # ── Supabase ──
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # ── Object Storage — S3-compatible (Supabase Storage ou MinIO) ──
    # Endpoint Supabase:  https://<projeto>.storage.supabase.co/storage/v1/s3
    # Endpoint MinIO dev: http://localhost:9000
    storage_endpoint:   str = "http://localhost:9000"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region:     str = "sa-east-1"
    storage_bucket:     str = "ecm-docs"

    @property
    def storage_configured(self) -> bool:
        """True quando as chaves S3 estão definidas no .env."""
        return bool(self.storage_access_key and self.storage_secret_key)

    # DB2 z/OS is the authoritative store for records shared with CICS.
    db2_dsn: str | None = None
    db2_schema: str = "LIFECORE"

    # ── Conector batch ──
    # Opções: "local" (GnuCOBOL subprocess) | "zowe" (z/OS real) | "stub" (simulação)
    batch_connector: str = "stub"

    # ── Zowe CLI (somente se batch_connector = "zowe") ──
    zowe_profile: str = "zos-dev"
    zos_hlq: str = "LIFECORE"
    zos_db2_system: str = "DB2P"

    # ── Raiz do projeto (para localizar binários COBOL) ──
    project_root: Path = Path(__file__).resolve().parents[3]

    # ── Frontend Next.js — build estático gerado por 'npm run build' ──
    # Padrão: <repo>/frontend/out   (ajuste via FRONTEND_BUILD_DIR no .env)
    frontend_build_dir: Path = Path(__file__).resolve().parents[3] / "frontend" / "out"

    @property
    def cobol_load_dir(self) -> Path:
        return self.project_root / "LOAD"

    @property
    def cobol_copylib_dir(self) -> Path:
        return self.project_root / "COPYLIB"

    model_config = {
        # Lê o .env único na raiz do repositório
        # config.py → app/core → app → integration-layer → LifeCore-Mainframe → LifeCore-Cobol(.env)
        "env_file": str(Path(__file__).resolve().parents[4] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# Garante que os diretórios existam ao subir a aplicação
for _dir in (
    settings.data_input_dir,
    settings.data_output_dir,
    settings.data_quarantine_dir,
):
    _dir.mkdir(parents=True, exist_ok=True)
