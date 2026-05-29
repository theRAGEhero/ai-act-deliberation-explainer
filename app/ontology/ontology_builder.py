from __future__ import annotations

import json
import re
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef


EX = Namespace("http://example.org/ai-act-deliberation#")


def slug(value: str) -> str:
    parts = re.sub(r"[^A-Za-z0-9]+", " ", value).strip().title().split()
    return "".join(parts) or "Unknown"


class OntologyBuilder:
    def __init__(self):
        self.graph = Graph()
        self.graph.bind("aid", EX)
        self.graph.bind("rdfs", RDFS)

    def build(self, seed_concepts_path: Path, seed_annexes_path: Path, legal_db=None) -> Graph:
        g = self.graph
        for cls in ["AIActArticle", "Actor", "Concept", "Risk", "RightOrInterest", "Obligation", "Scenario", "EvidenceSnippet", "MissingQuestion", "LegalSource", "AnnexArea"]:
            g.add((EX[cls], RDF.type, RDFS.Class))
        for prop in ["concerns", "defines", "createsObligation", "hasRisk", "hasRightOrInterest", "hasActor", "usedInContext", "mayTrigger", "sourceArticle", "detectedFrom", "hasMissingQuestion", "affects", "requires", "relatedToAnnexArea", "hasObligation"]:
            g.add((EX[prop], RDF.type, RDF.Property))

        seed = self._load(seed_concepts_path)
        for actor in seed.get("actors", []):
            self._individual(actor, "Actor")
        for concept in seed.get("concepts", []):
            self._individual(concept, "Concept")
        for risk in seed.get("risks", []):
            self._individual(risk, "Risk")
        for right in seed.get("rights_or_interests", []):
            self._individual(right, "RightOrInterest")
        for obligation in seed.get("obligations_to_verify", []):
            self._individual(obligation, "Obligation")

        annex = self._load(seed_annexes_path).get("annex_iii", [])
        for area in annex:
            uri = EX[f"AnnexIII{slug(area['id'])}"]
            g.add((uri, RDF.type, EX.AnnexArea))
            g.add((uri, RDFS.label, Literal(area["label"])))
            for risk in area.get("risk_hints", []):
                g.add((uri, EX.hasRisk, EX[slug(risk)]))
            for q in area.get("missing_questions", []):
                q_uri = EX[f"Question{slug(q)[:80]}"]
                g.add((q_uri, RDF.type, EX.MissingQuestion))
                g.add((q_uri, RDFS.label, Literal(q)))
                g.add((uri, EX.hasMissingQuestion, q_uri))

        self._article_links(legal_db)
        self._domain_links()
        return g

    def _individual(self, label: str, cls: str) -> URIRef:
        uri = EX[slug(label)]
        self.graph.add((uri, RDF.type, EX[cls]))
        self.graph.add((uri, RDFS.label, Literal(label)))
        return uri

    def _article_links(self, legal_db) -> None:
        if not legal_db:
            numbers = ["3", "5", "6", "9", "10", "11", "12", "13", "14", "15", "26", "27", "50", "86"]
            articles = [(n, f"Article {n}") for n in numbers]
        else:
            articles = [(a.number, a.heading or f"Article {a.number}") for a in legal_db.articles_by_number.values()]
        for number, heading in articles:
            uri = EX[f"Article{number}"]
            self.graph.add((uri, RDF.type, EX.AIActArticle))
            self.graph.add((uri, RDFS.label, Literal(f"Article {number}: {heading}")))

    def _domain_links(self) -> None:
        links = [
            ("Article13", "concerns", "Transparency"),
            ("Article14", "concerns", "HumanOversight"),
            ("Article27", "concerns", "FundamentalRightsImpactAssessment"),
            ("Article50", "concerns", "Transparency"),
            ("Article86", "concerns", "RightToExplanation"),
            ("Provider", "hasObligation", "ProvideInstructionsForUse"),
            ("HighRiskAiSystem", "requires", "HumanOversight"),
            ("EmploymentRanking", "mayTrigger", "AnnexIIIEmployment"),
            ("AffectedPerson", "hasRightOrInterest", "Transparency"),
        ]
        for subject, pred, obj in links:
            self.graph.add((EX[subject], EX[pred], EX[obj]))

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
