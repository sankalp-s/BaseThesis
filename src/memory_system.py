from __future__ import annotations


import re
import json
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, field

from adaptive_thresholds import AdaptiveThresholdController
from pattern_registry import PatternRegistry
from semantic_matcher import SemanticMatcher
from context_reasoner import ContextReasoner
from enum import Enum


class RetentionLevel(Enum):
    LONG_TERM = "long_term"      # Days/weeks/months
    SHORT_TERM = "short_term"    # 1-5 conversation turns
    IMMEDIATE = "immediate"       # Forget after this turn


@dataclass
class ConversationTurn:
    speaker: str
    text: str
    turn_number: int


@dataclass
class MemoryItem:
    content: str
    retention: RetentionLevel
    importance_score: float
    turn_number: int
    reasoning: str
    categories: List[str]
    context_rationale: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)


class ConversationalMemorySystem:

    def __init__(self, pattern_config_path: str | None = None, enable_semantic: bool = True):
        registry = PatternRegistry(pattern_config_path)
        loaded_patterns = registry.get_patterns()
        self.critical_patterns = loaded_patterns.get('critical', [])
        self.contextual_patterns = loaded_patterns.get('contextual', [])
        self.ephemeral_patterns = loaded_patterns.get('ephemeral', [])
        self.pattern_registry = registry

        # Runtime helpers
        self.memory_store: Dict[str, Dict] = {}
        self.threshold_controller = AdaptiveThresholdController()
        self.semantic_matcher = SemanticMatcher() if enable_semantic else None
        self.context_reasoner = ContextReasoner()
        
    def analyze_conversation(self, conversation: List[ConversationTurn]) -> List[MemoryItem]:
        memory_items = []
        
        for turn in conversation:
            items = self._analyze_turn(turn, conversation)
            memory_items.extend(items)
        
        # Post-processing: handle contradictions and temporal relationships
        memory_items = self._handle_contradictions(memory_items)
        memory_items = self._apply_temporal_decay(memory_items, len(conversation))
        
        return memory_items
    
    def _analyze_turn(self, turn: ConversationTurn, full_conversation: List[ConversationTurn]) -> List[MemoryItem]:
        
        # Skip very short turns (likely noise) - BUT check for critical keywords first
        critical_short_keywords = ['married', 'divorced', 'died', 'pregnant', 'allergy', 'PTSD', 'fired', 'quit']
        if len(turn.text.split()) < 3:
            # Allow short statements with critical keywords
            if not any(keyword in turn.text.lower() for keyword in critical_short_keywords):
                return [MemoryItem(
                    content=turn.text,
                    retention=RetentionLevel.IMMEDIATE,
                    importance_score=0,
                    turn_number=turn.turn_number,
                    reasoning="Too short to be meaningful",
                    categories=['noise']
                )]
        
        # Extract sentences/statements
        statements = self._extract_statements(turn.text)
        memory_items = []
        
        for statement in statements:
            item = self._classify_statement(statement, turn, full_conversation)
            if self.context_reasoner:
                rationale = self.context_reasoner.build_rationale(item.categories)
                if rationale:
                    item.context_rationale = rationale
                    item.reasoning += f" | {rationale}"
                self.context_reasoner.update(
                    turn_number=item.turn_number,
                    content=item.content,
                    categories=item.categories,
                    retention=item.retention.value,
                )
            if self.semantic_matcher:
                self.semantic_matcher.register_statement(item.content, item.turn_number)
            self.threshold_controller.record_decision(item.retention.value, item.importance_score)
            memory_items.append(item)
        
        return memory_items
    
    def _extract_statements(self, text: str) -> List[str]:
        # Split by sentence boundaries
        sentences = re.split(r'[.!?]+', text)
        statements = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        # If no clear sentences, return the whole text
        if not statements:
            return [text]
        
        return statements
    
    def _classify_statement(self, statement: str, turn: ConversationTurn, 
                           full_conversation: List[ConversationTurn]) -> MemoryItem:
        
        importance_score = 0
        categories = []
        reasoning_parts = []
        
        # Check critical patterns (highest priority)
        for pattern, category, weight in self.critical_patterns:
            if re.search(pattern, statement, re.IGNORECASE):
                importance_score += weight
                categories.append(category)
                reasoning_parts.append(f"Critical: {category}")
        
        # Check contextual patterns
        for pattern, category, weight in self.contextual_patterns:
            if re.search(pattern, statement, re.IGNORECASE):
                importance_score += weight
                categories.append(category)
                reasoning_parts.append(f"Contextual: {category}")
        
        # Check ephemeral patterns (reduce importance)
        for pattern, category, weight in self.ephemeral_patterns:
            if re.search(pattern, statement, re.IGNORECASE):
                importance_score += weight
                categories.append(category)
                reasoning_parts.append(f"Ephemeral: {category}")
        
        # Additional heuristics
        
        # Length and complexity bonus
        word_count = len(statement.split())
        if word_count > 15:
            importance_score += 3
            reasoning_parts.append("Detailed statement")
        
        # Proper nouns (names, places) - likely important
        proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', statement)
        if len(proper_nouns) > 1:
            importance_score += 4
            categories.append('named_entity')
            reasoning_parts.append("Contains named entities")
        
        # Numbers and dates - often important facts
        if re.search(r'\b\d+\b', statement):
            importance_score += 2
            categories.append('quantitative')
            reasoning_parts.append("Contains specific numbers/dates")
        
        # First-person statements often more important than questions
        if re.search(r'\b(I|my|me|I\'m|I\'ve)\b', statement, re.IGNORECASE):
            importance_score += 2
            reasoning_parts.append("First-person statement")
        
        # Questions are typically short-term
        if statement.strip().endswith('?'):
            importance_score -= 3
            categories.append('question')
            reasoning_parts.append("Question (short-term)")
        
        # Temporal references
        if re.search(r'\b(always|never|forever|permanently)\b', statement, re.IGNORECASE):
            importance_score += 5
            reasoning_parts.append("Permanent/absolute statement")
        
        if re.search(r'\b(today|now|currently|right now)\b', statement, re.IGNORECASE):
            importance_score -= 2
            reasoning_parts.append("Immediate temporal context")
        
        # Determine retention level using adaptive thresholds
        thresholds = self.threshold_controller.snapshot
        if importance_score >= thresholds.long_term:
            retention = RetentionLevel.LONG_TERM
        elif importance_score >= thresholds.short_term:
            retention = RetentionLevel.SHORT_TERM
        else:
            retention = RetentionLevel.IMMEDIATE
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Default classification"
        
        return MemoryItem(
            content=statement,
            retention=retention,
            importance_score=importance_score,
            turn_number=turn.turn_number,
            reasoning=reasoning,
            categories=categories if categories else ['uncategorized']
        )
    
    def _handle_contradictions(self, memory_items: List[MemoryItem]) -> List[MemoryItem]:
        # Group by semantic similarity (simplified: look for similar keywords)
        for i, item1 in enumerate(memory_items):
            for j, item2 in enumerate(memory_items[i+1:], start=i+1):
                contradiction_detected = self._are_potentially_contradictory(item1, item2)
                if not contradiction_detected and self.semantic_matcher:
                    contradiction_detected = self.semantic_matcher.detect_contradiction(
                        item1.content,
                        item2.content
                    )

                if contradiction_detected:
                    # Boost importance of newer information
                    memory_items[j].importance_score += 5
                    memory_items[j].reasoning += " | UPDATE: Contradicts earlier statement"
                    
                    # Mark older for potential replacement
                    memory_items[i].reasoning += " | SUPERSEDED: Later contradicting info exists"
        
        return memory_items
    
    def _are_potentially_contradictory(self, item1: MemoryItem, item2: MemoryItem) -> bool:
        # Simple heuristic: same categories, different turn numbers, both substantive
        if item1.turn_number == item2.turn_number:
            return False
        
        # Check for overlapping categories OR semantically related categories
        common_categories = set(item1.categories) & set(item2.categories)
        
        # Also check for semantically related categories (preferences vs restrictions, current vs past states)
        related_pairs = [
            {'strong_preference', 'dietary_restriction'},
            {'strong_preference', 'dietary'},
            {'dietary', 'dietary_restriction'},
            {'dietary', 'life_change'},
            {'strong_preference', 'life_change'},
            {'preference', 'life_change'},
            {'career', 'life_change'},
            {'career', 'past_status'},
            {'career', 'status_change'},
            {'relationship_status', 'past_status'},
            {'relationship_status', 'status_change'},
            {'occasional_behavior', 'strong_preference'},  # sometimes → never
        ]
        
        categories_related = any(
            set(item1.categories) & pair and set(item2.categories) & pair 
            for pair in related_pairs
        )
        
        if not (common_categories or categories_related) or 'noise' in (set(item1.categories) | set(item2.categories)):
            return False
        
        # Check for negation patterns suggesting contradiction
        text1_lower = item1.content.lower()
        text2_lower = item2.content.lower()
        text1_words = set(item1.content.lower().split())
        text2_words = set(item2.content.lower().split())
        
        # Filter out hypotheticals - not contradictions
        hypothetical_markers = ['would', 'could', 'might', 'if', 'thinking about', 'planning to', 'considering']
        if any(marker in text1_lower or marker in text2_lower for marker in hypothetical_markers):
            # Don't treat hypothetical vs actual as contradiction
            return False
        
        # Comprehensive negation detection
        negation_patterns = [
            # Single word negations
            'not', 'never', "don't", "doesn't", "didn't", "can't", "cannot", "won't", "wouldn't",
            # Phrase negations
            'no longer', 'not anymore', 'used to', 'quit', 'stopped', 'gave up',
            # Reversal words
            'but', 'however', 'although', 'though', 'actually',
            # Past tense markers (was vs is)
            'was', 'were', 'divorced', 'fired', 'quit'
        ]
        
        # Check for multi-word patterns first
        has_negation = (
            'no longer' in text2_lower or
            'not anymore' in text2_lower or
            'used to' in text2_lower or
            any(neg in text2_words for neg in negation_patterns)
        )
        
        # Special case: Double negation detection (don't like → don't dislike)
        # Count negations in each statement
        neg_count1 = sum(1 for neg in ["don't", "doesn't", "not", "never"] if neg in text1_lower)
        neg_count2 = sum(1 for neg in ["don't", "doesn't", "not", "never"] if neg in text2_lower)
        
        # If both have negations and have opposite sentiment words, it's a contradiction
        if neg_count1 > 0 and neg_count2 > 0:
            sentiment_opposites = [
                ('like', 'dislike'), ('love', 'hate'), ('enjoy', 'dislike'),
                ('want', 'refuse'), ('prefer', 'avoid')
            ]
            for pos, neg in sentiment_opposites:
                if (pos in text1_lower and neg in text2_lower) or (neg in text1_lower and pos in text2_lower):
                    has_negation = True
                    break
        
        # Check word overlap (allow for word stems: run/running, marry/married, etc.)
        def get_word_stems(words):
            """Simple stemming: remove common suffixes"""
            stems = set()
            for word in words:
                stem = word
                # Try removing suffixes in order (longer first to avoid double-stripping)
                for suffix in ['ning', 'ing', 'ied', 'ed', 'ary', 'ian', 'ly', 'es', 's']:
                    if len(word) > 4 and word.endswith(suffix):
                        stem = word[:-len(suffix)]
                        # Handle consonant doubling: running -> run (not runn)
                        if suffix in ['ning', 'ned', 'med'] and len(stem) > 2 and stem[-2:] == stem[-1] * 2:
                            stem = stem[:-1]
                        break
                stems.add(stem)
                stems.add(word)  # Also keep original
            return stems
        
        text1_stems = get_word_stems(text1_words)
        text2_stems = get_word_stems(text2_words)
        stem_overlap = len(text1_stems & text2_stems)
        
        has_overlap = stem_overlap >= 2  # At least 2 word stems in common
        
        return has_negation and has_overlap
    
    def _apply_temporal_decay(self, memory_items: List[MemoryItem], total_turns: int) -> List[MemoryItem]:
        for item in memory_items:
            if item.retention == RetentionLevel.SHORT_TERM:
                # Calculate how many turns ago this was mentioned
                turns_ago = total_turns - item.turn_number
                
                # Decay after 5 turns
                if turns_ago > 5:
                    decay_factor = (turns_ago - 5) * 0.5
                    item.importance_score -= decay_factor
                    
                    # If decayed too much, downgrade to immediate
                    if item.importance_score < 3:
                        item.retention = RetentionLevel.IMMEDIATE
                        item.reasoning += " | DECAYED: Too many turns ago"
        
        return memory_items
    
    def format_results(self, memory_items: List[MemoryItem]) -> str:
        output = []
        output.append("=" * 80)
        output.append("CONVERSATIONAL MEMORY ANALYSIS")
        output.append("=" * 80)
        output.append("")
        
        # Group by retention level
        long_term = [m for m in memory_items if m.retention == RetentionLevel.LONG_TERM]
        short_term = [m for m in memory_items if m.retention == RetentionLevel.SHORT_TERM]
        immediate = [m for m in memory_items if m.retention == RetentionLevel.IMMEDIATE]
        
        output.append(f"📌 LONG-TERM MEMORIES ({len(long_term)}): Persist for days/weeks/months")
        output.append("-" * 80)
        for item in sorted(long_term, key=lambda x: x.importance_score, reverse=True):
            output.append(f"  Turn {item.turn_number} | Score: {item.importance_score:.1f}")
            output.append(f"  💬 \"{item.content}\"")
            output.append(f"  🏷️  Categories: {', '.join(item.categories)}")
            output.append(f"  💡 Reasoning: {item.reasoning}")
            output.append("")
        
        output.append(f"\n⏱️  SHORT-TERM MEMORIES ({len(short_term)}): Keep for 1-5 turns")
        output.append("-" * 80)
        for item in sorted(short_term, key=lambda x: x.importance_score, reverse=True):
            output.append(f"  Turn {item.turn_number} | Score: {item.importance_score:.1f}")
            output.append(f"  💬 \"{item.content}\"")
            output.append(f"  🏷️  Categories: {', '.join(item.categories)}")
            output.append(f"  💡 Reasoning: {item.reasoning}")
            output.append("")
        
        output.append(f"\n🗑️  IMMEDIATE DISCARD ({len(immediate)}): Forget after this turn")
        output.append("-" * 80)
        for item in immediate[:10]:  # Show only first 10 to avoid clutter
            output.append(f"  Turn {item.turn_number} | Score: {item.importance_score:.1f}")
            output.append(f"  💬 \"{item.content}\"")
            output.append(f"  💡 Reasoning: {item.reasoning}")
            output.append("")
        
        if len(immediate) > 10:
            output.append(f"  ... and {len(immediate) - 10} more items")
        
        output.append("\n" + "=" * 80)
        output.append("SUMMARY STATISTICS")
        output.append("=" * 80)
        output.append(f"Total items analyzed: {len(memory_items)}")
        output.append(f"Long-term: {len(long_term)} ({len(long_term)/len(memory_items)*100:.1f}%)")
        output.append(f"Short-term: {len(short_term)} ({len(short_term)/len(memory_items)*100:.1f}%)")
        output.append(f"Immediate: {len(immediate)} ({len(immediate)/len(memory_items)*100:.1f}%)")
        
        return "\n".join(output)

    def get_context_window(self) -> List[Dict[str, Any]]:
        if not self.context_reasoner:
            return []
        return self.context_reasoner.summarize_window()


def parse_conversation_file(filepath: str) -> List[ConversationTurn]:
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    turns = []
    turn_number = 1
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Expected format: "Speaker: Text"
        if ':' in line:
            speaker, text = line.split(':', 1)
            turns.append(ConversationTurn(
                speaker=speaker.strip(),
                text=text.strip(),
                turn_number=turn_number
            ))
            turn_number += 1
    
    return turns


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python memory_system.py <conversation_file>")
        print("\nConversation file format:")
        print("  Speaker1: Hello, how are you?")
        print("  Speaker2: I'm doing well, thanks!")
        print("  ...")
        sys.exit(1)
    
    conversation_file = sys.argv[1]
    
    # Parse conversation
    print(f"Loading conversation from: {conversation_file}")
    conversation = parse_conversation_file(conversation_file)
    print(f"Loaded {len(conversation)} conversation turns\n")
    
    # Initialize system
    system = ConversationalMemorySystem()
    
    # Analyze
    print("Analyzing conversation...\n")
    memory_items = system.analyze_conversation(conversation)
    
    # Display results
    results = system.format_results(memory_items)
    print(results)
    
    # Save results
    output_file = conversation_file.replace('.txt', '_analysis.txt')
    with open(output_file, 'w') as f:
        f.write(results)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
