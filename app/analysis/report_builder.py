from __future__ import annotations

from app.models import AnalysisResponse, GraphView, PreliminaryAnalysis

DISCLAIMER = "This is a preliminary legal-design analysis for discussion and education. It is not legal advice and does not certify AI Act compliance."


class ReportBuilder:
    def build(self, preliminary: PreliminaryAnalysis, rdf_preview: str, llm_output: dict | None = None) -> AnalysisResponse:
        citizen = self._citizen_explanation(preliminary)
        markdown = self._markdown(preliminary)
        graph = self._graph(preliminary)
        return AnalysisResponse(
            case_summary=preliminary.case_summary,
            detected_actors=preliminary.detected_actors,
            detected_contexts=preliminary.detected_contexts,
            detected_ai_functions=preliminary.detected_ai_functions,
            possible_risks=preliminary.possible_risks,
            possible_rights_or_interests=preliminary.possible_rights_or_interests,
            obligations_to_verify=preliminary.obligations_to_verify,
            missing_questions=preliminary.missing_questions,
            relevant_ai_act_sources=preliminary.relevant_ai_act_sources,
            traceability=preliminary.traceability,
            citizen_explanation=llm_output.get("citizen_explanation") if llm_output and llm_output.get("citizen_explanation") else citizen,
            disclaimer=DISCLAIMER,
            raw_rule_output=preliminary.model_dump(),
            rdf_triples_preview=rdf_preview,
            markdown_summary=markdown,
            graph=graph,
        )

    def _citizen_explanation(self, analysis: PreliminaryAnalysis) -> str:
        risks = ", ".join(item.label for item in analysis.possible_risks[:5]) or "no strong risk signal detected"
        sources = ", ".join(f"Article {src.article_number}" for src in analysis.relevant_ai_act_sources[:6])
        return f"The text may involve AI Act issues such as {risks}. The sources to verify include {sources}. These are discussion prompts, not conclusions."

    def _markdown(self, analysis: PreliminaryAnalysis) -> str:
        return "\n".join(
            [
                f"## {analysis.case_summary}",
                "",
                "**Possible risks:** " + ", ".join(item.label for item in analysis.possible_risks),
                "**Rights/interests:** " + ", ".join(item.label for item in analysis.possible_rights_or_interests),
                "**Sources:** " + ", ".join(f"Article {src.article_number}" for src in analysis.relevant_ai_act_sources),
            ]
        )

    def _graph(self, analysis: PreliminaryAnalysis) -> GraphView:
        nodes, edges, seen = [], [], set()

        def add_node(node_id: str, label: str, kind: str):
            if node_id not in seen:
                seen.add(node_id)
                nodes.append({"id": node_id, "label": label, "type": kind})

        add_node("scenario", "Scenario", "scenario")
        for group, kind, relation in [
            (analysis.detected_actors, "actor", "has_actor"),
            (analysis.possible_risks, "risk", "may_create"),
            (analysis.possible_rights_or_interests, "right", "affects"),
            (analysis.obligations_to_verify, "obligation", "requires_verification"),
        ]:
            for item in group:
                node_id = item.label.lower().replace(" ", "_").replace("/", "_")
                add_node(node_id, item.label, kind)
                edges.append({"source": "scenario", "target": node_id, "label": relation})
        for src in analysis.relevant_ai_act_sources[:8]:
            node_id = f"article_{src.article_number}"
            add_node(node_id, f"Article {src.article_number}", "article")
            edges.append({"source": "scenario", "target": node_id, "label": "linked_to"})
        return GraphView(nodes=nodes, edges=edges)
