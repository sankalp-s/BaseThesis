"""Maintains sliding window context and generates rationales."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List


@dataclass
class ContextEvidence:
    turn_number: int
    content: str
    categories: List[str]
    retention: str


class ContextReasoner:
    def __init__(self, window_size: int = 8):
        self.window: Deque[ContextEvidence] = deque(maxlen=window_size)

    def update(self, turn_number: int, content: str, categories: List[str], retention: str) -> None:
        self.window.append(
            ContextEvidence(
                turn_number=turn_number,
                content=content,
                categories=categories,
                retention=retention,
            )
        )

    def build_rationale(self, categories: List[str]) -> str:
        if not categories:
            return ""
        relevant = [entry for entry in self.window if set(entry.categories) & set(categories)]
        if not relevant:
            return ""
        snippets = [f"Turn {entry.turn_number}: {entry.content[:80]}" for entry in relevant[-3:]]
        return "Context evidence → " + " | ".join(snippets)

    def summarize_window(self) -> List[Dict]:
        return [
            {
                "turn": entry.turn_number,
                "content": entry.content,
                "categories": entry.categories,
                "retention": entry.retention,
            }
            for entry in list(self.window)
        ]
