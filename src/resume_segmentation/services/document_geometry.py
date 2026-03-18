from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class WordNode:
    text: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    size: float | None = None
    fontname: str | None = None


@dataclass
class LineNode:
    text: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    column: int
    font_size: float | None
    words: list[WordNode] = field(default_factory=list)


@dataclass
class BlockNode:
    page: int
    column: int
    lines: list[LineNode] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def x0(self) -> float:
        return min((line.x0 for line in self.lines), default=0.0)

    @property
    def x1(self) -> float:
        return max((line.x1 for line in self.lines), default=0.0)

    @property
    def top(self) -> float:
        return min((line.top for line in self.lines), default=0.0)

    @property
    def bottom(self) -> float:
        return max((line.bottom for line in self.lines), default=0.0)

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2.0 if self.lines else 0.0

    @property
    def avg_line_height(self) -> float:
        if not self.lines:
            return 12.0
        heights = [ln.bottom - ln.top for ln in self.lines if ln.bottom > ln.top]
        return sum(heights) / len(heights) if heights else 12.0


@dataclass
class PageGeometry:
    page: int
    width: float
    height: float
    layout: str
    lines: list[LineNode] = field(default_factory=list)
    blocks: list[BlockNode] = field(default_factory=list)


@dataclass
class DocumentGeometry:
    pages: list[PageGeometry] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    def ordered_lines(self) -> list[str]:
        lines: list[str] = []
        for page in self.pages:
            for line in page.lines:
                if line.text.strip():
                    lines.append(line.text.strip())
        return lines


class GeometryExtractor:
    def extract(self, pdf_path: str) -> DocumentGeometry:
        try:
            import pdfplumber
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'pdfplumber'. Install project dependencies in the virtual environment."
            ) from exc

        document = DocumentGeometry()
        seen_urls: set[str] = set()

        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages):
                words = self._extract_words(page, page_index)
                lines = self._group_words_into_lines(words, page_index, float(page.width))
                ordered_lines = self._order_lines(lines, float(page.width), float(page.height))
                blocks = self._group_lines_into_blocks(ordered_lines)

                document.pages.append(PageGeometry(
                    page=page_index,
                    width=float(page.width),
                    height=float(page.height),
                    layout=self._detect_layout(ordered_lines, float(page.width)),
                    lines=ordered_lines,
                    blocks=blocks,
                ))

                for annot in page.annots or []:
                    uri = (annot.get("uri") or "").strip()
                    if uri.startswith(("http://", "https://")) and uri not in seen_urls:
                        seen_urls.add(uri)
                        document.urls.append(uri)

        return document

    def _extract_words(self, page, page_index: int) -> list[WordNode]:
        raw_words = page.extract_words(
            x_tolerance=1,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
            extra_attrs=["fontname", "size"],
        )

        words: list[WordNode] = []
        for item in raw_words:
            text = self._clean_text(item.get("text", ""))
            if not text:
                continue

            words.append(WordNode(
                text=text,
                page=page_index,
                x0=float(item["x0"]),
                x1=float(item["x1"]),
                top=float(item["top"]),
                bottom=float(item["bottom"]),
                size=float(item["size"]) if item.get("size") is not None else None,
                fontname=item.get("fontname"),
            ))

        words.sort(key=lambda word: (word.top, word.x0))
        return words

    def _group_words_into_lines(
        self,
        words: list[WordNode],
        page_index: int,
        page_width: float,
    ) -> list[LineNode]:
        if not words:
            return []

        groups: list[list[WordNode]] = []
        current_group: list[WordNode] = [words[0]]
        current_top = words[0].top
        line_tolerance = max((words[0].bottom - words[0].top) * 0.6, 3.0)

        for word in words[1:]:
            if abs(word.top - current_top) <= line_tolerance:
                current_group.append(word)
                current_top = (current_top + word.top) / 2
                continue

            groups.append(sorted(current_group, key=lambda item: item.x0))
            current_group = [word]
            current_top = word.top
            line_tolerance = max((word.bottom - word.top) * 0.6, 3.0)

        groups.append(sorted(current_group, key=lambda item: item.x0))

        lines: list[LineNode] = []
        for group in groups:
            x0 = min(word.x0 for word in group)
            x1 = max(word.x1 for word in group)
            top = min(word.top for word in group)
            bottom = max(word.bottom for word in group)
            font_sizes = [word.size for word in group if word.size is not None]
            column = self._assign_column(x0, x1, page_width)
            text = self._join_words(group)

            lines.append(LineNode(
                text=text,
                page=page_index,
                x0=x0,
                x1=x1,
                top=top,
                bottom=bottom,
                column=column,
                font_size=sum(font_sizes) / len(font_sizes) if font_sizes else None,
                words=group,
            ))

        return lines

    def _order_lines(self, lines: list[LineNode], page_width: float, page_height: float) -> list[LineNode]:
        layout = self._detect_layout(lines, page_width)
        if layout == "single_column":
            return sorted(lines, key=lambda line: (line.top, line.x0))

        header_band = page_height * 0.14
        header_lines = [line for line in lines if line.column == -1 and line.top <= header_band]
        left_lines = [line for line in lines if line.column == 0 and line.top > header_band]
        right_lines = [line for line in lines if line.column == 1 and line.top > header_band]
        floating_lines = [line for line in lines if line.column == -1 and line.top > header_band]

        ordered: list[LineNode] = []
        ordered.extend(sorted(header_lines, key=lambda line: (line.top, line.x0)))
        ordered.extend(sorted(left_lines, key=lambda line: (line.top, line.x0)))
        ordered.extend(sorted(right_lines, key=lambda line: (line.top, line.x0)))
        ordered.extend(sorted(floating_lines, key=lambda line: (line.top, line.x0)))
        return ordered

    def _group_lines_into_blocks(self, lines: list[LineNode]) -> list[BlockNode]:
        if not lines:
            return []

        blocks: list[BlockNode] = []
        current = BlockNode(page=lines[0].page, column=lines[0].column, lines=[lines[0]])

        for line in lines[1:]:
            prev = current.lines[-1]
            vertical_gap = line.top - prev.bottom
                                                                                         
            prev_line_height = max(prev.bottom - prev.top, 6.0)
            gap_threshold = prev_line_height * 1.4
            if line.page != prev.page or line.column != prev.column or vertical_gap > gap_threshold:
                blocks.append(current)
                current = BlockNode(page=line.page, column=line.column, lines=[line])
                continue

            current.lines.append(line)

        blocks.append(current)
        return blocks

    def _detect_layout(self, lines: list[LineNode], page_width: float) -> str:
        left_count = sum(1 for line in lines if line.column == 0)
        right_count = sum(1 for line in lines if line.column == 1)
        full_width_count = sum(1 for line in lines if line.column == -1 and (line.x1 - line.x0) > page_width * 0.55)

        if left_count >= 6 and right_count >= 6 and full_width_count < (left_count + right_count):
            return "two_column"
        return "single_column"

    def _assign_column(self, x0: float, x1: float, page_width: float) -> int:
        mid = page_width / 2
        if x1 <= mid + page_width * 0.04:
            return 0
        if x0 >= mid - page_width * 0.04:
            return 1
        return -1

    def _join_words(self, words: list[WordNode]) -> str:
        text = " ".join(word.text for word in words)
        text = re.sub(r"\s+([,.:;!?])", r"\1", text)
        return text.strip()

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\(cid:\d+\)", " ", text)
        text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
        text = text.replace("§", " ")
        text = text.replace("\u00a0", " ")
        text = text.replace("\u00c2", " ")
        text = text.replace("\u00ef\u00bc", " ")
        text = re.sub(r"\s*,\s*", ", ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
