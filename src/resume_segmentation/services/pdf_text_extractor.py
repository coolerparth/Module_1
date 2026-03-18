import re


class PDFTextExtractor:
    def extract(self, pdf_path: str) -> tuple[list[str], list[str]]:
        try:
            import pdfplumber
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'pdfplumber'. Install project dependencies in the virtual environment."
            ) from exc

        lines: list[str] = []
        urls: list[str] = []
        seen_urls: set[str] = set()

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for raw_line in text.splitlines():
                    cleaned = self._clean_line(raw_line)
                    if cleaned:
                        lines.append(cleaned)

                for annot in page.annots or []:
                    uri = (annot.get("uri") or "").strip()
                    if uri.startswith(("http://", "https://")) and uri not in seen_urls:
                        seen_urls.add(uri)
                        urls.append(uri)

        return lines, urls

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"\(cid:\d+\)", " ", line)
        line = re.sub(r"[\x00-\x1f\x7f]", " ", line)
        line = line.replace("§", " ")
        line = line.replace("\u00a0", " ")
        line = line.replace("\u00c2", " ")
        line = line.replace("\u00ef\u00bc", " ")
        line = re.sub(r"\s*,\s*", ", ", line)
        line = re.sub(r"\s+", " ", line).strip()
        return line
