from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from src.resume_segmentation.services.document_text_extractor import DocumentTextExtractor
from src.resume_segmentation.services.pipeline import ARIEPipeline


_DOC_RELS = """<?xml version='1.0' encoding='UTF-8'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink' Target='https://github.com/dev/resume' TargetMode='External'/>
</Relationships>
"""


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    body = []
    for paragraph in paragraphs:
        if paragraph == "__HYPERLINK__":
            body.append(
                "<w:p><w:hyperlink r:id='rId1'><w:r><w:t>GitHub</w:t></w:r></w:hyperlink></w:p>"
            )
            continue
        body.append(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>")

    document_xml = """<?xml version='1.0' encoding='UTF-8'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>
  <w:body>
    %s
  </w:body>
</w:document>
""" % "".join(body)

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", _DOC_RELS)


class DocumentTextExtractorTests(unittest.TestCase):
    def test_extracts_docx_lines_and_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            _make_docx(docx_path, ["General Information", "Dev Agarwal", "__HYPERLINK__"])

            lines, urls = DocumentTextExtractor().extract(str(docx_path))

            self.assertIn("General Information", lines)
            self.assertIn("Dev Agarwal", lines)
            self.assertIn("https://github.com/dev/resume", urls)

    def test_pipeline_supports_docx_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "resume.docx"
            _make_docx(
                docx_path,
                [
                    "General Information",
                    "Dev Agarwal",
                    "Software Engineer",
                    "Work Experience",
                    "Software Engineer",
                    "Acme Corp",
                    "2022 - Present",
                    "Education",
                    "Bachelor of Technology in Computer Science",
                    "ABC Institute of Technology",
                    "2021 - 2025",
                    "Technical Expertise",
                    "Python, FastAPI, PostgreSQL",
                    "__HYPERLINK__",
                ],
            )

            result = ARIEPipeline().extract(docx_path)

            self.assertTrue(result.success, msg=result.error)
            self.assertEqual(result.profile.personal_info.name, "Dev Agarwal")
            self.assertIn("Python", result.profile.skills)
            self.assertEqual(len(result.profile.experience), 1)
            self.assertEqual(result.enrichment.extractor_report["text"]["best_source"], "docx_xml")
            self.assertIsNone(result.enrichment.extractor_report["geometry"])


if __name__ == "__main__":
    unittest.main()
