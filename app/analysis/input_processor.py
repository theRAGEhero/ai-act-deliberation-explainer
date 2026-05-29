import re
from collections import Counter

from app.models import CaseInput


STOPWORDS = {"the", "and", "for", "with", "that", "this", "will", "use", "using", "from", "are", "but"}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def split_into_sentences_or_claims(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+|;", normalize_text(text))
    return [part.strip() for part in parts if part.strip()]


def extract_candidate_keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text.lower())
    counts = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _ in counts.most_common(30)]


def build_case_input(text: str, title: str | None = None, persona: str | None = "citizen") -> CaseInput:
    clean = normalize_text(text)
    return CaseInput(
        raw_text=clean,
        title=title or _infer_title(clean),
        persona=persona or "citizen",
        claims=split_into_sentences_or_claims(clean),
        keywords=extract_candidate_keywords(clean),
    )


def _infer_title(text: str) -> str:
    first = split_into_sentences_or_claims(text)[:1]
    return (first[0][:90] if first else "Untitled scenario").strip()
