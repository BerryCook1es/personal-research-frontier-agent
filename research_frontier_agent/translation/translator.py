from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .glossary import protect_terms, restore_terms
from ..utils import normalize_openai_api_base, openai_api_endpoint, request_json


class Translator:
    """Translation is intentionally separate from embedding and research judgment."""

    def __init__(self, *, backend: str = "auto", model: str = "", api_base: str = "",
                 api_key: str = "", temperature: float = 0.1, timeout: float = 60.0,
                 retries: int = 2, translate_fn: Callable[[str], str] | None = None):
        self.backend = backend
        self.model = model
        self.api_base = normalize_openai_api_base(api_base)
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries
        self.translate_fn = translate_fn

    def translate(self, text: str) -> str:
        if not text:
            return ""
        protected, markers = protect_terms(text)
        if self.translate_fn:
            return restore_terms(self.translate_fn(protected), markers)
        if self.backend in {"openai", "openai-compatible"} or (self.backend == "auto" and self.api_key):
            if not self.api_base or not self.api_key or not self.model:
                raise RuntimeError("translation model, api_base and api_key are required")
            data = request_json(
                openai_api_endpoint(self.api_base, "chat/completions"),
                method="POST",
                payload={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Translate academic English to Simplified Chinese. Preserve __TERM_n__ markers. Output translation only."},
                        {"role": "user", "content": protected},
                    ],
                    "temperature": self.temperature,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
                retries=self.retries,
            )
            translated = data["choices"][0]["message"]["content"].strip()
        elif self.backend in {"auto", "google"}:
            try:
                from deep_translator import GoogleTranslator
            except ImportError as exc:
                raise RuntimeError("Install deep-translator or configure an OpenAI-compatible translation API") from exc
            translated = GoogleTranslator(source="en", target="zh-CN").translate(protected)
        elif self.backend in {"none", "disabled"}:
            return ""
        else:
            raise ValueError(f"Unknown translation backend: {self.backend}")
        return restore_terms(translated or "", markers)

    def translate_papers(self, papers: list[dict[str, Any]], workers: int = 4) -> list[dict[str, Any]]:
        tasks: dict[Any, tuple[dict[str, Any], str]] = {}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for paper in papers:
                if not paper.get("title_cn") and paper.get("title"):
                    tasks[pool.submit(self.translate, paper["title"])] = (paper, "title_cn")
                if not paper.get("abstract_cn") and paper.get("abstract"):
                    tasks[pool.submit(self.translate, paper["abstract"][:3000])] = (paper, "abstract_cn")
            for future in as_completed(tasks):
                paper, field = tasks[future]
                try:
                    paper[field] = future.result()
                except Exception as exc:
                    paper.setdefault("translation_errors", []).append(str(exc))
                    paper.setdefault(field, "")
        return papers
