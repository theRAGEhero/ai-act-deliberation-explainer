from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    project_root: Path = Path(__file__).resolve().parent.parent
    ai_act_akn_path: Path = Path(os.getenv("AI_ACT_AKN_PATH", "reference/akoma-ntoso/aiAct-2024-1689.xml"))
    akomantoso_xsd_path: Path = Path(os.getenv("AKOMANTOSO_XSD_PATH", "reference/akoma-ntoso/akomantoso30.xsd"))
    xml_xsd_path: Path = Path(os.getenv("XML_XSD_PATH", "reference/akoma-ntoso/xml.xsd"))
    akomantoso_reference_path: Path | None = Path(os.getenv("AKOMANTOSO_REFERENCE_PATH", "reference/akoma-ntoso/akomantoso30.xml"))
    legal_ontology_dir: Path = Path(os.getenv("LEGAL_ONTOLOGY_DIR", "data/ontology"))
    seed_concepts_path: Path = Path("data/supporting/seed_concepts.json")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.6:free")
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "https://ai-act.democracyroutes.com")
    openrouter_app_title: str = os.getenv("OPENROUTER_APP_TITLE", "AI Act Prohibitions Checker")

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.project_root / path


settings = Settings()
