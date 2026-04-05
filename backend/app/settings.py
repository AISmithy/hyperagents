from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    root_dir = backend_dir.parent
    for env_path in (root_dir / ".env.local", backend_dir / ".env.local"):
        _load_env_file(env_path)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    use_openai: bool
    github_token: str
    db_path: str
    reviewer_prompt_path: str   # Path to code-reviewer.md; written after every submit

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)


def get_settings() -> Settings:
    load_local_env()
    backend_dir = Path(__file__).resolve().parents[1]
    root_dir = backend_dir.parent
    default_db = str(root_dir / "hyperagents.db")
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini",
        use_openai=_flag("HYPERAGENTS_USE_OPENAI", default=False),
        github_token=os.getenv("GITHUB_TOKEN", "").strip(),
        db_path=os.getenv("HYPERAGENTS_DB_PATH", default_db).strip(),
        reviewer_prompt_path=os.getenv("REVIEWER_PROMPT_PATH", "").strip(),
    )
