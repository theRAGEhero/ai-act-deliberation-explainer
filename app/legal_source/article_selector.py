from app.legal_source.legal_db import CONCEPT_ARTICLE_MAP, LegalKnowledgeDB
from app.models import LegalSourceRef


ARTICLE_REASONS = {
    "3": "Definitions may be needed to identify AI systems, actors and affected persons.",
    "5": "Prohibited-practice screening may be relevant and should be ruled in or out.",
    "6": "The scenario may fall within high-risk classification rules, especially where Annex III areas are signalled.",
    "9": "Risk-management obligations may need verification for a potentially high-risk AI system.",
    "10": "Data governance may be relevant where historical, training, welfare or demographic data is used.",
    "11": "Technical documentation may need verification for a potentially high-risk AI system.",
    "12": "Record-keeping/logging may need verification where outputs influence decisions.",
    "13": "Transparency for deployers may be relevant where people must interpret and use AI outputs appropriately.",
    "14": "Human oversight may be relevant where a human officer reviews or approves AI-influenced decisions.",
    "15": "Accuracy, robustness and cybersecurity may need verification for high-risk uses.",
    "26": "Deployer obligations may be relevant where a public body or organisation uses the system.",
    "27": "A fundamental rights impact assessment may be relevant for public-sector or Annex III uses.",
    "50": "Specific transparency duties may be relevant for chatbots or generated/synthetic content.",
    "86": "Explanation of individual decision-making may be relevant where an output significantly affects a person.",
}

PRIORITY = ["3", "6", "13", "14", "26", "27", "86", "10", "11", "12", "50", "5", "9", "15"]


def source_refs_for_concepts(concepts: list[str], legal_db: LegalKnowledgeDB) -> list[LegalSourceRef]:
    refs: list[LegalSourceRef] = []
    for number in _numbers_for_concepts(concepts):
        article = legal_db.get_article_by_number(number)
        if not article:
            continue
        refs.append(
            LegalSourceRef(
                article_number=article.number,
                article_heading=article.heading,
                eId=article.eId,
                short_excerpt=article.text[:450],
                relevance_reason=ARTICLE_REASONS.get(article.number, f"May be relevant to: {', '.join(concepts[:6])}"),
            )
        )
    return refs


def _numbers_for_concepts(concepts: list[str]) -> list[str]:
    found = {"3"}
    for concept in [concept.lower() for concept in concepts]:
        for key, mapped in CONCEPT_ARTICLE_MAP.items():
            if key in concept:
                found.update(mapped)
        if any(term in concept for term in ["annex iii", "employment", "education", "public services", "public benefits", "essential private services", "essential public services"]):
            found.update({"6", "13", "14", "26", "27", "86"})
        if any(term in concept for term in ["ranking", "scoring", "automated decision", "filtering", "recommendation"]):
            found.update({"6", "13", "14", "26", "86", "12"})
        if any(term in concept for term in ["bias", "dataset", "data governance", "historical data", "provenance"]):
            found.update({"10", "27"})
        if any(term in concept for term in ["opacity", "transparency", "explanation", "contestability"]):
            found.update({"13", "86"})
        if any(term in concept for term in ["human oversight", "human review", "automation bias"]):
            found.update({"14", "26"})
        if any(term in concept for term in ["technical documentation", "instructions"]):
            found.update({"11", "13"})
        if "logs" in concept or "logging" in concept:
            found.add("12")
        if any(term in concept for term in ["chatbot", "generated", "synthetic content"]):
            found.add("50")
    return [number for number in PRIORITY if number in found] + sorted(found.difference(PRIORITY), key=lambda n: int(n) if n.isdigit() else 999)
