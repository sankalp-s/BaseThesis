
from __future__ import annotations

import hashlib
import json
import logging
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    from llm_integration import RealLLMAnalyzer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    RealLLMAnalyzer = None  # type: ignore

logger = logging.getLogger(__name__)


class LLMBroker:
    def __init__(self, use_real_llm: bool = False, api_key: Optional[str] = None):
        self.use_real_llm = use_real_llm
        self._real_client = None
        if use_real_llm and RealLLMAnalyzer is not None:
            try:
                self._real_client = RealLLMAnalyzer(api_key=api_key)
            except Exception as exc:  # pragma: no cover - optional
                logger.warning("Falling back to mock LLM broker: %s", exc)
                self.use_real_llm = False
        else:
            self.use_real_llm = False

        self._cache: Dict[str, Dict] = {}
        self._stats = {"calls": 0, "cache_hits": 0}

    def analyze(self, statement: str, context: Optional[Dict] = None) -> Dict:
        cache_key = self._make_cache_key(statement, context)
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            return self._cache[cache_key]

        if self.use_real_llm and self._real_client:
            result = self._real_client.analyze_statement(statement, context)
        else:
            result = self._mock_analysis(statement)

        self._cache[cache_key] = result
        self._stats["calls"] += 1
        return result

    def get_stats(self) -> Dict:
        real_stats = self._real_client.get_usage_stats() if self._real_client else {}
        base_stats = {
            'calls': self._stats['calls'],
            'cache_hits': self._stats['cache_hits'],
            'total_calls': real_stats.get('total_calls', self._stats['calls']),
            'total_tokens': real_stats.get('total_tokens', 0),
            'avg_tokens_per_call': real_stats.get('avg_tokens_per_call', 0.0),
            'estimated_cost_usd': real_stats.get('estimated_cost_usd', 0.0),
            'model': real_stats.get('model', 'llm-broker-mock' if not self.use_real_llm else 'llm-broker-proxy'),
        }
        if real_stats:
            base_stats.update({f"real_{k}": v for k, v in real_stats.items()})
        return base_stats

    def get_usage_stats(self) -> Dict:
        """Compatibility helper mirroring RealLLMAnalyzer interface."""
        return self.get_stats()

    def _make_cache_key(self, statement: str, context: Optional[Dict]) -> str:
        payload = json.dumps({"statement": statement, "context": context or {}}, sort_keys=True)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _mock_analysis(self, statement: str) -> Dict:
        text = statement.lower()
        importance_boost = 0
        categories = []
        reasoning = "Semantic fallback"
        if "phobia" in text or "terrified" in text:
            importance_boost = 12
            categories = ["mental_health", "safety_concern"]
            reasoning = "Detected fear/trauma language"
        elif "medication" in text or "diagnosed" in text:
            importance_boost = 8
            categories = ["medical"]
            reasoning = "Detected implicit medical detail"
        elif "keeps happening" in text or "recurring" in text:
            importance_boost = 6
            categories = ["pattern"]
            reasoning = "Detected recurring pattern language"
        return {
            "importance_boost": importance_boost,
            "categories": categories,
            "reasoning": reasoning,
            "confidence": 0.75 if importance_boost else 0.5,
        }
