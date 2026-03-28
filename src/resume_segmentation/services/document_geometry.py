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
    is_bold: bool = False
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
    col_gap: float | None
    sidebar_column: int | None = None
    lines: list[LineNode] = field(default_factory=list)
    blocks: list[BlockNode] = field(default_factory=list)


@dataclass
class DocumentGeometry:
    pages: list[PageGeometry] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    table_skills: list[str] = field(default_factory=list)
    source_engine: str | None = None

    def ordered_lines(self) -> list[str]:
        lines: list[str] = []
        for page in self.pages:
            for line in page.lines:
                if line.text.strip():
                    lines.append(line.text.strip())
        return lines

    def smart_ordered_lines(self) -> list[str]:
        lines: list[str] = []
        for page in self.pages:
            ordered_blocks = self._reading_order_blocks(page)
            for block in ordered_blocks:
                for line in block.lines:
                    text = line.text.strip()
                    if text:
                        lines.append(text)
        return lines

    def _reading_order_blocks(self, page: PageGeometry) -> list[BlockNode]:
        if not page.blocks:
            return []

        if page.layout != "two_column":
            return sorted(page.blocks, key=lambda block: (block.top, block.x0))

        header_blocks = [block for block in page.blocks if block.column == -1]
        col0_blocks = [block for block in page.blocks if block.column == 0]
        col1_blocks = [block for block in page.blocks if block.column == 1]

        primary_blocks = col0_blocks
        secondary_blocks = col1_blocks

        if page.sidebar_column is not None:
            if page.sidebar_column == 0:
                primary_blocks = col1_blocks
                secondary_blocks = col0_blocks
            else:
                primary_blocks = col0_blocks
                secondary_blocks = col1_blocks

        ordered: list[BlockNode] = []
        ordered.extend(sorted(header_blocks, key=lambda block: (block.top, block.x0)))
        ordered.extend(sorted(primary_blocks, key=lambda block: block.top))
        ordered.extend(sorted(secondary_blocks, key=lambda block: block.top))
        return ordered


class GeometryExtractor:

    def extract(self, pdf_path: str) -> DocumentGeometry:
        try:
            import pdfplumber
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'pdfplumber'. Install project dependencies."
            ) from exc

        document = DocumentGeometry(source_engine="pdfplumber")
        seen_urls: set[str] = set()

        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages):
                page_width = float(page.width)
                page_height = float(page.height)

                words = self._extract_words(page, page_index)

                col_gap = self._find_column_gap(words, page_width, page_height)

                lines = self._group_words_into_lines(words, page_index, page_width, col_gap)

                for line in lines:
                    line.column = self._assign_column(
                        line.x0, line.x1, page_width, col_gap
                    )
                    line.is_bold = self._detect_bold(line.words)

                ordered_lines = self._order_lines(lines, page_height, col_gap)
                blocks = self._group_lines_into_blocks(ordered_lines)
                layout = "two_column" if col_gap is not None else "single_column"
                sidebar_column = self._detect_sidebar_column(ordered_lines, page_width, layout)

                document.pages.append(PageGeometry(
                    page=page_index,
                    width=page_width,
                    height=page_height,
                    layout=layout,
                    col_gap=col_gap,
                    sidebar_column=sidebar_column,
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

        words.sort(key=lambda w: (w.top, w.x0))
        return words

    def _find_column_gap(
        self, words: list[WordNode], page_width: float, page_height: float
    ) -> float | None:
        middle_words = [
            w for w in words
            if page_height * 0.12 < w.top < page_height * 0.92
        ]

        if len(middle_words) < 8:
            return None

        bin_size = 8.0
        num_bins = int(page_width / bin_size) + 2
        hist = [0] * num_bins

        for w in middle_words:
            x_center = (w.x0 + w.x1) / 2.0
            b = min(int(x_center / bin_size), num_bins - 1)
            hist[b] += 1

        left_bound = int(page_width * 0.28 / bin_size)
        right_bound = int(page_width * 0.72 / bin_size)

        best_start = -1
        best_end = -1
        best_len = 0
        gap_start = -1

        for i in range(left_bound, right_bound + 1):
            if hist[i] == 0:
                if gap_start == -1:
                    gap_start = i
            else:
                if gap_start != -1:
                    gap_len = i - gap_start
                    if gap_len > best_len:
                        best_len = gap_len
                        best_start = gap_start
                        best_end = i
                    gap_start = -1

        if gap_start != -1:
            gap_len = right_bound + 1 - gap_start
            if gap_len > best_len:
                best_len = gap_len
                best_start = gap_start
                best_end = right_bound + 1

        min_gap_px = 18.0
        if best_len * bin_size < min_gap_px or best_start == -1:
            return None

        gap_center = (best_start + best_end) / 2.0 * bin_size

        left_count = sum(1 for w in middle_words if (w.x0 + w.x1) / 2 < gap_center)
        right_count = sum(1 for w in middle_words if (w.x0 + w.x1) / 2 > gap_center)

        if left_count < 3 or right_count < 3:
            return None

        left_ratio = left_count / (left_count + right_count)
        if left_ratio < 0.15 or left_ratio > 0.85:
            return None

        return gap_center

    def _group_words_into_lines(
        self,
        words: list[WordNode],
        page_index: int,
        page_width: float,
        col_gap: float | None,
    ) -> list[LineNode]:
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w.top, w.x0))

        groups: list[list[WordNode]] = []
        current_group: list[WordNode] = [sorted_words[0]]
        current_top = sorted_words[0].top
        word_h = sorted_words[0].bottom - sorted_words[0].top
        line_tolerance = max(word_h * 0.55, 2.5)

        for word in sorted_words[1:]:
            y_close = abs(word.top - current_top) <= line_tolerance

            if y_close and col_gap is not None:
                group_x_center = sum(
                    (w.x0 + w.x1) / 2 for w in current_group
                ) / len(current_group)
                word_x_center = (word.x0 + word.x1) / 2
                same_column = (group_x_center < col_gap) == (word_x_center < col_gap)
                if not same_column:
                    groups.append(sorted(current_group, key=lambda w: w.x0))
                    current_group = [word]
                    current_top = word.top
                    h = word.bottom - word.top
                    line_tolerance = max(h * 0.55, 2.5)
                    continue

            if y_close:
                current_group.append(word)
                current_top = (current_top * len(current_group) + word.top) / (
                    len(current_group) + 1
                )
            else:
                groups.append(sorted(current_group, key=lambda w: w.x0))
                current_group = [word]
                current_top = word.top
                h = word.bottom - word.top
                line_tolerance = max(h * 0.55, 2.5)

        groups.append(sorted(current_group, key=lambda w: w.x0))

        lines: list[LineNode] = []
        for group in groups:
            x0 = min(w.x0 for w in group)
            x1 = max(w.x1 for w in group)
            top = min(w.top for w in group)
            bottom = max(w.bottom for w in group)
            sizes = [w.size for w in group if w.size is not None]
            font_size = sum(sizes) / len(sizes) if sizes else None
            text = self._join_words(group)

            lines.append(LineNode(
                text=text,
                page=page_index,
                x0=x0,
                x1=x1,
                top=top,
                bottom=bottom,
                column=-1,
                font_size=font_size,
                words=group,
            ))

        return lines

    def _assign_column(
        self, x0: float, x1: float, page_width: float, col_gap: float | None
    ) -> int:
        if col_gap is None:
            return -1

        line_width = x1 - x0
        if line_width > page_width * 0.48:
            return -1

        x_center = (x0 + x1) / 2.0
        if x_center < col_gap:
            return 0
        return 1

    def _detect_bold(self, words: list[WordNode]) -> bool:
        if not words:
            return False
        bold_count = sum(
            1 for w in words
            if w.fontname and "bold" in w.fontname.lower()
        )
        return bold_count > len(words) * 0.5

    def _order_lines(
        self, lines: list[LineNode], page_height: float, col_gap: float | None
    ) -> list[LineNode]:
        has_right_col = any(l.column == 1 for l in lines)

        if not has_right_col or col_gap is None:
            return sorted(lines, key=lambda l: (l.top, l.x0))

        header_band = page_height * 0.14

        header_lines = [l for l in lines if l.top <= header_band]
        body_lines = [l for l in lines if l.top > header_band]

        left_body = [l for l in body_lines if l.column in (-1, 0)]
        right_body = [l for l in body_lines if l.column == 1]

        ordered: list[LineNode] = []
        ordered.extend(sorted(header_lines, key=lambda l: (l.top, l.x0)))
        ordered.extend(sorted(left_body, key=lambda l: l.top))
        ordered.extend(sorted(right_body, key=lambda l: l.top))
        return ordered

    def _group_lines_into_blocks(self, lines: list[LineNode]) -> list[BlockNode]:
        if not lines:
            return []

        blocks: list[BlockNode] = []
        current = BlockNode(page=lines[0].page, column=lines[0].column, lines=[lines[0]])

        for line in lines[1:]:
            prev = current.lines[-1]
            vertical_gap = line.top - prev.bottom
            prev_h = max(prev.bottom - prev.top, 5.0)
            gap_threshold = prev_h * 1.6

            col_changed = line.column != prev.column
            page_changed = line.page != prev.page
            gap_exceeded = vertical_gap > gap_threshold

            if page_changed or col_changed or gap_exceeded:
                blocks.append(current)
                current = BlockNode(page=line.page, column=line.column, lines=[line])
            else:
                current.lines.append(line)

        blocks.append(current)
        return blocks

    def _detect_sidebar_column(
        self,
        lines: list[LineNode],
        page_width: float,
        layout: str,
    ) -> int | None:
        if layout != "two_column":
            return None

        col0 = [line for line in lines if line.column == 0]
        col1 = [line for line in lines if line.column == 1]
        if not col0 or not col1:
            return None

        def avg_width(col_lines: list[LineNode]) -> float:
            widths = [line.x1 - line.x0 for line in col_lines]
            return sum(widths) / len(widths) if widths else 0.0

        width0 = avg_width(col0)
        width1 = avg_width(col1)
        count0 = len(col0)
        count1 = len(col1)

        if width0 <= page_width * 0.28 and count0 <= count1 * 0.75:
            return 0
        if width1 <= page_width * 0.28 and count1 <= count0 * 0.75:
            return 1

        return None

    def _join_words(self, words: list[WordNode]) -> str:
        text = " ".join(w.text for w in words)
        text = re.sub(r"\s+([,.:;!?])", r"\1", text)
        return text.strip()

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\(cid:\d+\)", " ", text)
        text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
        text = text.replace("\u00a0", " ").replace("\u00c2", " ")
        text = re.sub(r"\s*,\s*", ", ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
