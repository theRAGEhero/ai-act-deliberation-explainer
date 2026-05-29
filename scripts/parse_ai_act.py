import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.legal_source.akn_parser import AKNParser


def main():
    corpus = AKNParser().parse_file(settings.resolve_path(settings.ai_act_akn_path))
    print(f"Warnings: {corpus.warnings}")
    print(f"Articles: {len(corpus.articles)}")
    print(f"Definitions: {len(corpus.definitions)}")
    for article in corpus.articles[:20]:
        print(f"Article {article.number}: {article.heading} [{article.eId}]")
    for number in ["3", "13", "14", "27", "50", "86"]:
        found = next((a for a in corpus.articles if a.number == number), None)
        print(f"Article {number}: {'found' if found else 'missing'}")


if __name__ == "__main__":
    main()
