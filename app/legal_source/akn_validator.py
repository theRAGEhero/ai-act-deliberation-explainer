from __future__ import annotations

from pathlib import Path

from lxml import etree
from pydantic import BaseModel, Field


class AKNValidationResult(BaseModel):
    is_valid: bool = False
    attempted: bool = False
    xml_path: str
    xsd_path: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LocalSchemaResolver(etree.Resolver):
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir

    def resolve(self, url, pubid, context):
        candidate = self.base_dir / Path(url).name
        if candidate.exists():
            return self.resolve_filename(str(candidate), context)
        return None


def validate_akn_xml(xml_path: str | Path, xsd_path: str | Path, xml_xsd_path: str | Path | None = None) -> AKNValidationResult:
    xml = Path(xml_path)
    xsd = Path(xsd_path)
    result = AKNValidationResult(xml_path=str(xml), xsd_path=str(xsd))

    if not xml.exists():
        result.warnings.append(f"AKN XML file not found: {xml}")
        return result
    if not xsd.exists():
        result.warnings.append(f"Akoma Ntoso XSD file not found: {xsd}")
        return result
    if xml_xsd_path and not Path(xml_xsd_path).exists():
        result.warnings.append(f"Imported XML namespace schema not found: {xml_xsd_path}")
        return result

    result.attempted = True
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    parser.resolvers.add(LocalSchemaResolver(xsd.parent))
    if xml_xsd_path:
        parser.resolvers.add(LocalSchemaResolver(Path(xml_xsd_path).parent))
    try:
        schema_doc = etree.parse(str(xsd), parser)
        schema = etree.XMLSchema(schema_doc)
        xml_doc = etree.parse(str(xml), parser)
        result.is_valid = bool(schema.validate(xml_doc))
        if not result.is_valid:
            result.errors.extend(str(error) for error in schema.error_log)
    except Exception as exc:
        result.is_valid = False
        result.errors.append(str(exc))
    return result
