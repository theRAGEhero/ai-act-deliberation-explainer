from __future__ import annotations

import re
from pathlib import Path
from lxml import etree

from app.models import LegalArticle, LegalCorpus, LegalDefinition, LegalParagraph


class AKNParser:
    """Robust, namespace-aware parser for Akoma Ntoso AI Act XML."""

    def parse_file(self, path: str | Path) -> LegalCorpus:
        source = Path(path)
        corpus = LegalCorpus(source_path=str(source))
        if not source.exists():
            corpus.warnings.append(f"AKN file not found: {source}")
            return corpus

        parser = etree.XMLParser(recover=True, huge_tree=True, remove_blank_text=True)
        try:
            root = etree.parse(str(source), parser).getroot()
        except Exception as exc:
            corpus.warnings.append(f"Could not parse AKN XML: {exc}")
            return corpus

        ns = {"akn": root.nsmap.get(None, "http://docs.oasis-open.org/legaldocml/ns/akn/3.0")}
        articles = root.xpath(".//akn:article", namespaces=ns)
        for node in articles:
            article = self._parse_article(node, source, ns)
            if article:
                corpus.articles.append(article)
                if article.number == "3":
                    corpus.definitions.extend(self._extract_definitions(node, ns))
        return corpus

    def _parse_article(self, node, source: Path, ns: dict[str, str]) -> LegalArticle | None:
        number_text = self._first_text(node, "./akn:num", ns)
        number = self._article_number(number_text) or self._article_number(node.get("eId", ""))
        if not number:
            return None
        heading = self._clean(self._first_text(node, "./akn:heading", ns))
        paragraphs: list[LegalParagraph] = []
        for para in node.xpath("./akn:paragraph|./akn:content/akn:p|./akn:list/akn:item", namespaces=ns):
            text = self._clean(" ".join(para.itertext()))
            if not text:
                continue
            paragraphs.append(
                LegalParagraph(
                    eId=para.get("eId") or para.get("{http://www.w3.org/XML/1998/namespace}id"),
                    number=self._clean(self._first_text(para, "./akn:num", ns)),
                    text=text,
                )
            )
        text = self._clean(" ".join(node.itertext()))
        return LegalArticle(
            eId=node.get("eId") or node.get("{http://www.w3.org/XML/1998/namespace}id"),
            number=number,
            heading=heading or None,
            text=text,
            paragraphs=paragraphs,
            source_path=str(source),
        )

    def _extract_definitions(self, article_node, ns: dict[str, str]) -> list[LegalDefinition]:
        definitions: list[LegalDefinition] = []
        candidates = article_node.xpath(".//akn:point|.//akn:paragraph|.//akn:item", namespaces=ns)
        for node in candidates:
            text = self._clean(" ".join(node.itertext()))
            if not text:
                continue
            match = re.search(r"[‘'“\"]([^’'”\"]{2,80})[’'”\"]\s+means\s+(.+)", text, re.I)
            if match:
                definitions.append(
                    LegalDefinition(
                        term=self._clean(match.group(1)),
                        text=self._clean(match.group(2)),
                        eId=node.get("eId"),
                    )
                )
        return definitions

    def _first_text(self, node, xpath: str, ns: dict[str, str]) -> str:
        found = node.xpath(xpath, namespaces=ns)
        return " ".join(found[0].itertext()) if found else ""

    def _article_number(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"Article\s*[\u00a0 ]*(\d+)|art[_-](\d+)|__art_(\d+)", value, re.I)
        if match:
            return next(group for group in match.groups() if group)
        if value.strip().isdigit():
            return value.strip()
        return None

    def _clean(self, text: str | None) -> str:
        return re.sub(r"\s+", " ", text or "").strip().strip("`")
