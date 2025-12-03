import os
from typing import Optional, Dict
from dotenv import load_dotenv
from openai import OpenAI
import json
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class RealLLMAnalyzer:
    """
    Real LLM integration using OpenAI API.
    Provides semantic understanding for conversation memory classification.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize LLM analyzer.
        
        Args:
            api_key: OpenAI API key (or uses OPENAI_API_KEY env var)
            model: Model to use (gpt-4o-mini for cost-efficiency, gpt-4 for best quality)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.total_calls = 0
        self.total_tokens = 0
        
        logger.info(f"Initialized RealLLMAnalyzer with model {model}")
    
    def analyze_statement(
        self, 
        statement: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze a conversation statement for memory importance.
        
        Args:
            statement: The text to analyze
            context: Optional conversation context
        
        Returns:
            Dictionary with:
            - retention_level: 'long_term', 'short_term', or 'immediate'
            - confidence: 0-1 score
            - reasoning: Explanation of classification
            - categories: List of relevant categories
            - importance_boost: Suggested score adjustment
        """
        system_prompt = """You are an expert at analyzing conversation content to determine what information should be remembered long-term versus what can be forgotten.

Classify statements into three retention levels:

1. LONG_TERM - Critical information that must be remembered permanently:
   - Medical conditions, allergies, disabilities
   - Safety concerns, emergency contacts
   - Personal identity (name, relationships, occupation)
   - Major life events, trauma, phobias
   - Core preferences that define the person

2. SHORT_TERM - Contextual information useful for near-term:
   - Current projects, tasks, short-term plans
   - Temporary states (mood, health symptoms)
   - Recent events worth remembering
   - Conversation-specific context

3. IMMEDIATE - Trivial information with no lasting value:
   - Greetings, small talk, acknowledgments
   - Weather, time, generic comments
   - Filler words, conversational maintenance
   - Information that's obvious or not worth storing

Analyze the statement and respond with a JSON object containing:
{
  "retention_level": "long_term" | "short_term" | "immediate",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why this classification was chosen",
  "categories": ["medical", "safety", "identity", etc.],
  "importance_boost": 0-20 (additional points for importance score)
}

Be conservative - when in doubt, prefer longer retention for potentially important information."""

        user_prompt = f"""Analyze this conversation statement:

Statement: "{statement}"
"""
        
        if context:
            user_prompt += f"\nContext: {json.dumps(context, indent=2)}"
        
        user_prompt += "\n\nProvide your analysis as a JSON object."
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent classification
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            self.total_calls += 1
            self.total_tokens += response.usage.total_tokens
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            logger.info(
                f"LLM analysis: {statement[:50]}... -> {result['retention_level']} "
                f"(confidence: {result['confidence']:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Return safe default
            return {
                'retention_level': 'short_term',
                'confidence': 0.5,
                'reasoning': f'LLM analysis failed: {str(e)}',
                'categories': [],
                'importance_boost': 0
            }
    
    def batch_analyze(
        self,
        statements: list,
        context: Optional[Dict] = None
    ) -> list:
        """
        Analyze multiple statements (more efficient than individual calls).
        
        Args:
            statements: List of statements to analyze
            context: Optional shared context
        
        Returns:
            List of analysis results
        """
        system_prompt = """You are an expert at analyzing conversation content to determine what information should be remembered long-term versus what can be forgotten.

Classify each statement into three retention levels:
- LONG_TERM: Critical info (medical, safety, identity)
- SHORT_TERM: Contextual info (current tasks, recent events)
- IMMEDIATE: Trivial info (greetings, small talk)

Respond with a JSON array of objects, one per statement."""

        statements_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(statements)])
        
        user_prompt = f"""Analyze these {len(statements)} conversation statements:

{statements_text}

Provide analysis for each as a JSON array of objects with:
{{
  "statement_number": 1-{len(statements)},
  "retention_level": "long_term" | "short_term" | "immediate",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "categories": ["medical", "safety", etc.],
  "importance_boost": 0-20
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            self.total_calls += 1
            self.total_tokens += response.usage.total_tokens
            
            result = json.loads(response.choices[0].message.content)
            
            # Extract results array
            if 'results' in result:
                return result['results']
            elif 'analyses' in result:
                return result['analyses']
            else:
                # Assume the result itself is an array
                return list(result.values())[0] if result else []
                
        except Exception as e:
            logger.error(f"Batch LLM analysis failed: {e}")
            # Return safe defaults
            return [
                {
                    'retention_level': 'short_term',
                    'confidence': 0.5,
                    'reasoning': f'Batch analysis failed: {str(e)}',
                    'categories': [],
                    'importance_boost': 0
                }
                for _ in statements
            ]
    
    def get_usage_stats(self) -> Dict:
        """Get LLM usage statistics."""
        avg_tokens = self.total_tokens / max(self.total_calls, 1)
        
        # Approximate cost (as of Dec 2024)
        # gpt-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        # Rough estimate: ~$0.0004 per call
        estimated_cost = self.total_calls * 0.0004
        
        return {
            'total_calls': self.total_calls,
            'total_tokens': self.total_tokens,
            'avg_tokens_per_call': round(avg_tokens, 1),
            'estimated_cost_usd': round(estimated_cost, 4),
            'model': self.model
        }

# Demo
def demo_real_llm():
    """Demonstrate real LLM integration."""
    print("=" * 70)
    print("Real LLM Integration Demo")
    print("=" * 70)
    
    # Initialize analyzer
    analyzer = RealLLMAnalyzer(model="gpt-4o-mini")
    
    # Test statements
    test_statements = [
        "I have a severe peanut allergy and carry an EpiPen",
        "My daughter Emily goes to Lincoln Elementary",
        "The weather is nice today",
        "I was diagnosed with PTSD after the accident",
        "What time is it?",
        "My emergency contact is my brother John at 555-0123"
    ]
    
    print("\nAnalyzing individual statements:")
    print("-" * 70)
    
    for i, statement in enumerate(test_statements, 1):
        print(f"\n{i}. \"{statement}\"")
        
        result = analyzer.analyze_statement(statement)
        
        print(f"   Retention: {result['retention_level']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Categories: {', '.join(result['categories'])}")
        print(f"   Reasoning: {result['reasoning']}")
        print(f"   Importance Boost: +{result['importance_boost']}")
    
    # Show usage stats
    print("\n" + "=" * 70)
    print("LLM Usage Statistics:")
    print("-" * 70)
    
    stats = analyzer.get_usage_stats()
    print(f"  Total API calls: {stats['total_calls']}")
    print(f"  Total tokens: {stats['total_tokens']:,}")
    print(f"  Avg tokens/call: {stats['avg_tokens_per_call']}")
    print(f"  Estimated cost: ${stats['estimated_cost_usd']:.4f}")
    print(f"  Model: {stats['model']}")
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo_real_llm()
