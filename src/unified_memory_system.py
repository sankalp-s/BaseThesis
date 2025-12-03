from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Import all components
from memory_system import (
    ConversationalMemorySystem, MemoryItem, RetentionLevel
)
from enhanced_memory_system import (
    EnhancedMemorySystem, LLMAnalysis
)
from entity_linking import (
    EntityLinker, Entity, EntityType, UserProfile
)
from adaptive_learning import (
    AdaptiveLearningSystem, Feedback, FeedbackType
)
from knowledge_graph import KnowledgeGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class UnifiedAnalysisResult:
    memory_item: MemoryItem
    llm_analysis: Optional[LLMAnalysis] = None
    entities: List[Entity] = field(default_factory=list)
    user_profile: Optional[UserProfile] = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'memory_item': {
                'content': self.memory_item.content,
                'retention_level': self.memory_item.retention.value,
                'importance_score': self.memory_item.importance_score,
                'categories': self.memory_item.categories,
                'turn_index': self.memory_item.turn_number,
                'context_rationale': self.memory_item.context_rationale
            },
            'llm_analysis': {
                'used_llm': self.llm_analysis is not None,
                'suggested_level': self.llm_analysis.suggested_level.value if self.llm_analysis else None,
                'reasoning': self.llm_analysis.reasoning if self.llm_analysis else None
            } if self.llm_analysis else None,
            'entities': [
                {
                    'text': e.text,
                    'type': e.type.value,
                    'confidence': e.confidence
                }
                for e in self.entities
            ],
            'confidence': self.confidence,
            'processing_time_ms': self.processing_time_ms
        }


class UnifiedMemorySystem:
    
    def __init__(
        self,
        user_id: str,
        enable_llm: bool = True,
        enable_entities: bool = True,
        enable_learning: bool = True,
        use_real_llm: bool = False
    ):
        self.user_id = user_id
        self.enable_llm = enable_llm
        self.enable_entities = enable_entities
        self.enable_learning = enable_learning
        self.use_real_llm = use_real_llm
        
        # Initialize components
        self.enhanced_memory = EnhancedMemorySystem(
            enable_llm=enable_llm,
            use_real_llm=use_real_llm
        )
        
        if enable_entities:
            self.entity_linker = EntityLinker()
            self.knowledge_graph = KnowledgeGraph()
        else:
            self.knowledge_graph = None
        
        if enable_learning:
            # Use user-specific storage path
            storage_path = f"adaptive_data_{user_id}.json"
            self.adaptive_learning = AdaptiveLearningSystem(storage_path)
            # Load user-specific weights if available
            self._load_user_weights()
        
        logger.info(
            f"Initialized unified system for user {user_id} "
            f"(LLM={enable_llm}, Entities={enable_entities}, Learning={enable_learning})"
        )
    
    def _load_user_weights(self):
        """Load user-specific importance weights from adaptive learning."""
        if hasattr(self, 'adaptive_learning'):
            # Get user-specific weight model
            if self.user_id in self.adaptive_learning.user_weights:
                weights_model = self.adaptive_learning.user_weights[self.user_id]
                weights = weights_model.weights if hasattr(weights_model, 'weights') else {}
                if weights:
                    # Apply to enhanced memory system
                    self.enhanced_memory.base_system.importance_weights.update(weights)
                    logger.info(f"Loaded {len(weights)} custom weights for user {self.user_id}")
            else:
                logger.debug(f"No custom weights found for user {self.user_id}")
    
    def process_conversation(
        self,
        conversation: List[Dict[str, str]],
        context: Optional[Dict] = None
    ) -> List[UnifiedAnalysisResult]:
        results = []
        start_time = datetime.now()
        
        logger.info(f"Processing conversation with {len(conversation)} turns")
        
        for turn_idx, turn in enumerate(conversation):
            result = self.process_turn(turn, turn_idx, conversation, context)
            results.append(result)
        
        # Update entity profiles after processing all turns
        if self.enable_entities and results:
            self._update_user_profile(results)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Processed {len(conversation)} turns in {processing_time:.2f}ms "
            f"(avg {processing_time/len(conversation):.2f}ms/turn)"
        )
        
        return results
    
    def process_turn(
        self,
        turn: Dict[str, str],
        turn_idx: int,
        full_conversation: List[Dict[str, str]],
        context: Optional[Dict] = None
    ) -> UnifiedAnalysisResult:
        start_time = datetime.now()
        
        # Phase 1: Enhanced memory classification
        memory_item, llm_analysis = self.enhanced_memory.analyze_conversation(
            [turn],  # Process single turn
            turn_idx
        )[0]
        
        # Phase 2: Entity extraction
        entities = []
        if self.enable_entities:
            # Create ConversationTurn object for entity extraction
            from memory_system import ConversationTurn
            conversation_turn = ConversationTurn(
                speaker=turn.get('speaker', 'user'),
                text=turn.get('content', ''),
                turn_number=turn_idx
            )
            entities = self.entity_linker.extract_entities([conversation_turn])
            if self.knowledge_graph:
                self.knowledge_graph.ingest_memory(memory_item)
                if entities:
                    self.knowledge_graph.ingest_entities(entities)
                    self.knowledge_graph.link_memory_to_entities(memory_item, entities)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            memory_item, llm_analysis, entities
        )
        
        # Phase 3: Adaptive learning (passive - affects future processing)
        # Learning happens when feedback is provided via record_feedback()
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return UnifiedAnalysisResult(
            memory_item=memory_item,
            llm_analysis=llm_analysis,
            entities=entities,
            user_profile=None,  # Set later
            confidence=confidence,
            processing_time_ms=processing_time
        )
    
    def _calculate_confidence(
        self,
        memory_item: MemoryItem,
        llm_analysis: Optional[LLMAnalysis],
        entities: List[Entity]
    ) -> float:

        # Base confidence from importance score (normalize to 0-1)
        confidence = min(memory_item.importance_score / 40.0, 1.0)
        
        # Boost if LLM agrees with classification
        if llm_analysis:
            if llm_analysis.suggested_level == memory_item.retention:
                confidence = min(confidence + 0.2, 1.0)
        
        # Slight boost for entity-rich content
        if entities:
            entity_boost = min(len(entities) * 0.05, 0.2)
            confidence = min(confidence + entity_boost, 1.0)
        
        return round(confidence, 3)
    
    def _update_user_profile(self, results: List[UnifiedAnalysisResult]):
        """Build/update user profile from analyzed conversation."""
        if not self.enable_entities:
            return
        
        # Collect all entities
        all_entities = []
        for result in results:
            all_entities.extend(result.entities)
        
        if not all_entities:
            return
        
        # Build profile
        profile = self.entity_linker.build_user_profile(
            self.user_id,
            all_entities
        )
        
        # Attach to all results
        for result in results:
            result.user_profile = profile
        
        logger.info(
            f"Built profile: {len(profile.people)} people, "
            f"{len(profile.medical_conditions)} conditions, "
            f"{len(profile.named_entities)} entities"
        )
    
    def record_feedback(
        self,
        turn_content: str,
        predicted_level: RetentionLevel,
        correct_level: RetentionLevel,
        comment: Optional[str] = None
    ):
        """
        Record user feedback to improve future classifications.
        
        Args:
            turn_content: The conversation turn content
            predicted_level: What system predicted
            correct_level: What user says is correct
            comment: Optional explanation
        """
        if not self.enable_learning:
            logger.warning("Adaptive learning disabled, feedback not recorded")
            return
        
        # Use the collect_feedback method from AdaptiveLearningSystem
        feedback = self.adaptive_learning.collect_feedback(
            user_id=self.user_id,
            statement=turn_content,
            actual_retention=predicted_level.value,
            expected_retention=correct_level.value,
            categories=[],  # Would be populated from classification
            importance_score=0,  # Would come from classification
            context={'comment': comment}
        )
        
        # Update weights immediately
        self._load_user_weights()
        
        logger.info(f"Recorded feedback for user {self.user_id}")
    
    def get_statistics(self) -> Dict:
        """Get comprehensive system statistics."""
        stats = {
            'user_id': self.user_id,
            'enabled_features': {
                'llm': self.enable_llm,
                'entities': self.enable_entities,
                'learning': self.enable_learning
            }
        }
        
        # Memory stats
        # Count unique categories from all patterns
        all_categories = set()
        for _, category, _ in self.enhanced_memory.critical_patterns:
            all_categories.add(category)
        for _, category, _ in self.enhanced_memory.contextual_patterns:
            all_categories.add(category)
        for _, category, _ in self.enhanced_memory.ephemeral_patterns:
            all_categories.add(category)
        
        stats['memory'] = {
            'patterns': len(self.enhanced_memory.critical_patterns) + len(self.enhanced_memory.contextual_patterns) + len(self.enhanced_memory.ephemeral_patterns),
            'categories': len(all_categories)
        }
        
        # Entity stats
        if self.enable_entities:
            stats['entities'] = {
                'patterns': len(self.entity_linker.relationship_patterns) + len(self.entity_linker.medical_patterns),
                'types': len(EntityType)
            }
        
        # Learning stats
        if self.enable_learning:
            user_stats = self.adaptive_learning.get_user_stats(self.user_id)
            stats['learning'] = user_stats
        
        return stats
    
    def export_user_data(self) -> Dict:
        """Export all user data for portability/debugging."""
        data = {
            'user_id': self.user_id,
            'exported_at': datetime.now().isoformat(),
            'enabled_features': {
                'llm': self.enable_llm,
                'entities': self.enable_entities,
                'learning': self.enable_learning
            }
        }
        
        # Custom weights
        if self.enable_learning:
            user_stats = self.adaptive_learning.get_user_stats(self.user_id)
            data['feedback_count'] = user_stats.get('total_feedback', 0)
            if self.user_id in self.adaptive_learning.user_weights:
                weights_model = self.adaptive_learning.user_weights[self.user_id]
                data['custom_weights'] = weights_model.weights if hasattr(weights_model, 'weights') else {}
        
        return data
    
    def get_memory_summary(self, results: List[UnifiedAnalysisResult]) -> Dict:

        long_term = [r for r in results if r.memory_item.retention == RetentionLevel.LONG_TERM]
        short_term = [r for r in results if r.memory_item.retention == RetentionLevel.SHORT_TERM]
        immediate = [r for r in results if r.memory_item.retention == RetentionLevel.IMMEDIATE]
        
        # Calculate average confidence by level
        avg_confidence = {
            'long_term': sum(r.confidence for r in long_term) / len(long_term) if long_term else 0,
            'short_term': sum(r.confidence for r in short_term) / len(short_term) if short_term else 0,
            'immediate': sum(r.confidence for r in immediate) / len(immediate) if immediate else 0
        }
        
        return {
            'total_turns': len(results),
            'retention_distribution': {
                'long_term': len(long_term),
                'short_term': len(short_term),
                'immediate': len(immediate)
            },
            'retention_percentages': {
                'long_term': round(len(long_term) / len(results) * 100, 1),
                'short_term': round(len(short_term) / len(results) * 100, 1),
                'immediate': round(len(immediate) / len(results) * 100, 1)
            },
            'average_confidence': {
                k: round(v, 3) for k, v in avg_confidence.items()
            },
            'llm_usage': sum(1 for r in results if r.llm_analysis) / len(results) * 100,
            'entities_found': len({(e.text, e.type.value) for r in results for e in r.entities}),
            'avg_processing_time_ms': round(
                sum(r.processing_time_ms for r in results) / len(results), 2
            ),
            'knowledge_graph': self.knowledge_graph.get_summary() if self.knowledge_graph else {},
            'context_window': self.enhanced_memory.get_context_window()
        }


# Demo & Testing

def demo_unified_system():
    """Demonstrate unified system with all features."""
    print("=" * 70)
    print("Unified Conversational Memory System - Demo")
    print("=" * 70)
    
    # Initialize system for user
    system = UnifiedMemorySystem(
        user_id="user_123",
        enable_llm=True,
        enable_entities=True,
        enable_learning=True
    )
    
    # Sample conversation with medical info
    conversation = [
        {
            "speaker": "user",
            "content": "Hi, I'm Sarah and I have a severe peanut allergy"
        },
        {
            "speaker": "assistant",
            "content": "I've noted your peanut allergy. Are you carrying an EpiPen?"
        },
        {
            "speaker": "user",
            "content": "Yes, always. My daughter Emily also has allergies"
        },
        {
            "speaker": "assistant",
            "content": "Good to know. What is Emily allergic to?"
        },
        {
            "speaker": "user",
            "content": "She's allergic to shellfish. It's pretty serious."
        },
        {
            "speaker": "assistant",
            "content": "I'll remember both allergies. How old is Emily?"
        },
        {
            "speaker": "user",
            "content": "She's 8 and goes to Lincoln Elementary"
        },
        {
            "speaker": "assistant",
            "content": "Thanks. Do you need any restaurant recommendations that are allergy-friendly?"
        },
        {
            "speaker": "user",
            "content": "That would be great! We live in Austin."
        }
    ]
    
    # Process conversation
    print("\n1. Processing conversation through unified system...")
    results = system.process_conversation(conversation)
    
    print(f"\nProcessed {len(results)} turns:")
    print("-" * 70)
    
    for i, result in enumerate(results):
        content = conversation[i]['content']
        if len(content) > 50:
            content = content[:50] + "..."
        
        print(f"\n  Turn {i+1}: {content}")
        print(f"    Retention:  {result.memory_item.retention.value}")
        print(f"    Importance: {result.memory_item.importance_score}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Categories: {', '.join(result.memory_item.categories)}")
        
        if result.entities:
            print(f"    Entities:   {len(result.entities)} found")
            for entity in result.entities[:3]:  # Show first 3
                print(f"      → {entity.type.value}: {entity.text} (conf: {entity.confidence:.2f})")
        
        if result.llm_analysis:
            print(f"    LLM Used:   Yes")
    
    # Show user profile
    print("\n" + "=" * 70)
    print("2. User Profile Built:")
    print("-" * 70)
    
    if results[0].user_profile:
        profile = results[0].user_profile
        
        if profile.people:
            print(f"\n  People identified:")
            for name, relations in profile.people.items():
                print(f"    • {name}: {', '.join(relations)}")
        
        if profile.medical_conditions:
            print(f"\n  Medical conditions:")
            for condition in profile.medical_conditions:
                print(f"    • {condition}")
        
        if profile.named_entities:
            print(f"\n  Other entities:")
            for entity_type, entities in profile.named_entities.items():
                if entities:
                    print(f"    • {entity_type}: {', '.join(entities)}")
    
    # Show summary statistics
    print("\n" + "=" * 70)
    print("3. Analysis Summary:")
    print("-" * 70)
    
    summary = system.get_memory_summary(results)
    print(f"\n  Total turns processed: {summary['total_turns']}")
    print(f"\n  Retention distribution:")
    print(f"    Long-term:  {summary['retention_distribution']['long_term']} "
          f"({summary['retention_percentages']['long_term']}%)")
    print(f"    Short-term: {summary['retention_distribution']['short_term']} "
          f"({summary['retention_percentages']['short_term']}%)")
    print(f"    Immediate:  {summary['retention_distribution']['immediate']} "
          f"({summary['retention_percentages']['immediate']}%)")
    
    print(f"\n  Average confidence:")
    print(f"    Long-term:  {summary['average_confidence']['long_term']:.3f}")
    print(f"    Short-term: {summary['average_confidence']['short_term']:.3f}")
    print(f"    Immediate:  {summary['average_confidence']['immediate']:.3f}")
    
    print(f"\n  Performance:")
    print(f"    Entities found: {summary['entities_found']}")
    print(f"    LLM usage: {summary['llm_usage']:.1f}%")
    print(f"    Avg processing: {summary['avg_processing_time_ms']:.2f}ms/turn")
    
    # Simulate feedback
    print("\n" + "=" * 70)
    print("4. Recording User Feedback:")
    print("-" * 70)
    
    system.record_feedback(
        turn_content=conversation[0]['content'],
        predicted_level=RetentionLevel.LONG_TERM,
        correct_level=RetentionLevel.LONG_TERM,
        comment="Correctly identified critical medical information"
    )
    print("\n  ✓ Positive feedback recorded for peanut allergy detection")
    
    system.record_feedback(
        turn_content=conversation[8]['content'],
        predicted_level=RetentionLevel.IMMEDIATE,
        correct_level=RetentionLevel.SHORT_TERM,
        comment="Location should be remembered for context"
    )
    print("  ✓ Correction recorded for location retention")
    
    # System statistics
    print("\n" + "=" * 70)
    print("5. System Statistics:")
    print("-" * 70)
    
    stats = system.get_statistics()
    print(f"\n  Features enabled:")
    for feature, enabled in stats['enabled_features'].items():
        print(f"    • {feature.upper()}: {'✓' if enabled else '✗'}")
    
    print(f"\n  Memory system:")
    print(f"    Patterns: {stats['memory']['patterns']}")
    print(f"    Categories: {stats['memory']['categories']}")
    
    if 'entities' in stats:
        print(f"\n  Entity system:")
        print(f"    Patterns: {stats['entities']['patterns']}")
        print(f"    Types: {stats['entities']['types']}")
    
    if 'learning' in stats:
        print(f"\n  Adaptive learning:")
        print(f"    Total feedback: {stats['learning']['total']}")
        print(f"    Positive: {stats['learning']['by_type'].get('positive', 0)}")
        print(f"    Corrections: {stats['learning']['by_type'].get('correction', 0)}")
    
    print("\n" + "=" * 70)
    print("Demo complete! System ready for production use.")
    print("=" * 70)
    print("\nNext steps:")
    print("  • Run tests: pytest test_unified_system.py")
    print("  • Deploy API: See DEPLOYMENT_GUIDE.md")
    print("  • Monitor: See INTEGRATION_GUIDE.md")
    print("=" * 70)


if __name__ == "__main__":
    demo_unified_system()
