from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef


AID = Namespace("http://example.org/ai-act-deliberation#")
CIRSFID_AI = Namespace("https://cirsfid.unibo.it/ontology/ai-act/property/")
CIRSFID_PROH = Namespace("https://cirsfid.unibo.it/ontology/ai-act/prohibited-practice/")
CIRSFID_MOD = Namespace("https://cirsfid.unibo.it/ontology/ai-act/modifier/")
CIRSFID_AKN = Namespace("https://cirsfid.unibo.it/akn/eu/ai-act/")


class LegalOntologyStatus(BaseModel):
    loaded: bool = False
    is_valid: bool = False
    directory: str
    files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LegalOntologyStore:
    REQUIRED_CLASSES = ["ProhibitedPractice", "LegalElement", "Exception", "Right"]
    REQUIRED_PROPERTIES = ["prohibitedBy", "requiresElement", "hasException", "affectsRight", "hasSourceAnchor"]
    CIRSFID_REQUIRED_CLASSES = [CIRSFID_PROH.ProhibitedPractice, CIRSFID_MOD.Exception]
    CIRSFID_REQUIRED_PROPERTIES = [
        CIRSFID_AI.legalSource,
        CIRSFID_AI.usesSystem,
        CIRSFID_AI.affectsRight,
        CIRSFID_AI.requiresCondition,
        CIRSFID_AI.hasException,
    ]
    ELEMENT_OBJECT_PROPERTIES = [
        CIRSFID_AI.usesSystem,
        CIRSFID_AI.targets,
        CIRSFID_AI.occursInContext,
        CIRSFID_AI.performedBy,
        CIRSFID_AI.requiresCondition,
    ]
    ELEMENT_DATA_PROPERTIES = [
        CIRSFID_AI.materiallyDistortsBehaviour,
        CIRSFID_AI.impairsInformedDecisionMaking,
        CIRSFID_AI.causesHarm,
        CIRSFID_AI.likelyToCauseHarm,
        CIRSFID_AI.classifiesPerson,
        CIRSFID_AI.evaluatesPerson,
        CIRSFID_AI.infersCharacteristic,
        CIRSFID_AI.usesBiometricData,
        CIRSFID_AI.usesFacialImages,
        CIRSFID_AI.usesProfiling,
        CIRSFID_AI.prohibitedWhen,
        CIRSFID_AI.notProhibitedWhen,
    ]

    def __init__(self, ontology_dir: str | Path):
        self.ontology_dir = Path(ontology_dir)
        self.graph = Graph()
        self.graph.bind("aid", AID)
        self.graph.bind("ai", CIRSFID_AI)
        self.graph.bind("proh", CIRSFID_PROH)
        self.status = LegalOntologyStatus(directory=str(self.ontology_dir))
        self.load()

    def load(self) -> None:
        if not self.ontology_dir.exists():
            self.status.warnings.append(f"Legal ontology directory not found: {self.ontology_dir}")
            return
        files = sorted(self.ontology_dir.glob("*.ttl"))
        self.status.files = [str(path) for path in files]
        if not files:
            self.status.warnings.append(f"No .ttl legal ontology files found in {self.ontology_dir}")
            return
        for path in files:
            try:
                self.graph.parse(path, format="turtle")
            except Exception as exc:
                self.status.errors.append(f"Could not parse {path}: {exc}")
        self.status.loaded = len(self.graph) > 0 and not self.status.errors
        self.status.is_valid = self.validate()

    def validate(self) -> bool:
        has_aid_vocab = (AID.ProhibitedPractice, RDF.type, RDFS.Class) in self.graph
        has_cirsfid_vocab = (CIRSFID_PROH.ProhibitedPractice, RDF.type, OWL.Class) in self.graph or (
            CIRSFID_PROH.ProhibitedPractice,
            RDF.type,
            RDFS.Class,
        ) in self.graph
        if has_cirsfid_vocab:
            self._validate_cirsfid()
            self._warn_if_omnibus_present()
            return self.status.loaded and not self.status.errors
        if not has_aid_vocab:
            self.status.errors.append("Missing supported ontology vocabulary: expected CIRSFID Article 5 vocabulary or aid test vocabulary")
            return False
        for class_name in self.REQUIRED_CLASSES:
            subject = AID[class_name]
            if not ((subject, RDF.type, RDFS.Class) in self.graph or (subject, RDF.type, AID.Class) in self.graph):
                self.status.errors.append(f"Missing required ontology class: aid:{class_name}")
        for property_name in self.REQUIRED_PROPERTIES:
            subject = AID[property_name]
            if (subject, RDF.type, RDF.Property) not in self.graph:
                self.status.errors.append(f"Missing required ontology property: aid:{property_name}")
        return self.status.loaded and not self.status.errors

    def get_graph(self) -> Graph:
        return self.graph

    def serialize_turtle(self) -> str:
        return self.graph.serialize(format="turtle") if self.status.loaded else ""

    def serialize_jsonld(self) -> str:
        return self.graph.serialize(format="json-ld", indent=2) if self.status.loaded else "[]"

    def get_prohibited_practices(self) -> list[dict[str, Any]]:
        aid_practices = [self._resource(subject) for subject in self.graph.subjects(RDF.type, AID.ProhibitedPractice)]
        cirsfid_practices = [self._resource(subject) for subject in self.graph.subjects(RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice)]
        return aid_practices + cirsfid_practices

    def get_practice(self, practice_id: str) -> dict[str, Any] | None:
        subject = self._resolve_resource(practice_id)
        if not subject or not self._is_prohibited_practice(subject):
            return None
        return self._resource(subject)

    def get_required_elements(self, practice_id: str) -> list[dict[str, Any]]:
        subject = self._resolve_resource(practice_id)
        if subject and (subject, RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice) in self.graph:
            return self._cirsfid_required_elements(subject)
        return self._linked_resources(practice_id, AID.requiresElement)

    def get_exceptions(self, practice_id: str) -> list[dict[str, Any]]:
        subject = self._resolve_resource(practice_id)
        if subject and (subject, RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice) in self.graph:
            return [self._resource(obj) for obj in self._objects(subject, CIRSFID_AI.hasException, CIRSFID_PROH.hasException) if isinstance(obj, URIRef)]
        return self._linked_resources(practice_id, AID.hasException)

    def get_affected_rights(self, practice_id: str) -> list[dict[str, Any]]:
        subject = self._resolve_resource(practice_id)
        if subject and (subject, RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice) in self.graph:
            return [self._resource(obj) for obj in self.graph.objects(subject, CIRSFID_AI.affectsRight) if isinstance(obj, URIRef)]
        return self._linked_resources(practice_id, AID.affectsRight)

    def get_source_anchors(self, practice_id: str) -> list[dict[str, Any]]:
        subject = self._resolve_resource(practice_id)
        if subject and (subject, RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice) in self.graph:
            return [self._resource(obj) for obj in self.graph.objects(subject, CIRSFID_AI.legalSource) if isinstance(obj, URIRef)]
        return self._linked_resources(practice_id, AID.hasSourceAnchor)

    def get_required_conditions(self, resource_id: str) -> list[dict[str, Any]]:
        subject = self._resolve_resource(resource_id)
        if not subject:
            return []
        return [self._resource(obj) for obj in self.graph.objects(subject, CIRSFID_AI.requiresCondition) if isinstance(obj, URIRef)]

    def is_current_law_practice(self, practice_id: str) -> bool:
        anchors = self.get_source_anchors(practice_id)
        return bool(anchors) and all(anchor.get("legal_status") == "current_binding_law" for anchor in anchors)

    def _linked_resources(self, practice_id: str, predicate: URIRef) -> list[dict[str, Any]]:
        subject = self._resolve_resource(practice_id)
        if not subject:
            return []
        return [self._resource(obj) for obj in self.graph.objects(subject, predicate) if isinstance(obj, URIRef)]

    def _resolve_resource(self, resource_id: str) -> URIRef | None:
        if resource_id.startswith("http://") or resource_id.startswith("https://"):
            return URIRef(resource_id)
        candidate = AID[resource_id]
        if (candidate, None, None) in self.graph or (None, None, candidate) in self.graph:
            return candidate
        for subject in self.graph.subjects():
            if isinstance(subject, URIRef) and str(subject).rstrip("/#").split("#")[-1] == resource_id:
                return subject
            if isinstance(subject, URIRef) and str(subject).rstrip("/").split("/")[-1] == resource_id:
                return subject
        return None

    def _resource(self, subject: URIRef) -> dict[str, Any]:
        return {
            "id": self._local_id(subject),
            "uri": str(subject),
            "label": self._literal(subject, RDFS.label) or self._humanize(self._local_id(subject)),
            "source": self._literal(subject, AID.sourceText) or self._literal(subject, AID.source),
            "element_type": self._literal(subject, AID.elementType),
            "requirement_type": self._literal(subject, AID.requirementType) or "required",
            "source_anchor": self._literal(subject, AID.sourceAnchor) or self._literal(subject, CIRSFID_AI.sourceAnchor),
            "is_omnibus": self._is_omnibus_source(subject),
            "legal_status": "proposed_or_amending_material" if self._is_omnibus_source(subject) else "current_binding_law",
            "current_binding_law": self._current_binding_law(subject),
        }

    def _literal(self, subject: URIRef, predicate: URIRef) -> str | None:
        for value in self.graph.objects(subject, predicate):
            if isinstance(value, Literal):
                return str(value)
            if isinstance(value, URIRef):
                return str(value)
        return None

    def _validate_cirsfid(self) -> None:
        for class_uri in self.CIRSFID_REQUIRED_CLASSES:
            if not ((class_uri, RDF.type, OWL.Class) in self.graph or (class_uri, RDF.type, RDFS.Class) in self.graph):
                self.status.errors.append(f"Missing required CIRSFID ontology class: {class_uri}")
        for property_uri in self.CIRSFID_REQUIRED_PROPERTIES:
            if not ((property_uri, RDF.type, OWL.ObjectProperty) in self.graph or (property_uri, RDF.type, RDF.Property) in self.graph):
                self.status.errors.append(f"Missing required CIRSFID ontology property: {property_uri}")
        if not list(self.graph.subjects(RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice)):
            self.status.errors.append("No CIRSFID prohibited practice subclasses found")
        if not list(self.graph.objects(None, CIRSFID_AI.legalSource)):
            self.status.errors.append("No CIRSFID legal source anchors found")

    def _warn_if_omnibus_present(self) -> None:
        omnibus = [str(source) for source in self.graph.subjects(CIRSFID_AI.insertedBy, CIRSFID_AKN.OmnibusAIAct)]
        if omnibus:
            self.status.warnings.append("Ontology contains Omnibus/proposed amendment material; current-law analysis must distinguish it from Regulation (EU) 2024/1689.")

    def _is_prohibited_practice(self, subject: URIRef) -> bool:
        return (subject, RDF.type, AID.ProhibitedPractice) in self.graph or (subject, RDFS.subClassOf, CIRSFID_PROH.ProhibitedPractice) in self.graph

    def _cirsfid_required_elements(self, practice: URIRef) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for predicate in self.ELEMENT_OBJECT_PROPERTIES:
            for obj in self.graph.objects(practice, predicate):
                if isinstance(obj, URIRef):
                    elements.append(self._element_resource(practice, predicate, obj, "object"))
        for predicate in self.ELEMENT_DATA_PROPERTIES:
            for obj in self.graph.objects(practice, predicate):
                elements.append(self._element_resource(practice, predicate, obj, "data"))
        return elements

    def _element_resource(self, practice: URIRef, predicate: URIRef, obj, element_type: str) -> dict[str, Any]:
        obj_id = self._local_id(obj) if isinstance(obj, URIRef) else str(obj)
        pred_label = self._humanize(self._local_id(predicate))
        obj_label = self._resource(obj)["label"] if isinstance(obj, URIRef) else str(obj)
        return {
            "id": f"{self._local_id(practice)}__{self._local_id(predicate)}__{obj_id}".replace(" ", "_"),
            "uri": str(obj) if isinstance(obj, URIRef) else "",
            "label": f"{pred_label}: {obj_label}",
            "source": None,
            "element_type": element_type,
            "requirement_type": "required",
            "source_anchor": None,
        }

    def _objects(self, subject: URIRef, *predicates: URIRef):
        seen = set()
        for predicate in predicates:
            for obj in self.graph.objects(subject, predicate):
                if obj not in seen:
                    seen.add(obj)
                    yield obj

    def _local_id(self, value) -> str:
        text = str(value)
        if "#" in text:
            return text.rsplit("#", 1)[-1]
        return text.rstrip("/").rsplit("/", 1)[-1]

    def _humanize(self, value: str) -> str:
        import re

        value = value.replace("_", " ")
        value = re.sub(r"(?<!^)([A-Z])", r" \1", value)
        return re.sub(r"\s+", " ", value).strip()

    def _is_omnibus_source(self, subject: URIRef) -> bool:
        if subject == CIRSFID_AKN.OmnibusAIAct or (subject, CIRSFID_AI.insertedBy, CIRSFID_AKN.OmnibusAIAct) in self.graph:
            return True
        return any(source == CIRSFID_AKN.OmnibusAIAct for source in self.graph.objects(subject, CIRSFID_AI.insertedBy))

    def _current_binding_law(self, subject: URIRef) -> bool:
        for value in self.graph.objects(subject, CIRSFID_AI.currentBindingLaw):
            if isinstance(value, Literal):
                return str(value).lower() in {"true", "1"}
        return not self._is_omnibus_source(subject)
