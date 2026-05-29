from pathlib import Path
from rdflib import Graph, RDFS

from app.ontology.ontology_builder import EX, OntologyBuilder, slug


class OntologyStore:
    def __init__(self, seed_concepts_path: Path, seed_annexes_path: Path, legal_db=None):
        self.graph = OntologyBuilder().build(seed_concepts_path, seed_annexes_path, legal_db)

    def get_graph(self) -> Graph:
        return self.graph

    def serialize_turtle(self) -> str:
        return self.graph.serialize(format="turtle")

    def serialize_jsonld(self) -> str:
        return self.graph.serialize(format="json-ld", indent=2)

    def find_articles_for_concept(self, concept: str) -> list[str]:
        target = EX[slug(concept)]
        articles = []
        for article, _, _ in self.graph.triples((None, EX.concerns, target)):
            label = self.graph.value(article, RDFS.label)
            articles.append(str(label or article))
        return articles

    def find_related_risks(self, concept: str) -> list[str]:
        subject = EX[slug(concept)]
        return [str(self.graph.value(risk, RDFS.label) or risk) for _, _, risk in self.graph.triples((subject, EX.hasRisk, None))]

    def find_related_questions(self, concept: str) -> list[str]:
        subject = EX[slug(concept)]
        return [str(self.graph.value(q, RDFS.label) or q) for _, _, q in self.graph.triples((subject, EX.hasMissingQuestion, None))]
