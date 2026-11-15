import xml.etree.ElementTree as ET
from typing import List
from src.models import FeedSource

def parse_opml(file_path: str) -> List[FeedSource]:
    """
    Parses an OPML file and yields all RSS/Atom feed sources without altering URLs.
    Handles nested outline categories.
    """
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as e:
        raise ValueError(f"Malformed OPML XML file: {e}")

    root = tree.getroot()
    body = root.find("body")
    if body is None:
        raise ValueError("Invalid OPML format: <body> element missing.")

    sources: List[FeedSource] = []

    def _extract_outlines(element: ET.Element, current_category: str):
        for outline in element.findall("outline"):
            text = outline.attrib.get("text") or outline.attrib.get("title") or "Unknown"
            xml_url = outline.attrib.get("xmlUrl")
            type_attr = outline.attrib.get("type")

            if xml_url and type_attr == "rss":
                sources.append(
                    FeedSource(
                        name=text,
                        xml_url=xml_url,
                        category=current_category
                    )
                )
            else:
                # Treat as category folder and traverse deeper
                nested_category = outline.attrib.get("title") or text
                _extract_outlines(outline, nested_category)

    _extract_outlines(body, "Uncategorized")
    return sources