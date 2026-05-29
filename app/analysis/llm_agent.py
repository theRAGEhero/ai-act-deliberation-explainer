from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.analysis.prompt_templates import SYSTEM_PROMPT, USER_PROMPT


class OptionalLLMAgent:
    def available(self) -> bool:
        return bool(settings.openai_api_key)

    def refine(self, input_text: str, preliminary: dict[str, Any], legal_sources: list[dict[str, Any]], ontology_concepts: list[str]) -> dict[str, Any] | None:
        if not self.available():
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
            prompt = USER_PROMPT.format(
                input_text=input_text,
                preliminary_json=json.dumps(preliminary, ensure_ascii=False),
                legal_sources=json.dumps(legal_sources, ensure_ascii=False),
                ontology_concepts=json.dumps(ontology_concepts, ensure_ascii=False),
            )
            response = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return None
