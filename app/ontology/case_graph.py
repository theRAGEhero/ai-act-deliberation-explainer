from __future__ import annotations

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from app.models import PreliminaryAnalysis


AID = Namespace("http://example.org/ai-act-deliberation#")
CASE = Namespace("http://example.org/ai-act-case#")


class CaseGraphBuilder:
    def build(self, analysis: PreliminaryAnalysis) -> Graph:
        graph = Graph()
        graph.bind("aid", AID)
        graph.bind("case", CASE)
        scenario = CASE["scenario"]
        graph.add((scenario, RDF.type, AID.Scenario))
        graph.add((scenario, RDFS.label, Literal(analysis.case_summary)))
        for index, match in enumerate(analysis.matched_prohibited_practices, start=1):
            practice = CASE[f"practice_{match.id}"]
            graph.add((practice, RDF.type, AID.ProhibitedPractice))
            graph.add((practice, RDFS.label, Literal(match.label)))
            graph.add((scenario, AID.hasCandidatePractice, practice))
            for element in match.legal_elements:
                element_node = CASE[f"element_{match.id}_{element.id}"]
                graph.add((element_node, RDF.type, AID.LegalElement))
                graph.add((element_node, RDFS.label, Literal(element.label)))
                graph.add((element_node, AID.status, Literal(element.status)))
                graph.add((practice, AID.requiresElement, element_node))
                for evidence_index, evidence in enumerate(element.evidence, start=1):
                    evidence_node = CASE[f"evidence_{index}_{evidence_index}"]
                    graph.add((evidence_node, RDF.type, AID.EvidenceSnippet))
                    graph.add((evidence_node, RDFS.label, Literal(evidence.snippet)))
                    graph.add((element_node, AID.supportedBy, evidence_node))
            for anchor in match.source_anchors:
                anchor_node = URIRef(CASE[f"source_{anchor.eId or anchor.article}"])
                graph.add((anchor_node, RDF.type, AID.SourceAnchor))
                graph.add((anchor_node, RDFS.label, Literal(anchor.label)))
                graph.add((practice, AID.hasSourceAnchor, anchor_node))
        return graph

    def serialize_turtle(self, analysis: PreliminaryAnalysis) -> str:
        return self.build(analysis).serialize(format="turtle")
