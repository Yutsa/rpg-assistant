from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from rpg_core.models.raw import BBox

NodeDepth = Literal["block", "line", "span"]
NodeType = Literal["text", "image"]


@dataclass
class LayoutNode:
    id: str
    depth: NodeDepth
    node_type: NodeType
    parent_id: str | None
    block_index: int
    line_index: int | None
    span_index: int | None
    text: str
    bbox: BBox
    metadata: dict[str, Any]


def _bbox_from_tuple(coords: tuple[float, ...] | list[float]) -> BBox:
    return BBox(x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3])


def _span_text(span: dict[str, Any]) -> str:
    return span.get("text", "")


def _line_metadata(line: dict[str, Any]) -> dict[str, Any]:
    spans = line.get("spans") or []
    if not spans:
        return {}
    primary = max(spans, key=lambda span: len(span.get("text", "")))
    return {
        "font_size": primary.get("size"),
        "font_flags": primary.get("flags"),
        "font_name": primary.get("font"),
    }


def _line_text(line: dict[str, Any]) -> str:
    return "".join(_span_text(span) for span in line.get("spans") or [])


def _block_text(block: dict[str, Any]) -> str:
    lines = block.get("lines") or []
    return "\n".join(_line_text(line).strip() for line in lines if _line_text(line).strip())


def flatten_raw_layout(
    raw_layout: dict[str, Any],
    *,
    level: NodeDepth | None = None,
    node_type: NodeType | None = None,
) -> list[LayoutNode]:
    """Flatten a PyMuPDF page dict into overlay-friendly nodes."""
    nodes: list[LayoutNode] = []
    for block_index, block in enumerate(raw_layout.get("blocks") or []):
        block_type = block.get("type", 0)
        if block_type == 0:
            block_id = f"b{block_index}"
            block_text = _block_text(block)
            block_bbox = _bbox_from_tuple(block["bbox"])
            if level is None or level == "block":
                if node_type is None or node_type == "text":
                    nodes.append(
                        LayoutNode(
                            id=block_id,
                            depth="block",
                            node_type="text",
                            parent_id=None,
                            block_index=block_index,
                            line_index=None,
                            span_index=None,
                            text=block_text,
                            bbox=block_bbox,
                            metadata={"line_count": len(block.get("lines") or [])},
                        )
                    )
            for line_index, line in enumerate(block.get("lines") or []):
                line_id = f"{block_id}_l{line_index}"
                line_text = _line_text(line)
                if not line_text.strip():
                    continue
                line_bbox = _bbox_from_tuple(line["bbox"])
                if level is None or level == "line":
                    if node_type is None or node_type == "text":
                        nodes.append(
                            LayoutNode(
                                id=line_id,
                                depth="line",
                                node_type="text",
                                parent_id=block_id,
                                block_index=block_index,
                                line_index=line_index,
                                span_index=None,
                                text=line_text,
                                bbox=line_bbox,
                                metadata={},
                            )
                        )
                for span_index, span in enumerate(line.get("spans") or []):
                    span_text = _span_text(span)
                    if not span_text:
                        continue
                    span_id = f"{line_id}_s{span_index}"
                    if level is None or level == "span":
                        if node_type is None or node_type == "text":
                            nodes.append(
                                LayoutNode(
                                    id=span_id,
                                    depth="span",
                                    node_type="text",
                                    parent_id=line_id,
                                    block_index=block_index,
                                    line_index=line_index,
                                    span_index=span_index,
                                    text=span_text,
                                    bbox=_bbox_from_tuple(span["bbox"]),
                                    metadata={
                                        "font": span.get("font"),
                                        "size": span.get("size"),
                                        "flags": span.get("flags"),
                                        "color": span.get("color"),
                                    },
                                )
                            )
        elif block_type == 1:
            if node_type is not None and node_type != "image":
                continue
            if level is not None and level != "block":
                continue
            image_id = f"img{block_index}"
            nodes.append(
                LayoutNode(
                    id=image_id,
                    depth="block",
                    node_type="image",
                    parent_id=None,
                    block_index=block_index,
                    line_index=None,
                    span_index=None,
                    text="",
                    bbox=_bbox_from_tuple(block["bbox"]),
                    metadata={
                        "width": block.get("width"),
                        "height": block.get("height"),
                        "ext": block.get("ext"),
                    },
                )
            )
    return nodes
