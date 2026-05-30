from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    project_root: Path = Path(__file__).resolve().parent.parent
    ai_act_akn_path: Path = Path(os.getenv("AI_ACT_AKN_PATH", "data/aiACT.xml"))
    seed_concepts_path: Path = Path("data/seed_concepts.json")
    seed_annexes_path: Path = Path("data/seed_annexes.json")
    seed_prohibitions_path: Path = Path("data/seed_prohibitions.json")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.6:free")
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "https://ai-act.democracyroutes.com")
    openrouter_app_title: str = os.getenv("OPENROUTER_APP_TITLE", "AI Act Prohibitions Checker")

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.project_root / path


settings = Settings()
