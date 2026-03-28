from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .document_evidence import DocumentEvidence
from .document_geometry import DocumentGeometry, PageGeometry


@dataclass
class PageLayoutSummary:
    page: int
    layout: str
    line_count: int
    block_count: int
    heading_count: int
    left_column_lines: int
    right_column_lines: int
    sidebar_detected: bool
    sidebar_column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "layout": self.layout,
            "line_count": self.line_count,
            "block_count": self.block_count,
            "heading_count": self.heading_count,
            "left_column_lines": self.left_column_lines,
            "right_column_lines": self.right_column_lines,
            "sidebar_detected": self.sidebar_detected,
            "sidebar_column": self.sidebar_column,
        }


@dataclass
class LayoutReport:
    overall_layout: str
    page_count: int
    reading_order_confidence: float
    heading_density: float
    sidebar_pages: list[int] = field(default_factory=list)
    page_summaries: list[PageLayoutSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_layout": self.overall_layout,
            "page_count": self.page_count,
            "reading_order_confidence": self.reading_order_confidence,
            "heading_density": self.heading_density,
            "sidebar_pages": self.sidebar_pages,
            "page_summaries": [page.to_dict() for page in self.page_summaries],
        }


class LayoutEngine:
    def analyze(self, geometry: DocumentGeometry, evidence: DocumentEvidence | None = None) -> LayoutReport:
        page_summaries: list[PageLayoutSummary] = []
        sidebar_pages: list[int] = []

        for page in geometry.pages:
            summary = self._summarize_page(page, evidence)
            page_summaries.append(summary)
            if summary.sidebar_detected:
                sidebar_pages.append(page.page)

        page_count = len(geometry.pages)
        overall_layout = "single_column"
        if any(page.layout == "two_column" for page in geometry.pages):
            overall_layout = "mixed" if any(page.layout == "single_column" for page in geometry.pages) else "two_column"

        heading_count = sum(page.heading_count for page in page_summaries)
        line_count = max(sum(page.line_count for page in page_summaries), 1)
        heading_density = round(heading_count / line_count, 3)

        reading_order_confidence = 0.72
        if overall_layout == "single_column":
            reading_order_confidence += 0.18
        if overall_layout == "two_column":
            reading_order_confidence -= 0.08
        if sidebar_pages:
            reading_order_confidence -= 0.05
        if evidence and evidence.headings:
            reading_order_confidence += 0.06

        return LayoutReport(
            overall_layout=overall_layout,
            page_count=page_count,
            reading_order_confidence=round(min(max(reading_order_confidence, 0.0), 1.0), 3),
            heading_density=heading_density,
            sidebar_pages=sidebar_pages,
            page_summaries=page_summaries,
        )

    def _summarize_page(
        self,
        page: PageGeometry,
        evidence: DocumentEvidence | None,
    ) -> PageLayoutSummary:
        left_column_lines = sum(1 for line in page.lines if line.column == 0)
        right_column_lines = sum(1 for line in page.lines if line.column == 1)
        heading_count = 0
        if evidence:
            heading_count = sum(1 for heading in evidence.headings if heading.page == page.page)

        dominant = max(left_column_lines, right_column_lines, 1)
        minor = min(left_column_lines, right_column_lines)
        sidebar_detected = (
            page.layout == "two_column"
            and minor > 0
            and (minor / dominant) <= 0.45
        )

        return PageLayoutSummary(
            page=page.page,
            layout=page.layout,
            line_count=len(page.lines),
            block_count=len(page.blocks),
            heading_count=heading_count,
            left_column_lines=left_column_lines,
            right_column_lines=right_column_lines,
            sidebar_detected=sidebar_detected,
            sidebar_column=page.sidebar_column,
        )
