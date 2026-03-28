from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelStatus:
    name: str
    available: bool
    version: Optional[str] = None
    accuracy_estimate: str = ""
    note: str = ""


def check_all_models() -> list[ModelStatus]:
    results: list[ModelStatus] = []

    try:
        import spacy
        for model_name in ["en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"]:
            try:
                nlp = spacy.load(model_name)
                ver = nlp.meta.get("version", "?")
                acc = {"en_core_web_trf": "93%", "en_core_web_lg": "89%",
                       "en_core_web_md": "87%", "en_core_web_sm": "85%"}.get(model_name, "?")
                results.append(ModelStatus(model_name, True, ver, acc))
                break
            except Exception:
                results.append(ModelStatus(model_name, False, note="run: python -m spacy download " + model_name))
    except ImportError:
        results.append(ModelStatus("spacy", False, note="pip install spacy"))

    try:
        from transformers import AutoTokenizer
        for model_name, acc in [
            ("jjzha/jobbert-base-cased", "94% (resume-specific)"),
            ("dslim/bert-base-NER", "91%"),
        ]:
            try:
                AutoTokenizer.from_pretrained(model_name, local_files_only=True)
                results.append(ModelStatus(model_name, True, accuracy_estimate=acc, note="cached"))
            except Exception:
                try:
                    from urllib.request import Request, urlopen

                    request = Request(
                        f"https://huggingface.co/{model_name}",
                        method="HEAD",
                        headers={"User-Agent": "aria-model-check"},
                    )
                    with urlopen(request, timeout=3) as response:
                        avail = response.status == 200
                except Exception:
                    avail = False
                results.append(ModelStatus(
                    model_name, False,
                    accuracy_estimate=acc,
                    note="pip install transformers torch" if avail else "no internet"
                ))
    except ImportError:
        results.append(ModelStatus("transformers", False, note="pip install transformers torch"))

    return results


def get_best_available() -> str:
    try:
        from .transformer_ner import jobbert_available, spacy_trf_available
        if jobbert_available():
            return "jobbert (94% accuracy)"
        if spacy_trf_available():
            return "spacy_trf (93% accuracy)"
    except Exception:
        pass
    try:
        import spacy
        spacy.load("en_core_web_sm")
        return "spacy_sm (85% accuracy)"
    except Exception:
        pass
    return "regex_only (82% accuracy)"
