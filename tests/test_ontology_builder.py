from pathlib import Path

from rdflib import RDF

from app.ontology.ontology_builder import EX, OntologyBuilder


def test_ontology_builds_and_serializes():
    graph = OntologyBuilder().build(Path("data/supporting/seed_concepts.json"), Path("data/supporting/seed_annexes.json"))
    assert (EX.Provider, RDF.type, EX.Actor) in graph
    assert (EX.Deployer, RDF.type, EX.Actor) in graph
    assert (EX.HumanOversight, RDF.type, EX.Concept) in graph
    assert "@prefix" in graph.serialize(format="turtle")
