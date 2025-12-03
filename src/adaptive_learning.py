import json
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum
import random


class FeedbackType(Enum):
    """Types of user feedback"""
    FORGOT_IMPORTANT = "forgot_important"  # System forgot something important
    REMEMBERED_TRIVIAL = "remembered_trivial"  # System remembered something unimportant
    CORRECT = "correct"  # System got it right
    WRONG_CATEGORY = "wrong_category"  # Right retention, wrong category


@dataclass
class Feedback:
    """User feedback on a memory decision"""
    feedback_id: str
    user_id: str
    statement: str
    actual_retention: str  # What system classified
    expected_retention: str  # What user expected
    feedback_type: FeedbackType
    categories: List[str]
    importance_score: float
    timestamp: float
    context: Dict = field(default_factory=dict)


@dataclass
class UserWeights:
    """User-specific importance weights"""
    user_id: str
    pattern_weights: Dict[str, float] = field(default_factory=dict)
    category_multipliers: Dict[str, float] = field(default_factory=dict)
    threshold_adjustments: Dict[str, float] = field(default_factory=dict)
    feedback_count: int = 0
    last_updated: float = 0.0
    
    def adjust_weight(self, pattern: str, adjustment: float):
        """Adjust weight for a pattern"""
        if pattern not in self.pattern_weights:
            self.pattern_weights[pattern] = 0.0
        self.pattern_weights[pattern] += adjustment
        self.last_updated = time.time()
    
    def get_weight(self, pattern: str, default: float = 0.0) -> float:
        """Get weight for a pattern"""
        return self.pattern_weights.get(pattern, default)


class AdaptiveLearningSystem:
    """
    Learn from user feedback and adapt classification over time.
    """
    
    def __init__(self, storage_path: str = "adaptive_data.json"):
        self.storage_path = storage_path
        self.user_weights = {}
        self.feedback_history = []
        self.pattern_effectiveness = defaultdict(lambda: {'correct': 0, 'incorrect': 0})
        self.ab_tests = {}
        
        # Load existing data
        self._load_data()
    
    def collect_feedback(self, user_id: str, statement: str, 
                        actual_retention: str, expected_retention: str,
                        categories: List[str], importance_score: float,
                        context: Dict = None) -> Feedback:
        """Collect feedback from user"""
        
        # Determine feedback type
        if actual_retention == expected_retention:
            feedback_type = FeedbackType.CORRECT
        elif expected_retention == "long_term" and actual_retention != "long_term":
            feedback_type = FeedbackType.FORGOT_IMPORTANT
        elif expected_retention == "immediate" and actual_retention != "immediate":
            feedback_type = FeedbackType.REMEMBERED_TRIVIAL
        else:
            feedback_type = FeedbackType.WRONG_CATEGORY
        
        feedback = Feedback(
            feedback_id=f"{user_id}_{int(time.time())}_{random.randint(1000, 9999)}",
            user_id=user_id,
            statement=statement,
            actual_retention=actual_retention,
            expected_retention=expected_retention,
            feedback_type=feedback_type,
            categories=categories,
            importance_score=importance_score,
            timestamp=time.time(),
            context=context or {}
        )
        
        self.feedback_history.append(feedback)
        self._process_feedback(feedback)
        self._save_data()
        
        return feedback
    
    def _process_feedback(self, feedback: Feedback):
        """Process feedback and update weights"""
        
        user_id = feedback.user_id
        
        # Initialize user weights if needed
        if user_id not in self.user_weights:
            self.user_weights[user_id] = UserWeights(user_id=user_id)
        
        user_weights = self.user_weights[user_id]
        user_weights.feedback_count += 1
        
        # Calculate adjustment based on feedback type
        if feedback.feedback_type == FeedbackType.FORGOT_IMPORTANT:
            # User said we forgot something important -> increase weights for these patterns
            adjustment = 2.0
            for category in feedback.categories:
                user_weights.adjust_weight(f"category_{category}", adjustment)
            
            # If score was close to threshold, adjust threshold
            if 10 <= feedback.importance_score <= 14:
                user_weights.threshold_adjustments['long_term'] = \
                    user_weights.threshold_adjustments.get('long_term', 0) - 1.0
        
        elif feedback.feedback_type == FeedbackType.REMEMBERED_TRIVIAL:
            # User said we remembered something unimportant -> decrease weights
            adjustment = -1.0
            for category in feedback.categories:
                user_weights.adjust_weight(f"category_{category}", adjustment)
            
            # Adjust threshold
            if 4 <= feedback.importance_score <= 8:
                user_weights.threshold_adjustments['short_term'] = \
                    user_weights.threshold_adjustments.get('short_term', 0) + 1.0
        
        elif feedback.feedback_type == FeedbackType.CORRECT:
            # Positive reinforcement
            adjustment = 0.5
            for category in feedback.categories:
                user_weights.adjust_weight(f"category_{category}", adjustment)
    
    def get_adjusted_score(self, user_id: str, base_score: float, 
                          categories: List[str]) -> float:
        """Get importance score adjusted for user-specific weights"""
        
        if user_id not in self.user_weights:
            return base_score
        
        user_weights = self.user_weights[user_id]
        adjusted_score = base_score
        
        # Apply category multipliers
        for category in categories:
            weight = user_weights.get_weight(f"category_{category}", 0.0)
            adjusted_score += weight
        
        return adjusted_score
    
    def get_adjusted_thresholds(self, user_id: str) -> Dict[str, float]:
        """Get thresholds adjusted for user preferences"""
        
        default_thresholds = {
            'long_term': 12.0,
            'short_term': 4.0
        }
        
        if user_id not in self.user_weights:
            return default_thresholds
        
        user_weights = self.user_weights[user_id]
        adjusted = {}
        
        for key, default in default_thresholds.items():
            adjustment = user_weights.threshold_adjustments.get(key, 0.0)
            adjusted[key] = max(0, default + adjustment)  # Don't go negative
        
        return adjusted
    
    def create_ab_test(self, test_name: str, variants: Dict[str, Dict]) -> str:
        """Create A/B test for comparing approaches"""
        
        test_id = f"test_{int(time.time())}_{test_name}"
        
        self.ab_tests[test_id] = {
            'name': test_name,
            'variants': variants,
            'results': defaultdict(lambda: {'users': set(), 'feedback': []}),
            'created_at': time.time(),
            'active': True
        }
        
        return test_id
    
    def assign_variant(self, test_id: str, user_id: str) -> Optional[str]:
        """Assign user to A/B test variant"""
        
        if test_id not in self.ab_tests:
            return None
        
        test = self.ab_tests[test_id]
        if not test['active']:
            return None
        
        # Simple random assignment
        variant_name = random.choice(list(test['variants'].keys()))
        test['results'][variant_name]['users'].add(user_id)
        
        return variant_name
    
    def record_ab_result(self, test_id: str, variant: str, feedback: Feedback):
        """Record result for A/B test"""
        
        if test_id in self.ab_tests:
            self.ab_tests[test_id]['results'][variant]['feedback'].append(feedback)
    
    def analyze_ab_test(self, test_id: str) -> Dict:
        """Analyze A/B test results"""
        
        if test_id not in self.ab_tests:
            return {}
        
        test = self.ab_tests[test_id]
        analysis = {
            'test_name': test['name'],
            'variants': {}
        }
        
        for variant_name, data in test['results'].items():
            feedback_list = data['feedback']
            users = data['users']
            
            if not feedback_list:
                continue
            
            correct = sum(1 for f in feedback_list if f.feedback_type == FeedbackType.CORRECT)
            total = len(feedback_list)
            
            analysis['variants'][variant_name] = {
                'users': len(users),
                'feedback_count': total,
                'accuracy': correct / total if total > 0 else 0,
                'correct': correct,
                'forgot_important': sum(1 for f in feedback_list 
                                       if f.feedback_type == FeedbackType.FORGOT_IMPORTANT),
                'remembered_trivial': sum(1 for f in feedback_list 
                                         if f.feedback_type == FeedbackType.REMEMBERED_TRIVIAL)
            }
        
        # Determine winner
        best_variant = max(analysis['variants'].items(), 
                          key=lambda x: x[1]['accuracy']) if analysis['variants'] else None
        
        if best_variant:
            analysis['winner'] = {
                'variant': best_variant[0],
                'accuracy': best_variant[1]['accuracy']
            }
        
        return analysis
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a user"""
        
        if user_id not in self.user_weights:
            return {'feedback_count': 0, 'weights_learned': 0}
        
        weights = self.user_weights[user_id]
        
        # Get feedback for this user
        user_feedback = [f for f in self.feedback_history if f.user_id == user_id]
        
        feedback_by_type = defaultdict(int)
        for f in user_feedback:
            feedback_by_type[f.feedback_type.value] += 1
        
        return {
            'user_id': user_id,
            'feedback_count': weights.feedback_count,
            'weights_learned': len(weights.pattern_weights),
            'threshold_adjustments': weights.threshold_adjustments,
            'feedback_breakdown': dict(feedback_by_type),
            'last_updated': weights.last_updated,
            'top_adjusted_patterns': sorted(
                weights.pattern_weights.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:5]
        }
    
    def _save_data(self):
        """Save learning data to disk"""
        
        data = {
            'user_weights': {
                uid: asdict(w) for uid, w in self.user_weights.items()
            },
            'feedback_count': len(self.feedback_history),
            'ab_tests': self.ab_tests
        }
        
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save data: {e}")
    
    def _load_data(self):
        """Load learning data from disk"""
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Restore user weights
            for uid, w_data in data.get('user_weights', {}).items():
                self.user_weights[uid] = UserWeights(**w_data)
            
            # Restore AB tests
            self.ab_tests = data.get('ab_tests', {})
            
        except FileNotFoundError:
            # No existing data
            pass
        except Exception as e:
            print(f"Failed to load data: {e}")


def demo_adaptive_learning():
    """Demonstrate adaptive learning"""
    
    print("=" * 80)
    print("ADAPTIVE LEARNING SYSTEM DEMO")
    print("=" * 80)
    print()
    
    # Initialize system
    system = AdaptiveLearningSystem("demo_adaptive.json")
    
    user_id = "user_001"
    
    # Simulate feedback
    print("Simulating user feedback...\n")
    
    # Example 1: User says we forgot something important
    feedback1 = system.collect_feedback(
        user_id=user_id,
        statement="I have a severe peanut allergy",
        actual_retention="short_term",
        expected_retention="long_term",
        categories=["medical", "allergy"],
        importance_score=11.0
    )
    print(f"Feedback 1: {feedback1.feedback_type.value}")
    print(f"  Statement: {feedback1.statement}")
    print(f"  System said: {feedback1.actual_retention}, User wanted: {feedback1.expected_retention}")
    
    # Example 2: User says we remembered something trivial
    feedback2 = system.collect_feedback(
        user_id=user_id,
        statement="My favorite color is blue",
        actual_retention="short_term",
        expected_retention="immediate",
        categories=["preference"],
        importance_score=6.0
    )
    print(f"\nFeedback 2: {feedback2.feedback_type.value}")
    print(f"  Statement: {feedback2.statement}")
    
    # Example 3: System got it right
    feedback3 = system.collect_feedback(
        user_id=user_id,
        statement="I have PTSD from a car accident",
        actual_retention="long_term",
        expected_retention="long_term",
        categories=["mental_health", "medical"],
        importance_score=25.0
    )
    print(f"\nFeedback 3: {feedback3.feedback_type.value}")
    print(f"  Statement: {feedback3.statement}")
    
    # Show learned weights
    print("\n" + "=" * 80)
    print("LEARNED WEIGHTS")
    print("=" * 80)
    
    stats = system.get_user_stats(user_id)
    print(f"\nUser: {stats['user_id']}")
    print(f"Feedback collected: {stats['feedback_count']}")
    print(f"Patterns learned: {stats['weights_learned']}")
    
    print("\nTop adjusted patterns:")
    for pattern, weight in stats['top_adjusted_patterns']:
        direction = "↑" if weight > 0 else "↓"
        print(f"  {direction} {pattern}: {weight:+.1f}")
    
    print("\nThreshold adjustments:")
    for threshold, adj in stats['threshold_adjustments'].items():
        print(f"  {threshold}: {adj:+.1f}")
    
    # Show how score would be adjusted
    print("\n" + "=" * 80)
    print("SCORE ADJUSTMENTS")
    print("=" * 80)
    
    test_cases = [
        ("I have an allergy to shellfish", 15.0, ["medical", "allergy"]),
        ("I like pizza", 6.0, ["preference"]),
        ("I have anxiety about flying", 18.0, ["mental_health"]),
    ]
    
    print("\nHow learned weights affect classification:\n")
    for statement, base_score, categories in test_cases:
        adjusted = system.get_adjusted_score(user_id, base_score, categories)
        print(f"Statement: \"{statement}\"")
        print(f"  Base score: {base_score:.1f}")
        print(f"  Adjusted score: {adjusted:.1f} ({adjusted - base_score:+.1f})")
        print(f"  Categories: {categories}")
        print()
    
    # Demo A/B testing
    print("=" * 80)
    print("A/B TESTING")
    print("=" * 80)
    
    test_id = system.create_ab_test(
        "threshold_test",
        variants={
            'current': {'long_term_threshold': 12.0},
            'stricter': {'long_term_threshold': 15.0},
            'lenient': {'long_term_threshold': 10.0}
        }
    )
    
    print(f"\nCreated A/B test: {test_id}")
    print("Variants: current (12.0), stricter (15.0), lenient (10.0)")
    
    # Simulate some test results
    for i in range(10):
        test_user = f"test_user_{i}"
        variant = system.assign_variant(test_id, test_user)
        
        # Simulate feedback
        feedback = Feedback(
            feedback_id=f"test_{i}",
            user_id=test_user,
            statement="test",
            actual_retention="long_term",
            expected_retention="long_term" if random.random() > 0.3 else "short_term",
            feedback_type=FeedbackType.CORRECT if random.random() > 0.3 else FeedbackType.WRONG_CATEGORY,
            categories=["test"],
            importance_score=12.0,
            timestamp=time.time()
        )
        system.record_ab_result(test_id, variant, feedback)
    
    # Analyze
    analysis = system.analyze_ab_test(test_id)
    print("\nTest results:")
    for variant, results in analysis['variants'].items():
        print(f"\n  Variant: {variant}")
        print(f"    Users: {results['users']}")
        print(f"    Feedback: {results['feedback_count']}")
        print(f"    Accuracy: {results['accuracy']:.1%}")
    
    if 'winner' in analysis:
        print(f"\n  Winner: {analysis['winner']['variant']} "
              f"(accuracy: {analysis['winner']['accuracy']:.1%})")
    
    print("\n" + "=" * 80)
    print("Demo complete!")


if __name__ == "__main__":
    demo_adaptive_learning()
