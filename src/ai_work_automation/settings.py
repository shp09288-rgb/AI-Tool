from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel


class Settings(BaseModel):
    automation_enabled_after: datetime
    opt_in_path: Path = Path("data/opt_in.json")
    job_log_path: Path = Path("data/job_log.jsonl")
    routes_path: Path = Path("config/routes.yaml")
    pms_base_url: str = "https://pms.parksystems.com"
    pms_api_key_env: str = "PMS_API_KEY"
    sf_instance_url_env: str = "SF_INSTANCE_URL"
    sf_access_token_env: str = "SF_ACCESS_TOKEN"
    dry_run: bool = False


def load_settings(path: Path) -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
