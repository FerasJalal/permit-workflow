from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./permits.db"

    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_sender_email: str = ""

    adobe_sign_base_url: str = "https://api.na1.adobesign.com/api/rest/v6"
    adobe_sign_access_token: str = ""
    adobe_sign_webhook_url: str = ""

    sharepoint_site_id: str = ""
    sharepoint_drive_id: str = ""
    sharepoint_folder_path: str = "/Permits/Signed"

    app_base_url: str = "http://localhost:8000"
    templates_dir: str = "templates"
    uploads_dir: str = "uploads"
    generated_dir: str = "generated"
    libreoffice_path: str = "soffice"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def templates_path(self) -> Path:
        return Path(self.templates_dir)

    @property
    def uploads_path(self) -> Path:
        return Path(self.uploads_dir)

    @property
    def generated_path(self) -> Path:
        return Path(self.generated_dir)


settings = Settings()
