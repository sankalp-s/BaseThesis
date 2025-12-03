"""Lightweight semantic similarity helper for contradiction detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None


NEGATION_WORDS = {
    "not",
    "never",
    "can't",
    "cannot",
    "won't",
    "no",
    "nothing",
    "nobody",
    "hardly",
    "barely",
    "rarely",
}


@dataclass
class SemanticMatch:
    text: str
    similarity: float
    turn_number: int


class SemanticMatcher:
    """Provides embedding-backed similarity + negation checks."""

    def __init__(self, similarity_threshold: float = 0.78) -> None:
        self.similarity_threshold = similarity_threshold
        self._cache: Dict[str, np.ndarray | set] = {}
        self._turn_index: Dict[str, int] = {}
        self._model = None

        if SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:  # pragma: no cover - optional dependency
                self._model = None

    def register_statement(self, text: str, turn_number: int) -> None:
        if text not in self._cache:
            self._cache[text] = self._encode(text)
            self._turn_index[text] = turn_number

    def find_similar(self, statement: str, top_k: int = 3) -> List[SemanticMatch]:
        if not self._cache:
            return []

        target_vector = self._encode(statement)
        matches: List[SemanticMatch] = []
        for text, vector in self._cache.items():
            similarity = self._similarity(target_vector, vector)
            if similarity >= self.similarity_threshold:
                matches.append(
                    SemanticMatch(
                        text=text,
                        similarity=float(similarity),
                        turn_number=self._turn_index.get(text, -1),
                    )
                )

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:top_k]

    def detect_contradiction(self, statement_a: str, statement_b: str) -> bool:
        sim = self._similarity(self._encode(statement_a), self._encode(statement_b))
        if sim < self.similarity_threshold:
            return False
        return self._has_negation_disagreement(statement_a, statement_b)

    def _encode(self, text: str) -> np.ndarray | set:
        if text in self._cache:
            return self._cache[text]

        if self._model is not None:
            return self._model.encode(text, normalize_embeddings=True)

        tokens = set(re.findall(r"[a-zA-Z']+", text.lower()))
        return tokens

    def _similarity(self, vector_a, vector_b) -> float:
        if self._model is not None:
            return float(np.dot(vector_a, vector_b))

        if not vector_a or not vector_b:
            return 0.0

        intersection = len(vector_a & vector_b)
        union = len(vector_a | vector_b)
        return intersection / union if union else 0.0

    def _has_negation_disagreement(self, text_a: str, text_b: str) -> bool:
        tokens_a = set(text_a.lower().split())
        tokens_b = set(text_b.lower().split())
        neg_a = tokens_a & NEGATION_WORDS
        neg_b = tokens_b & NEGATION_WORDS
        return (neg_a and not neg_b) or (neg_b and not neg_a)
