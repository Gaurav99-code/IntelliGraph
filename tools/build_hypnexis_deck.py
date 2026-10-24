from __future__ import annotations

import copy
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
ET.register_namespace("a", NS["a"])
ET.register_namespace("p", NS["p"])


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".opencode" / "omnirush" / "inbox" / "chat-attachments" / "21b04928a7d0edf4-HYPNEXIS26_Official_PPT_Template.pptx"
OUTPUT = ROOT / "reports" / "IntelliGraph_Hypnexis26_Deck.pptx"


def slides_in(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
    return sorted(names, key=slide_number)


def slide_number(name: str) -> int:
    match = re.search(r"(\d+)", name)
    if match is None:
        raise ValueError(f"Slide number not found in {name}")
    return int(match.group(1))


def shape_by_name(root: ET.Element, name: str) -> ET.Element:
    for shape in root.findall(".//p:sp", NS):
        c_nv_pr = shape.find("./p:nvSpPr/p:cNvPr", NS)
        if c_nv_pr is not None and c_nv_pr.get("name") == name:
            return shape
    raise KeyError(f"Shape not found: {name}")


def text_nodes(shape: ET.Element) -> list[ET.Element]:
    return shape.findall(".//a:t", NS)


def replace_text(shape: ET.Element, text: str) -> None:
    nodes = text_nodes(shape)
    if not nodes:
        raise ValueError("Shape has no text run")
    nodes[0].text = text
    for node in nodes[1:]:
        node.text = ""


def replace_body(shape: ET.Element, items: list[str]) -> None:
    tx_body = shape.find("./p:txBody", NS)
    if tx_body is None:
        raise ValueError("Shape has no text body")
    paragraphs = tx_body.findall("./a:p", NS)
    if not paragraphs:
        raise ValueError("Shape has no paragraphs")
    template = paragraphs[0]
    for paragraph in paragraphs:
        tx_body.remove(paragraph)
    for item in items:
        paragraph = copy.deepcopy(template)
        runs = paragraph.findall(".//a:t", NS)
        if not runs:
            run = ET.SubElement(paragraph, f"{{{NS['a']}}}r")
            ET.SubElement(run, f"{{{NS['a']}}}t").text = item
        else:
            runs[0].text = item
            for run in runs[1:]:
                run.text = ""
        tx_body.append(paragraph)


def set_team_tag(root: ET.Element) -> None:
    replace_text(shape_by_name(root, "Team tag"), "The Nothing  |  u39i29xk")


def update_slide(root: ET.Element, slide_number: int) -> None:
    if slide_number == 1:
        replace_text(shape_by_name(root, "Text 6"), "The Nothing")
        replace_text(shape_by_name(root, "Text 8"), "u39i29xk")
        replace_text(shape_by_name(root, "Text 10"), "Ai-03")
        replace_text(shape_by_name(root, "Text 12"), "Interactive Knowledge Base - Topic-Augmented Knowledge Graph Builder")
        replace_text(shape_by_name(root, "Text 14"), "AI & ML")
        replace_text(shape_by_name(root, "Text 16"), "Software")
        return

    if slide_number == 9:
        replace_text(shape_by_name(root, "Text 1"), "The Nothing  |  u39i29xk  |  IntelliGraph")
        return

    set_team_tag(root)

    if slide_number == 2:
        replace_text(shape_by_name(root, "Text 0"), "Interactive Knowledge Base - Topic-Augmented Knowledge Graph Builder")
        replace_body(shape_by_name(root, "Problem body"), [
            "Knowledge is trapped in long PDFs and scattered notes.",
            "Keyword search misses relationships between topics, entities, and evidence.",
            "Users need fast answers they can trace back to source passages.",
        ])
        replace_body(shape_by_name(root, "Solution body"), [
            "Upload PDFs/text and extract chunks, topics, entities, and relationships.",
            "Combine ChromaDB retrieval with a local JSON graph; Neo4j is optional.",
            "Return grounded answers, citations, source excerpts, and graph evidence.",
        ])
        replace_text(shape_by_name(root, "Image placeholder text"), "UPLOAD  ->  EXTRACT  ->  INDEX  ->  EXPLAIN\nLocal Ollama + citations + graph evidence")

    elif slide_number == 3:
        replace_body(shape_by_name(root, "Arch body"), [
            "Upload PDF/text -> parse and chunk documents",
            "Heuristic or Ollama extraction -> topics, entities, relationships",
            "ChromaDB vectors + JSON graph; optional Neo4j synchronization",
            "Question -> retrieve evidence -> grounded answer + citations",
        ])
        replace_body(shape_by_name(root, "Tech body"), [
            "Python / FastAPI / Pydantic / React / Vite",
            "ChromaDB + sentence-transformers embeddings",
            "Ollama local LLM, optional Neo4j, D3 graph canvas",
        ])
        replace_body(shape_by_name(root, "Unique body"), [
            "Evidence-first answers with validated citation IDs",
            "Works offline with heuristic and extractive fallbacks",
            "Hybrid vector + graph context in one explainable flow",
        ])

    elif slide_number == 4:
        replace_body(shape_by_name(root, "UI body"), [
            "Upload workspace with document list and processing status",
            "Chat answer shows route, confidence, citations, and highlighted excerpts",
            "Interactive graph highlights the nodes and relationships used",
        ])
        replace_text(shape_by_name(root, "Text 9"), "Upload PDFs and inspect extracted documents")
        replace_text(shape_by_name(root, "Text 12"), "Ask a factual or thematic question")
        replace_text(shape_by_name(root, "Text 15"), "Trace the answer to chunks and graph paths")
        replace_body(shape_by_name(root, "Goal body"), [
            "Make complex documents feel navigable: every answer should be understandable, traceable, and one click away from its evidence.",
        ])
        replace_text(shape_by_name(root, "Wireframe placeholder"), "Research workspace\nDocuments  |  Chat  |  Graph\nSee evidence, not just an answer")

    elif slide_number == 5:
        replace_body(shape_by_name(root, "Technical Feasibility body"), [
            "Runs on a commodity laptop with Python, Node, and local storage",
            "Open-source components are already integrated and tested",
            "Modular adapters support future vector, graph, and model upgrades",
        ])
        replace_body(shape_by_name(root, "Economic Feasibility body"), [
            "Prototype runs locally; no paid API is required with Ollama",
            "Open-source stack keeps pilot and maintenance costs low",
            "Future SaaS or enterprise connectors can fund scaling",
        ])
        replace_body(shape_by_name(root, "Operational Viability body"), [
            "Local FastAPI + Vite deployment; JSON fallback keeps demos resilient",
            "Risks: model availability, vector failures, and graph service downtime",
            "Mitigation: retries, caching, fallbacks, health status, and logs",
        ])

    elif slide_number == 6:
        replace_body(shape_by_name(root, "Social Impact body"), [
            "Researchers, students, and teams find answers faster",
            "Citations improve trust and reduce verification time",
            "A visual interface helps non-technical users navigate knowledge",
        ])
        replace_body(shape_by_name(root, "Environmental Impact body"), [
            "Local retrieval reduces repeated cloud calls for the same documents",
            "Chunk caching avoids redundant extraction work",
            "Reusable knowledge reduces duplicated manual analysis",
        ])
        replace_body(shape_by_name(root, "Technical Impact body"), [
            "Grounded generation combines vector search, graph context, and citations",
            "Ollama support enables private local inference",
            "Graceful fallbacks keep the product usable during failures",
        ])
        replace_body(shape_by_name(root, "Educational Impact body"), [
            "Makes relationships in technical material visible",
            "Supports evidence-based learning and research",
            "Demonstrates practical AI/ML system design",
        ])

    elif slide_number == 7:
        replace_body(shape_by_name(root, "Users body"), [
            "Researchers and students working with technical PDFs",
            "Innovation teams, analysts, and knowledge managers",
            "Institutions seeking private document intelligence",
        ])
        replace_body(shape_by_name(root, "Rev body"), [
            "Pilot: free or low-cost deployment for teams",
            "SaaS: per workspace, document, or seat-based plans",
            "Enterprise: connectors, governance, analytics, and support",
        ])
        replace_body(shape_by_name(root, "Sus body"), [
            "Add connectors for drives, wikis, and databases",
            "Expand to domain-specific models and shared workspaces",
            "Keep fallback components open for community adoption",
        ])

    elif slide_number == 8:
        replace_body(shape_by_name(root, "Ref body"), [
            "FastAPI, Pydantic, React, Vite, and D3.js documentation",
            "ChromaDB and sentence-transformers for local vector retrieval",
            "Ollama OpenAI-compatible API for local structured generation",
            "Neo4j Python driver and graph model for optional persistence",
            "Project validation: upload -> query -> citations -> fallback",
        ])


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Template not found: {TEMPLATE}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TEMPLATE, "r") as source:
        files = {name: source.read(name) for name in source.namelist()}
    with zipfile.ZipFile(TEMPLATE, "r") as source:
        slide_names = slides_in(source)
    for slide_name in slide_names:
        slide_number_value = slide_number(slide_name)
        root = ET.fromstring(files[slide_name])
        update_slide(root, slide_number_value)
        files[slide_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as destination:
        for name, content in files.items():
            destination.writestr(name, content)
    print(OUTPUT)


if __name__ == "__main__":
    main()
