from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


@dataclass
class SourceNode:
    article: str
    text: str
    heading: str | None = None
    paragraph: str | None = None
    point: str | None = None
    eId: str | None = None
    label: str = ""
    frbr_uri: str | None = None
    celex: str | None = None


class LegalSourceIndex:
    def __init__(self, xml_path: str | Path):
        self.xml_path = Path(xml_path)
        self.ns = {"akn": AKN_NS}
        self.articles: dict[str, SourceNode] = {}
        self.points: dict[tuple[str, str | None, str], SourceNode] = {}
        self.eids: dict[str, SourceNode] = {}
        self.definitions_by_number: dict[str, SourceNode] = {}
        self.definitions_by_term: dict[str, SourceNode] = {}
        self.frbr_uri: str | None = None
        self.celex: str | None = None
        self.is_loaded = False
        self.errors: list[str] = []
        self._load()

    def get_article(self, number: str) -> SourceNode | None:
        return self.articles.get(str(number))

    def get_article_point(self, article: str, paragraph: str, point: str) -> SourceNode | None:
        return self.points.get((str(article), str(paragraph) if paragraph else None, str(point).lower()))

    def get_eid(self, eid: str) -> SourceNode | None:
        return self.eids.get(eid)

    def get_article_5_points(self) -> list[SourceNode]:
        return [node for key, node in sorted(self.points.items()) if key[0] == "5"]

    def get_article_3_definitions(self) -> list[SourceNode]:
        return list(self.definitions_by_number.values())

    def get_definition_by_number(self, number: str) -> SourceNode | None:
        return self.definitions_by_number.get(str(number))

    def get_definition_by_term(self, term: str) -> SourceNode | None:
        return self.definitions_by_term.get(term.casefold())

    def _load(self) -> None:
        if not self.xml_path.exists():
            self.errors.append(f"AKN XML file not found: {self.xml_path}")
            return
        try:
            parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=True)
            root = etree.parse(str(self.xml_path), parser).getroot()
        except Exception as exc:
            self.errors.append(f"Could not parse AKN XML: {exc}")
            return

        self.frbr_uri = self._first_attr(root, ".//akn:FRBRWork/akn:FRBRuri", "value")
        self.celex = self._first_attr(root, ".//akn:FRBRWork/akn:FRBRalias[@name='CELEX']", "value")
        for article_node in root.xpath(".//akn:article", namespaces=self.ns):
            number = self._article_number(self._first_text(article_node, "./akn:num")) or self._article_number(article_node.get("eId", ""))
            if not number:
                continue
            article = SourceNode(
                article=number,
                heading=self._clean(self._first_text(article_node, "./akn:heading")) or None,
                text=self._clean(" ".join(article_node.itertext())),
                eId=self._eid(article_node),
                label=f"Article {number}",
                frbr_uri=self.frbr_uri,
                celex=self.celex,
            )
            self.articles[number] = article
            if article.eId:
                self.eids[article.eId] = article
            self._index_points(number, article_node)
            if number == "3":
                self._index_definitions(article_node)
        self.is_loaded = bool(self.articles)

    def _index_points(self, article: str, article_node) -> None:
        for para in article_node.xpath("./akn:paragraph", namespaces=self.ns):
            paragraph = self._article_number(self._first_text(para, "./akn:num")) or self._paragraph_from_eid(self._eid(para))
            for point in para.xpath(".//akn:point", namespaces=self.ns):
                point_label = self._point_label(point)
                if not point_label:
                    continue
                node = SourceNode(
                    article=article,
                    paragraph=paragraph,
                    point=point_label,
                    heading=self.articles.get(article).heading if article in self.articles else None,
                    text=self._clean(" ".join(point.itertext())),
                    eId=self._eid(point),
                    label=f"Article {article}({paragraph})({point_label})" if paragraph else f"Article {article}({point_label})",
                    frbr_uri=self.frbr_uri,
                    celex=self.celex,
                )
                self.points[(article, paragraph, point_label.lower())] = node
                if node.eId:
                    self.eids[node.eId] = node

    def _index_definitions(self, article_node) -> None:
        for point in article_node.xpath(".//akn:point", namespaces=self.ns):
            number = self._normalize_point(self._first_text(point, "./akn:num"))
            if not number:
                continue
            text = self._clean(" ".join(point.itertext()))
            term = self._definition_term(text)
            node = SourceNode(
                article="3",
                paragraph="1",
                point=number,
                heading="Definitions",
                text=text,
                eId=self._eid(point),
                label=f"Article 3({number})",
                frbr_uri=self.frbr_uri,
                celex=self.celex,
            )
            self.definitions_by_number[number] = node
            if term:
                self.definitions_by_term[term.casefold()] = node
            if node.eId:
                self.eids[node.eId] = node

    def _first_text(self, node, xpath: str) -> str:
        found = node.xpath(xpath, namespaces=self.ns)
        return " ".join(found[0].itertext()) if found else ""

    def _first_attr(self, node, xpath: str, attr: str) -> str | None:
        found = node.xpath(xpath, namespaces=self.ns)
        return found[0].get(attr) if found else None

    def _eid(self, node) -> str | None:
        return node.get("eId") or node.get(XML_ID)

    def _article_number(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"Article\s*[\u00a0 ]*(\d+)|art[_-](\d+)|para_(\d+)|^\(?([0-9]+)\)?$", value, re.I)
        if match:
            return next(group for group in match.groups() if group)
        return None

    def _paragraph_from_eid(self, eid: str | None) -> str | None:
        match = re.search(r"para_(\d+)", eid or "")
        return match.group(1) if match else None

    def _point_from_eid(self, eid: str | None) -> str | None:
        match = re.search(r"point_([a-z]+|[ivx]+)$", eid or "", re.I)
        return match.group(1).lower() if match else None

    def _point_label(self, point) -> str | None:
        own = self._normalize_point(self._first_text(point, "./akn:num")) or self._point_from_eid(self._eid(point))
        parent_points = point.xpath("ancestor::akn:point", namespaces=self.ns)
        if parent_points:
            parent = parent_points[-1]
            parent_label = self._normalize_point(self._first_text(parent, "./akn:num")) or self._point_from_eid(self._eid(parent))
            if parent_label and own:
                return f"{parent_label}.{own}"
        return own

    def _normalize_point(self, value: str | None) -> str | None:
        cleaned = self._clean(value).strip("()").lower()
        return cleaned or None

    def _definition_term(self, text: str) -> str | None:
        match = re.search(r"[‘'“\"]([^’'”\"]{2,100})[’'”\"]\s+means", text, re.I)
        return self._clean(match.group(1)) if match else None

    def _clean(self, text: str | None) -> str:
        return re.sub(r"\s+", " ", text or "").strip()
