from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .table_skill_extractor import (
    extract_skills_from_table,
    extract_skills_from_table_text,
)
from .document_geometry import (
    BlockNode,
    DocumentGeometry,
    LineNode,
    PageGeometry,
    WordNode,
)

_HEADING_LABELS = frozenset({
    "SectionHeaderItem",
    "TitleItem",
    "section_header",
    "title",
    "SECTION_HEADER",
    "TITLE",
})

_TABLE_LABELS = frozenset({
    "TableItem",
    "table",
    "TABLE",
})

_SKIP_LABELS = frozenset({
    "PictureItem",
    "picture",
    "PICTURE",
    "FigureItem",
    "figure",
    "FIGURE",
})

_MIN_CHARS_PER_AREA = 0.012


class DoclingLayoutExtractor:

    _converter: Any = None
    _ocr: Any = None

    @classmethod
    def _get_converter(cls) -> Any:
        if cls._converter is not None:
            return cls._converter

        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
        except ImportError as exc:
            raise RuntimeError(
                "docling not installed. Run: pip install docling"
            ) from exc

        opts = PdfPipelineOptions()
        opts.do_ocr = False
        opts.do_table_structure = True
        opts.generate_picture_images = False

        cls._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
            }
        )
        return cls._converter

    @classmethod
    def _get_ocr(cls) -> Any:
        if cls._ocr is not None:
            return cls._ocr

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "paddleocr not installed. Run: pip install paddleocr"
            ) from exc

        cls._ocr = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            use_gpu=False,
            show_log=False,
            det_db_score_mode="slow",
            rec_batch_num=6,
        )
        return cls._ocr

    def extract(self, pdf_path: str) -> DocumentGeometry:
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("pdfplumber not installed.") from exc

        converter = self._get_converter()
        result = converter.convert(pdf_path)
        doc = result.document

        document = DocumentGeometry(source_engine="docling")
        seen_urls: set[str] = set()

        with pdfplumber.open(pdf_path) as pdf:
            for page_index, plumber_page in enumerate(pdf.pages):
                page_width = float(plumber_page.width)
                page_height = float(plumber_page.height)

                layout_blocks = self._extract_layout_blocks(
                    doc, page_index + 1, page_height
                )

                lines: list[LineNode] = []
                for block in layout_blocks:
                    label = block["label"]
                    if label in _SKIP_LABELS:
                        continue

                    x0, top, x1, bottom = block["bbox"]
                    x0 = max(0.0, x0)
                    top = max(0.0, top)
                    x1 = min(page_width, x1)
                    bottom = min(page_height, bottom)

                    if x1 <= x0 or bottom <= top:
                        continue

                    if label in _TABLE_LABELS:
                        table_skills = self._extract_table_skills(
                            block.get("raw_item"), block["text"]
                        )
                        seen_ts = set(s.lower() for s in document.table_skills)
                        for ts in table_skills:
                            if ts.lower() not in seen_ts:
                                seen_ts.add(ts.lower())
                                document.table_skills.append(ts)
                        continue

                    box_area = (x1 - x0) * (bottom - top)

                    docling_text = block["text"].strip()

                    plumber_text = self._extract_text_pdfplumber(
                        plumber_page, x0, top, x1, bottom
                    )

                    text = self._pick_best_text(
                        docling_text, plumber_text, box_area
                    )

                    if self._needs_ocr(text, box_area):
                        ocr_text = self._extract_text_ocr(
                            plumber_page, x0, top, x1, bottom, page_height
                        )
                        text = self._pick_best_text(text, ocr_text, box_area)

                    if not text:
                        continue

                    text = self._clean_text(text)
                    if not text:
                        continue

                    is_heading = label in _HEADING_LABELS
                    font_size = self._get_font_size(
                        plumber_page, x0, top, x1, bottom
                    )
                    is_bold = is_heading or self._detect_bold(
                        plumber_page, x0, top, x1, bottom
                    )

                    block_lines = [l.strip() for l in text.split("\n") if l.strip()]
                    num_lines = max(len(block_lines), 1)
                    line_h = (bottom - top) / num_lines

                    for li, line_text in enumerate(block_lines):
                        line_top = top + li * line_h
                        line_bottom = line_top + line_h
                        lines.append(LineNode(
                            text=line_text,
                            page=page_index,
                            x0=x0,
                            x1=x1,
                            top=line_top,
                            bottom=line_bottom,
                            column=-1,
                            font_size=font_size,
                            is_bold=is_bold,
                        ))

                for annot in plumber_page.annots or []:
                    uri = (annot.get("uri") or "").strip()
                    if uri.startswith(("http://", "https://")) and uri not in seen_urls:
                        seen_urls.add(uri)
                        document.urls.append(uri)

                blocks = self._group_into_blocks(lines)
                document.pages.append(PageGeometry(
                    page=page_index,
                    width=page_width,
                    height=page_height,
                    layout="single_column",
                    col_gap=None,
                    lines=lines,
                    blocks=blocks,
                ))

        return document

    def _extract_table_skills(
        self, raw_item: Any, fallback_text: str
    ) -> list[str]:
        if raw_item is not None:
            try:
                skills = extract_skills_from_table(raw_item)
                if skills:
                    return skills
            except Exception:
                pass
        return extract_skills_from_table_text(fallback_text)

    def _pick_best_text(
        self, text_a: str, text_b: str, box_area: float
    ) -> str:
        a = text_a.strip()
        b = text_b.strip()
        if not a and not b:
            return ""
        if not a:
            return b
        if not b:
            return a
        if len(b) > len(a) * 1.15:
            return b
        return a

    def _needs_ocr(self, text: str, box_area: float) -> bool:
        if not text:
            return True
        expected_min_chars = box_area * _MIN_CHARS_PER_AREA
        return len(text) < expected_min_chars * 0.3

    def _extract_layout_blocks(
        self,
        doc: Any,
        page_no: int,
        page_height: float,
    ) -> list[dict]:
        blocks: list[dict] = []

        try:
            for item, _level in doc.iterate_items():
                if not hasattr(item, "prov") or not item.prov:
                    continue

                for prov in item.prov:
                    if prov.page_no != page_no:
                        continue

                    bbox = prov.bbox
                    x0, top, x1, bottom = self._convert_bbox(bbox, page_height)

                    text = ""
                    if hasattr(item, "text") and item.text:
                        text = item.text

                    label = type(item).__name__

                    blocks.append({
                        "bbox": (x0, top, x1, bottom),
                        "label": label,
                        "text": text,
                        "orig_top": top,
                        "orig_left": x0,
                        "raw_item": item if label in _TABLE_LABELS else None,
                    })
        except Exception:
            pass

        blocks.sort(key=lambda b: (b["orig_top"], b["orig_left"]))
        return blocks

    def _convert_bbox(
        self, bbox: Any, page_height: float
    ) -> tuple[float, float, float, float]:
        l = float(bbox.l)
        t = float(bbox.t)
        r = float(bbox.r)
        b = float(bbox.b)

        coord_origin = getattr(bbox, "coord_origin", None)
        origin_name = str(coord_origin).upper() if coord_origin is not None else ""

        if "BOTTOMLEFT" in origin_name or "BOTTOM" in origin_name:
            top = page_height - t
            bottom = page_height - b
            if top > bottom:
                top, bottom = bottom, top
            return l, top, r, bottom

        if "TOPLEFT" in origin_name or "TOP" in origin_name:
            top = min(b, t)
            bottom = max(b, t)
            return l, top, r, bottom

        if t > b:
            top = page_height - t
            bottom = page_height - b
        else:
            top = t
            bottom = b

        if top > bottom:
            top, bottom = bottom, top

        return l, top, r, bottom

    def _extract_text_pdfplumber(
        self,
        page: Any,
        x0: float,
        top: float,
        x1: float,
        bottom: float,
    ) -> str:
        try:
            padding = 2.0
            crop = page.crop((
                max(0, x0 - padding),
                max(0, top - padding),
                min(float(page.width), x1 + padding),
                min(float(page.height), bottom + padding),
            ))
            text = crop.extract_text(x_tolerance=2, y_tolerance=3) or ""
            return text.strip()
        except Exception:
            return ""

    def _extract_text_ocr(
        self,
        page: Any,
        x0: float,
        top: float,
        x1: float,
        bottom: float,
        page_height: float,
    ) -> str:
        try:
            import numpy as np

            width = x1 - x0
            height = bottom - top
            if width < 8 or height < 6:
                return ""

            resolution = 250
            padding_px = 6

            page_img = page.to_image(resolution=resolution)
            pil_img = page_img.original

            scale = resolution / 72.0
            px_x0 = max(0, int(x0 * scale) - padding_px)
            px_top = max(0, int(top * scale) - padding_px)
            px_x1 = min(pil_img.width, int(x1 * scale) + padding_px)
            px_bottom = min(pil_img.height, int(bottom * scale) + padding_px)

            if px_x1 <= px_x0 or px_bottom <= px_top:
                return ""

            crop_img = pil_img.crop((px_x0, px_top, px_x1, px_bottom))
            img_array = np.array(crop_img)

            ocr = self._get_ocr()
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                return ""

            lines: list[tuple[float, str]] = []
            for line in result[0]:
                if not line or len(line) < 2:
                    continue
                bbox_pts = line[0]
                text_conf = line[1]
                if not text_conf or len(text_conf) < 2:
                    continue
                text = str(text_conf[0]).strip()
                conf = float(text_conf[1])
                if text and conf >= 0.45:
                    y_center = sum(pt[1] for pt in bbox_pts) / 4
                    lines.append((y_center, text))

            lines.sort(key=lambda x: x[0])
            return "\n".join(t for _, t in lines)

        except Exception:
            return ""

    def _get_font_size(
        self,
        page: Any,
        x0: float,
        top: float,
        x1: float,
        bottom: float,
    ) -> float | None:
        try:
            crop = page.crop((
                max(0, x0 - 1),
                max(0, top - 1),
                min(float(page.width), x1 + 1),
                min(float(page.height), bottom + 1),
            ))
            words = crop.extract_words(extra_attrs=["size"])
            sizes = [float(w["size"]) for w in words if w.get("size")]
            if sizes:
                return sum(sizes) / len(sizes)
        except Exception:
            pass
        return None

    def _detect_bold(
        self,
        page: Any,
        x0: float,
        top: float,
        x1: float,
        bottom: float,
    ) -> bool:
        try:
            crop = page.crop((
                max(0, x0 - 1),
                max(0, top - 1),
                min(float(page.width), x1 + 1),
                min(float(page.height), bottom + 1),
            ))
            words = crop.extract_words(extra_attrs=["fontname"])
            if not words:
                return False
            bold_count = sum(
                1 for w in words
                if w.get("fontname") and "bold" in str(w["fontname"]).lower()
            )
            return bold_count > len(words) * 0.5
        except Exception:
            return False

    def _group_into_blocks(self, lines: list[LineNode]) -> list[BlockNode]:
        if not lines:
            return []

        blocks: list[BlockNode] = []
        current = BlockNode(page=lines[0].page, column=-1, lines=[lines[0]])

        for line in lines[1:]:
            prev = current.lines[-1]
            gap = line.top - prev.bottom
            prev_h = max(prev.bottom - prev.top, 5.0)
            if line.page != prev.page or gap > prev_h * 1.8:
                blocks.append(current)
                current = BlockNode(page=line.page, column=-1, lines=[line])
            else:
                current.lines.append(line)

        blocks.append(current)
        return blocks

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\(cid:\d+\)", " ", text)
        text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
        text = text.replace("\u00a0", " ").replace("\u00c2", " ")
        text = re.sub(r"\s*,\s*", ", ", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
