from pathlib import Path
from rdflib import Graph


def export_graph(graph: Graph, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    turtle = output_dir / "ontology.ttl"
    jsonld = output_dir / "ontology.jsonld"
    turtle.write_text(graph.serialize(format="turtle"), encoding="utf-8")
    jsonld.write_text(graph.serialize(format="json-ld", indent=2), encoding="utf-8")
    return turtle, jsonld
