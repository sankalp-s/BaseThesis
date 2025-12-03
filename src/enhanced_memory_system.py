import re
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from memory_system import (
    RetentionLevel, ConversationTurn, MemoryItem, ConversationalMemorySystem
)
from llm_broker import LLMBroker

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LLMAnalysis:
    suggested_level: RetentionLevel
    confidence: float  # 0-1
    reasoning: str
    entities_found: List[str] = field(default_factory=list)


class EnhancedMemorySystem(ConversationalMemorySystem):
    
    def __init__(self, enable_llm: bool = True, llm_api_key: Optional[str] = None, use_real_llm: bool = False):
        super().__init__()
        self.enable_llm = enable_llm
        self.use_llm = enable_llm  # Backward compatibility
        self.use_real_llm = use_real_llm
        self.llm_api_key = llm_api_key or os.getenv('OPENAI_API_KEY')
        self.llm_calls_count = 0
        self.llm_enhanced_items = []
        
        broker_real_flag = self.use_real_llm and bool(self.llm_api_key)
        self.llm_broker = LLMBroker(use_real_llm=broker_real_flag, api_key=self.llm_api_key)
        self.use_real_llm = self.llm_broker.use_real_llm
        self.real_llm_analyzer = self.llm_broker
        
        # Store base system reference for easier access
        self.base_system = self
        
        # Emotional language patterns that might indicate importance
        self.emotional_indicators = [
            r'\b(terrified|terrifying|terrifies|frightens|scares)\b',
            r'\b(devastated|heartbroken|tragic|traumatic)\b',
            r'\b(desperate|urgent|critical|emergency)\b',
            r'\b(anxious|worried|concerned|stressed)\b',
        ]
    
    def _classify_statement(self, statement: str, turn: ConversationTurn, 
                           full_conversation: List[ConversationTurn]) -> MemoryItem:
        
        # First, use the fast path (pattern matching)
        item = super()._classify_statement(statement, turn, full_conversation)
        
        # Determine if we need LLM enhancement
        needs_llm = self._should_invoke_llm(statement, item)
        
        if needs_llm and self.use_llm and self.llm_api_key:
            enhanced_item = self._enhance_with_llm(statement, item, turn)
            if enhanced_item:
                self.llm_calls_count += 1
                self.llm_enhanced_items.append(enhanced_item)
                return enhanced_item
        
        return item
    
    def _should_invoke_llm(self, statement: str, item: MemoryItem) -> bool:
        
        # Case 1: Score is near threshold boundaries (uncertain classification)
        if 10 <= item.importance_score <= 14:  # Near long-term threshold
            return True
        if 2 <= item.importance_score <= 6:    # Near short-term threshold
            return True
        
        # Case 2: Contains emotional language but low score
        has_emotional = any(re.search(pattern, statement, re.IGNORECASE) 
                          for pattern in self.emotional_indicators)
        if has_emotional and item.importance_score < 15:
            return True
        
        # Case 3: First-person statement with strong language but not caught by patterns
        if re.search(r'\b(I|my|me)\b', statement, re.IGNORECASE):
            strong_words = ['never', 'always', 'must', 'need', 'have to', 'essential']
            if any(word in statement.lower() for word in strong_words) and item.importance_score < 10:
                return True
        
        return False
    
    def _enhance_with_llm(self, statement: str, base_item: MemoryItem, 
                         turn: ConversationTurn) -> Optional[MemoryItem]:
        
        try:
            llm_analysis = self.llm_broker.analyze(
                statement,
                context={
                    'importance': base_item.importance_score,
                    'categories': base_item.categories,
                    'turn': turn.turn_number,
                }
            )
            
            if llm_analysis:
                # Adjust importance score based on LLM insights
                score_adjustment = llm_analysis.get('importance_boost', 0)
                new_score = base_item.importance_score + score_adjustment
                
                thresholds = self.threshold_controller.snapshot
                if new_score >= thresholds.long_term:
                    retention = RetentionLevel.LONG_TERM
                elif new_score >= thresholds.short_term:
                    retention = RetentionLevel.SHORT_TERM
                else:
                    retention = RetentionLevel.IMMEDIATE
                
                # Merge categories
                new_categories = list(set(base_item.categories + llm_analysis.get('categories', [])))
                
                # Enhanced reasoning
                enhanced_reasoning = (
                    f"{base_item.reasoning} | LLM: {llm_analysis.get('reasoning', '')}"
                )
                
                return MemoryItem(
                    content=statement,
                    retention=retention,
                    importance_score=new_score,
                    turn_number=turn.turn_number,
                    reasoning=enhanced_reasoning,
                    categories=new_categories
                )
        
        except Exception as e:
            # If LLM fails, return original item
            print(f"LLM enhancement failed: {e}")
            return base_item
        
        return None
    
    def analyze_conversation(
        self, 
        conversation: List[Dict[str, str]],
        start_turn: int = 0
    ) -> List[Tuple[MemoryItem, Optional[LLMAnalysis]]]:
        results = []
        
        # Convert to ConversationTurn format
        turns = []
        for i, turn_dict in enumerate(conversation):
            turn = ConversationTurn(
                speaker=turn_dict.get('speaker', 'user'),
                text=turn_dict.get('content', ''),
                turn_number=start_turn + i
            )
            turns.append(turn)
        
        # Process through base system first (inherited method)
        memory_items = super().analyze_conversation(turns)
        
        # Check if LLM enhancement is needed for each item
        for item in memory_items:
            llm_analysis = None
            
            if self.enable_llm and self._should_invoke_llm(item.content, item):
                broker_result = self.llm_broker.analyze(
                    item.content,
                    context={'turn': item.turn_number, 'categories': item.categories}
                )
                if broker_result:
                    llm_analysis = LLMAnalysis(
                        suggested_level=item.retention,
                        confidence=broker_result.get('confidence', 0.85),
                        reasoning=broker_result.get('reasoning', 'LLM analysis'),
                        entities_found=broker_result.get('entities', [])
                    )
            
            results.append((item, llm_analysis))
        
        return results
    
    def get_llm_stats(self) -> Dict:
        return {
            'total_llm_calls': self.llm_calls_count,
            'items_enhanced': len(self.llm_enhanced_items),
            'enhancement_rate': f"{len(self.llm_enhanced_items) / max(1, self.llm_calls_count) * 100:.1f}%"
        }


# Example: Real LLM integration (commented out, requires API key)
"""
def _real_llm_analysis(self, statement: str) -> Optional[Dict]:
    import openai
    
    openai.api_key = self.llm_api_key
    
    prompt = f'''
    Analyze this conversational statement for memory importance:
    
    Statement: "{statement}"
    
    Determine:
    1. Is this critical information that should be remembered long-term?
    2. What categories does it fall into? (medical, safety, identity, preference, etc.)
    3. On a scale of 0-25, how important is this to remember?
    
    Return JSON with: importance_boost (0-15), categories (list), reasoning (string)
    '''
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in conversational memory systems."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"LLM API error: {e}")
        return None
"""


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python enhanced_memory_system.py <conversation_file>")
        sys.exit(1)
    
    conversation_file = sys.argv[1]
    
    # Parse conversation
    from memory_system import parse_conversation_file
    print(f"Loading conversation from: {conversation_file}")
    conversation = parse_conversation_file(conversation_file)
    print(f"Loaded {len(conversation)} conversation turns\n")
    
    # Initialize enhanced system
    print("Initializing Enhanced Memory System (with LLM fallback)...")
    system = EnhancedMemorySystem(use_llm=True)
    
    # Analyze
    print("Analyzing conversation...\n")
    memory_items = system.analyze_conversation(conversation)
    
    # Display results
    results = system.format_results(memory_items)
    print(results)
    
    # Show LLM statistics
    print("\n" + "=" * 80)
    print("LLM ENHANCEMENT STATISTICS")
    print("=" * 80)
    stats = system.get_llm_stats()
    print(f"Total LLM calls: {stats['total_llm_calls']}")
    print(f"Items enhanced: {stats['items_enhanced']}")
    print(f"Enhancement rate: {stats['enhancement_rate']}")
    
    if system.llm_enhanced_items:
        print("\nLLM-Enhanced Items:")
        for item in system.llm_enhanced_items[:5]:  # Show first 5
            print(f"  • {item.content[:60]}...")
            print(f"    Score: {item.importance_score} | {item.retention.value}")
    
    # Save results
    output_file = conversation_file.replace('.txt', '_enhanced_analysis.txt')
    with open(output_file, 'w') as f:
        f.write(results)
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("LLM ENHANCEMENT STATISTICS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total LLM calls: {stats['total_llm_calls']}\n")
        f.write(f"Items enhanced: {stats['items_enhanced']}\n")
        f.write(f"Enhancement rate: {stats['enhancement_rate']}\n")
    
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
