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
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.project_root / path


settings = Settings()
