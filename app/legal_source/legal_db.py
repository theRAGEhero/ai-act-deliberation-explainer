from __future__ import annotations

import json
from pathlib import Path

from app.legal_source.akn_parser import AKNParser
from app.models import LegalArticle, LegalCorpus


SEEDED_ARTICLES = {
    "3": "Definitions",
    "5": "Prohibited AI practices",
    "6": "Classification rules for high-risk AI systems",
    "9": "Risk management system",
    "10": "Data and data governance",
    "11": "Technical documentation",
    "12": "Record-keeping",
    "13": "Transparency and provision of information to deployers",
    "14": "Human oversight",
    "15": "Accuracy, robustness and cybersecurity",
    "26": "Obligations of deployers of high-risk AI systems",
    "27": "Fundamental rights impact assessment for high-risk AI systems",
    "50": "Transparency obligations for providers and deployers of certain AI systems",
    "86": "Right to explanation of individual decision-making",
}


CONCEPT_ARTICLE_MAP = {
    "definitions": ["3"],
    "ai system": ["3"],
    "prohibited practice": ["5"],
    "high-risk": ["6"],
    "annex iii": ["6"],
    "risk management": ["9"],
    "data governance": ["10"],
    "dataset provenance": ["10"],
    "technical documentation": ["11"],
    "logging": ["12"],
    "transparency": ["13"],
    "chatbot": ["50"],
    "content generation": ["50"],
    "human oversight": ["14"],
    "deployer": ["26"],
    "fundamental rights impact assessment": ["27"],
    "right to explanation": ["86"],
    "contestability": ["86"],
}


class LegalKnowledgeDB:
    def __init__(self, seed_concepts_path: str | Path | None = None):
        self.corpus = LegalCorpus()
        self.articles_by_number: dict[str, LegalArticle] = {}
        self.seed_concepts = self._load_json(seed_concepts_path) if seed_concepts_path else {}
        self._load_seeded_articles()

    def load_from_akn(self, path: str | Path) -> LegalCorpus:
        parsed = AKNParser().parse_file(path)
        self.corpus = parsed
        self.articles_by_number = {article.number: article for article in parsed.articles}
        self._load_seeded_articles(fill_only=True)
        return parsed

    def get_article_by_number(self, number: str) -> LegalArticle | None:
        return self.articles_by_number.get(str(number))

    def search_articles(self, query_terms: list[str]) -> list[LegalArticle]:
        terms = [term.lower() for term in query_terms if term]
        scored: list[tuple[int, LegalArticle]] = []
        for article in self.articles_by_number.values():
            haystack = f"{article.heading or ''} {article.text}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, article))
        return [article for _, article in sorted(scored, key=lambda item: item[0], reverse=True)]

    def get_relevant_articles_for_concepts(self, concepts: list[str]) -> list[LegalArticle]:
        numbers: list[str] = ["3"]
        for concept in concepts:
            lowered = concept.lower()
            for key, mapped in CONCEPT_ARTICLE_MAP.items():
                if key in lowered:
                    numbers.extend(mapped)
        seen = set()
        articles = []
        for number in numbers:
            if number not in seen and (article := self.get_article_by_number(number)):
                seen.add(number)
                articles.append(article)
        return articles

    def _load_seeded_articles(self, fill_only: bool = False) -> None:
        for number, heading in SEEDED_ARTICLES.items():
            if fill_only and number in self.articles_by_number:
                continue
            self.articles_by_number[number] = LegalArticle(
                number=number,
                heading=heading,
                text=f"Seed reference for AI Act Article {number}: {heading}. Replace with parsed AKN text when available.",
                source_type="seed",
            )
        self.corpus.articles = list(self.articles_by_number.values())

    def _load_json(self, path: str | Path | None) -> dict:
        if not path or not Path(path).exists():
            return {}
        return json.loads(Path(path).read_text(encoding="utf-8"))
