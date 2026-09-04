from __future__ import annotations

import math
from typing import Any, Callable

from ..utils import normalize_openai_api_base, openai_api_endpoint, request_json


class EmbeddingRanker:
    """Stage 2 semantic scorer with pluggable local or OpenAI-compatible embeddings."""

    def __init__(self, *, backend: str, model: str, api_base: str = "", api_key: str = "",
                 timeout: float = 30.0, retries: int = 3,
                 encoder: Callable[[list[str]], list[list[float]]] | None = None):
        self.backend = backend
        self.model = model
        self.api_base = normalize_openai_api_base(api_base)
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self._encoder = encoder

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if self._encoder:
            return self._encoder(texts)
        if self.backend == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("Install optional dependency: pip install sentence-transformers") from exc
            model = SentenceTransformer(self.model)
            return model.encode(texts, normalize_embeddings=True).tolist()
        if self.backend in {"openai", "openai-compatible"}:
            if not self.api_base or not self.api_key:
                raise RuntimeError("embedding_api_base and embedding_api_key are required")
            data = request_json(
                openai_api_endpoint(self.api_base, "embeddings"),
                method="POST",
                payload={"model": self.model, "input": texts},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
                retries=self.retries,
            )
            return [row["embedding"] for row in sorted(data["data"], key=lambda row: row["index"])]
        raise ValueError(f"Unknown embedding backend: {self.backend}")

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
        if not denominator:
            return 0.0
        raw = sum(x * y for x, y in zip(a, b)) / denominator
        # Negative cosine values are irrelevant, while positive cosine is already
        # a useful 0-1 relevance scale for modern text-embedding models.
        return max(0.0, min(1.0, raw))

    def rank(self, papers: list[dict[str, Any]], profile_description: str) -> list[dict[str, Any]]:
        if not papers:
            return papers
        texts = [profile_description] + [f"{p.get('title', '')}\n{p.get('abstract', '')}" for p in papers]
        vectors = self._encode(texts)
        profile_vector = vectors[0]
        for paper, vector in zip(papers, vectors[1:]):
            paper["semantic_score"] = round(self._cosine(profile_vector, vector), 6)
        ranked = sorted(papers, key=lambda p: p.get("semantic_score", 0.0), reverse=True)
        for index, paper in enumerate(ranked, 1):
            paper["semantic_rank"] = index
        return papers
