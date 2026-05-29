import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.legal_source.legal_db import LegalKnowledgeDB
from app.ontology.export import export_graph
from app.ontology.ontology_store import OntologyStore


def main():
    legal_db = LegalKnowledgeDB(settings.resolve_path(settings.seed_concepts_path))
    legal_db.load_from_akn(settings.resolve_path(settings.ai_act_akn_path))
    store = OntologyStore(settings.resolve_path(settings.seed_concepts_path), settings.resolve_path(settings.seed_annexes_path), legal_db)
    turtle, jsonld = export_graph(store.get_graph(), settings.project_root / "generated")
    print(f"Wrote {turtle}")
    print(f"Wrote {jsonld}")
    print(f"Triples: {len(store.get_graph())}")


if __name__ == "__main__":
    main()
