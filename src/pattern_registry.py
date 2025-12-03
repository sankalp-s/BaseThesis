"""Pattern registry loader for adaptive memory system."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PatternDefinition:
    """Represents a single regex pattern configuration."""

    pattern: str
    category: str
    weight: int
    enabled: bool = True

    def as_tuple(self) -> Tuple[str, str, int]:
        return self.pattern, self.category, self.weight


class PatternRegistry:
    """Loads and caches regex patterns from disk with sane defaults."""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = Path(config_path) if config_path else Path("config/pattern_registry.json")
        self._cache: Dict[str, List[PatternDefinition]] | None = None

    def load(self, force_reload: bool = False) -> Dict[str, List[PatternDefinition]]:
        if self._cache is not None and not force_reload:
            return self._cache

        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                self._cache = self._parse_config(data)
                logger.info("Loaded pattern registry from %s", self.config_path)
                return self._cache
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to load pattern registry %s: %s", self.config_path, exc)

        logger.info("Using built-in pattern registry defaults")
        self._cache = self._default_patterns()
        return self._cache

    def _parse_config(self, data: Dict[str, List[Dict]]) -> Dict[str, List[PatternDefinition]]:
        parsed: Dict[str, List[PatternDefinition]] = {"critical": [], "contextual": [], "ephemeral": []}
        for key in parsed.keys():
            for entry in data.get(key, []):
                parsed[key].append(
                    PatternDefinition(
                        pattern=entry["pattern"],
                        category=entry["category"],
                        weight=int(entry.get("weight", 0)),
                        enabled=entry.get("enabled", True),
                    )
                )
        return parsed

    def _default_patterns(self) -> Dict[str, List[PatternDefinition]]:
        defaults = {
            "critical": [
                (r"\b(allerg(?:y|ies|ic)|medical condition|diagnosed|disease|disorder|syndrome)\b", "medical", 15),
                (r"\b(panic attack|anxiety|PTSD|trauma|phobia|depression)\b", "mental_health", 20),
                (r"\b(medication|prescription|treatment|therapy)\b", "medical_treatment", 12),
                (r"\b(afraid|fear|terrified|scared|danger|unsafe)\b", "safety_concern", 18),
                (r"\b(emergency|urgent|critical|life-threatening)\b", "emergency", 25),
                (r"\b(my name is|I'm called|call me)\b", "identity", 20),
                (r"\b(I am|I'm) (a |an )?\w+ (person|man|woman)", "identity", 15),
                (r"\b(born|birthday|age \d+|years old)\b", "personal_info", 10),
                (r"\b(my (wife|husband|partner|spouse|child|son|daughter|mother|father|parent))\b", "family", 14),
                (r"\b(married|divorced|widowed|relationship)\b", "relationship_status", 12),
                (r"\b(died|death|passed away|funeral|loss|grief)\b", "grief", 18),
                (r"\b(pregnant|expecting|baby|birth)\b", "major_life_event", 16),
                (r"\b(job loss|fired|laid off|unemployed)\b", "major_life_event", 14),
                (r"\b(never|always|hate|love|cannot|can't stand)\b", "strong_preference", 12),
                (r"\b(vegetarian|vegan|kosher|halal|dietary)\b", "dietary", 13),
                (r"\b(can't|cannot|don't|no longer|stopped) (eat|have|consume)\b", "dietary_restriction", 10),
                (r"\b(used to|no longer|stopped|quit|gave up)\b", "life_change", 12),
                (r"\b(was|were) (married|employed|working|living)\b", "past_status", 12),
                (r"\b(divorced|separated|fired|laid off|quit)\b", "status_change", 12),
                (r"\b(sometimes|occasionally|rarely) (drink|eat|do|go)\b", "occasional_behavior", 8),
            ],
            "contextual": [
                (r"\b(goal|plan|want to|need to|trying to)\b", "goal", 8),
                (r"\b(prefer|like|enjoy|interested in|dislike|hate)\b", "preference", 6),
                (r"\b(meeting|appointment|schedule|calendar)\b", "logistics", 7),
                (r"\b(address|phone|email|contact)\b", "contact_info", 9),
                (r"\b(work at|job|career|profession)\b", "career", 10),
            ],
            "ephemeral": [
                (r"\b(hello|hi|hey|goodbye|bye|see you)\b", "greeting", -5),
                (r"\b(yes|no|okay|ok|sure|maybe|perhaps)\b", "confirmation", -3),
                (r"\b(um|uh|like|you know|I mean)\b", "filler", -8),
                (r"\b(thanks|thank you|please)\b", "pleasantry", -4),
                (r"\b(what|when|where|why|how)\b", "question_word", -2),
            ],
        }
        return {k: [PatternDefinition(*entry) for entry in v] for k, v in defaults.items()}

    def get_patterns(self) -> Dict[str, List[Tuple[str, str, int]]]:
        data = self.load()
        return {
            group: [definition.as_tuple() for definition in definitions if definition.enabled]
            for group, definitions in data.items()
        }


def load_patterns(config_path: str | None = None) -> Dict[str, List[Tuple[str, str, int]]]:
    """Helper for one-off loads."""
    return PatternRegistry(config_path).get_patterns()
