from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


class Paths:
    root = REPO_ROOT
    data = REPO_ROOT / "data"
    bronze = REPO_ROOT / "data" / "bronze"
    silver = REPO_ROOT / "data" / "silver"
    gold = REPO_ROOT / "data" / "gold"
    gold_nc = REPO_ROOT / "data" / "gold" / "nc"
    manifests = REPO_ROOT / "data" / "manifests"
    replay = REPO_ROOT / "data" / "replay"
    registry = REPO_ROOT / "core" / "registry"
    corridors = REPO_ROOT / "core" / "watch"
    dist = REPO_ROOT / "dist"
    trace = REPO_ROOT / "data" / "trace"
    state_db = REPO_ROOT / "data" / "sanket.sqlite"
    lakehouse_db = REPO_ROOT / "data" / "lakehouse.duckdb"
    chroma = REPO_ROOT / "dist" / "chroma"
    audio = REPO_ROOT / "dist" / "audio"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    max_steps: int = 10
    tick_seconds_active: int = 900
    tick_seconds_standing: int = 21600
    tick_seconds_survey: int = 604800
    run_timeout_seconds: int = 300
    baseline_observations: int = 14
    escalation_z: float = 3.0
    maintenance_z: float = 2.0
    lead_time_threshold_minutes: int = 30
    cooldown_minutes: int = 40
    gate_deadline_minutes: int = 30
    vertical_exaggeration: float = 1.6
    npr_per_usd: float = 141.0
    aoi_bbox: tuple[float, float, float, float] = (85.10, 27.80, 85.45, 28.55)
    working_crs: str = "EPSG:32645"
    display_crs: str = "EPSG:4326"
    scenario_volumes_mm3: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
    scenario_breach_minutes: tuple[int, ...] = (5, 15, 30, 60, 120, 180, 360)
    replay_message_prefix: str = "[REPLAY - TEST]"
    log_level: str = "INFO"
    earthdata_username: str = Field(default="")
    earthdata_password: str = Field(default="")
    public_base_url: str = Field(default="http://127.0.0.1:5000")


settings = Settings()
paths = Paths()


def ensure_directories() -> None:
    for directory in (
        paths.bronze,
        paths.silver,
        paths.gold,
        paths.gold_nc,
        paths.manifests,
        paths.replay,
        paths.dist,
        paths.trace,
        paths.audio,
    ):
        directory.mkdir(parents=True, exist_ok=True)
