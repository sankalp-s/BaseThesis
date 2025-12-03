import re
import json
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class EntityType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    MEDICAL_CONDITION = "medical_condition"
    EVENT = "event"
    OBJECT = "object"


@dataclass
class Entity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str
    mentions: List[Tuple[int, str]] = field(default_factory=list)  # (turn_num, mention_text)
    attributes: Dict[str, any] = field(default_factory=dict)
    importance_score: float = 0.0
    first_mentioned: int = 0
    last_mentioned: int = 0
    
    @property
    def text(self) -> str:
        return self.canonical_name
    
    @property
    def type(self) -> EntityType:

        return self.entity_type
    
    @property
    def confidence(self) -> float:
        # Normalize importance score to 0-1 range
        return min(self.importance_score / 25.0, 1.0)
    
    @property
    def context(self) -> str:
        if self.mentions:
            return self.mentions[-1][1]  # Return last mention text
        return ""
    
    def add_mention(self, turn_num: int, mention_text: str):
        self.mentions.append((turn_num, mention_text))
        if not self.first_mentioned:
            self.first_mentioned = turn_num
        self.last_mentioned = turn_num
    
    def add_attribute(self, key: str, value: any, turn_num: int):
        if key not in self.attributes:
            self.attributes[key] = {
                'value': value,
                'first_mentioned': turn_num,
                'last_updated': turn_num
            }
        else:
            self.attributes[key]['value'] = value
            self.attributes[key]['last_updated'] = turn_num


@dataclass
class UserProfile:
    user_id: str
    entities: Dict[str, Entity] = field(default_factory=dict)
    conversation_count: int = 0
    total_turns: int = 0
    important_facts: List[Dict] = field(default_factory=list)
    preferences: Dict[str, any] = field(default_factory=dict)
    created_at: str = ""
    last_updated: str = ""
    
    @property
    def people(self) -> Dict[str, List[str]]:
        people_dict = {}
        for entity in self.entities.values():
            if entity.entity_type == EntityType.PERSON:
                name = entity.canonical_name
                relations = []
                if 'relationship' in entity.attributes:
                    relations.append(entity.attributes['relationship']['value'])
                if 'age' in entity.attributes:
                    relations.append(f"age {entity.attributes['age']['value']}")
                people_dict[name] = relations if relations else ["mentioned"]
        return people_dict
    
    @property
    def medical_conditions(self) -> List[str]:
        conditions = []
        for entity in self.entities.values():
            if entity.entity_type == EntityType.MEDICAL_CONDITION:
                conditions.append(entity.canonical_name)
        return conditions
    
    @property
    def named_entities(self) -> Dict[str, Set[str]]:
        named = defaultdict(set)
        for entity in self.entities.values():
            if entity.entity_type in [EntityType.LOCATION, EntityType.ORGANIZATION, EntityType.OBJECT]:
                named[entity.entity_type.value].add(entity.canonical_name)
        return dict(named)
    
    def add_entity(self, entity: Entity):
        self.entities[entity.entity_id] = entity
    
    def get_entity_by_mention(self, mention: str) -> Optional[Entity]:
        mention_lower = mention.lower()
        for entity in self.entities.values():
            if any(mention_lower in m[1].lower() for m in entity.mentions):
                return entity
        return None
    
    def add_important_fact(self, fact: str, category: str, turn_num: int, importance: float):
        self.important_facts.append({
            'fact': fact,
            'category': category,
            'turn': turn_num,
            'importance': importance,
            'conversation': self.conversation_count
        })


class EntityLinker:
    def __init__(self):
        self.entities = {}
        self.entity_counter = 0
        
        # Relationship patterns
        self.relationship_patterns = [
            (r'\bmy (wife|husband|partner|spouse)\b', 'spouse'),
            (r'\bmy (son|daughter|child|kid)\b', 'child'),
            (r'\bmy (mother|mom|father|dad|parent)\b', 'parent'),
            (r'\bmy (brother|sister|sibling)\b', 'sibling'),
            (r'\bmy (friend|colleague|coworker|boss|manager)\b', 'other'),
        ]
        
        # Medical condition patterns (order matters - specific before general)
        self.medical_patterns = [
            # Specific allergies first
            (r'\b(severe\s+)?peanut\s+allerg(?:y|ies|ic)\b', 'peanut allergy', 9.0),
            (r'\b(severe\s+)?shellfish\s+allerg(?:y|ies|ic)\b', 'shellfish allergy', 9.0),
            (r'\b(severe\s+)?nut\s+allerg(?:y|ies|ic)\b', 'nut allergy', 9.0),
            # General allergy (fallback)
            (r'\b(allerg(?:y|ies|ic))\b', 'allergy', 8.0),
            # Intolerances
            (r'\b(lactose\s+intoleran(?:t|ce))\b', 'lactose intolerance', 8.0),
            (r'\b(gluten\s+intoleran(?:t|ce))\b', 'gluten intolerance', 8.0),
            # Dietary restrictions
            (r'\b(vegetarian)\b', 'vegetarian', 7.0),
            (r'\b(vegan)\b', 'vegan', 7.0),
            # Mental health
            (r'\b(PTSD|anxiety|depression|panic attack)\b', 'mental health condition', 9.0),
            # Chronic conditions
            (r'\b(diabetes|asthma|epilepsy|cancer)\b', 'chronic condition', 8.0),
            # Medical equipment
            (r'\b(epipen|inhaler)\b', 'medical equipment', 8.0),
        ]
    
    def build_user_profile(self, user_id: str, entities: List[Entity]) -> UserProfile:
        profile = UserProfile(user_id=user_id)
        for entity in entities:
            profile.add_entity(entity)
        return profile
    
    def extract_entities(self, conversation: List) -> List[Entity]:
        from memory_system import ConversationTurn
        
        for turn in conversation:
            if isinstance(turn, ConversationTurn):
                self._extract_from_turn(turn)
        
        return list(self.entities.values())
    
    def _extract_from_turn(self, turn):
        text = turn.text
        turn_num = turn.turn_number
        
        # Extract people
        self._extract_people(text, turn_num)
        
        # Extract medical conditions
        self._extract_medical_conditions(text, turn_num)
        
        # Extract named entities (capitalized words)
        self._extract_named_entities(text, turn_num)
    
    def _extract_people(self, text: str, turn_num: int):
        
        for pattern, relationship in self.relationship_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                mention = match.group(0)
                relation_type = match.group(1)
                
                # Create entity ID based on relationship
                entity_id = f"person_{relationship}_{relation_type}"
                
                if entity_id not in self.entities:
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=EntityType.PERSON,
                        canonical_name=f"User's {relation_type}",
                        importance_score=10.0  # Family is important
                    )
                    entity.add_attribute('relationship', relationship, turn_num)
                    self.entities[entity_id] = entity
                
                self.entities[entity_id].add_mention(turn_num, mention)
                
                # Extract additional attributes
                self._extract_person_attributes(text, entity_id, turn_num)
    
    def _extract_person_attributes(self, text: str, entity_id: str, turn_num: int):
        
        entity = self.entities[entity_id]
        
        # Age extraction
        age_patterns = [
            r'(\d+) years? old',
            r'age (\d+)',
            r'turned (\d+)',
        ]
        for pattern in age_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = int(match.group(1))
                entity.add_attribute('age', age, turn_num)
        
        # Implicit age from context
        if 'kindergarten' in text.lower() or 'starts school' in text.lower():
            if 'age' not in entity.attributes:
                entity.add_attribute('age', 5, turn_num)
                entity.add_attribute('age_inferred', True, turn_num)
        
        # Grade level -> age estimation
        grade_match = re.search(r'(\d+)(?:st|nd|rd|th) grade', text, re.IGNORECASE)
        if grade_match:
            grade = int(grade_match.group(1))
            estimated_age = grade + 5  # Rough estimate
            entity.add_attribute('age', estimated_age, turn_num)
            entity.add_attribute('grade', grade, turn_num)
    
    def _extract_medical_conditions(self, text: str, turn_num: int):
        
        for pattern_tuple in self.medical_patterns:
            pattern, canonical_name, importance = pattern_tuple
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                condition_text = match.group(0)
                
                # Look for context around the condition
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end]
                
                # Use canonical name as entity ID to consolidate mentions
                entity_id = f"medical_{canonical_name.replace(' ', '_').lower()}"
                
                if entity_id not in self.entities:
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=EntityType.MEDICAL_CONDITION,
                        canonical_name=canonical_name,
                        importance_score=importance
                    )
                    self.entities[entity_id] = entity
                
                self.entities[entity_id].add_mention(turn_num, context)
    
    def _extract_named_entities(self, text: str, turn_num: int):
        
        # Comprehensive exclusion list
        exclude_words = {
            'i', 'the', 'a', 'an', 'my', 'your', 'his', 'her', 'their', 'our',
            'hello', 'hi', 'hey', 'bye', 'goodbye', 'thanks', 'thank', 'please',
            'yes', 'no', 'yeah', 'yep', 'nope', 'okay', 'ok', 'sure', 'maybe',
            'um', 'uh', 'hmm', 'oh', 'ah', 'well', 'so', 'like', 'just',
            'how', 'what', 'when', 'where', 'why', 'who', 'which',
            'can', 'could', 'would', 'should', 'will', 'may', 'might',
            'do', 'does', 'did', 'have', 'has', 'had', 'is', 'are', 'was', 'were',
            'this', 'that', 'these', 'those', 'there', 'here',
            'it', 'its', 'he', 'she', 'they', 'we', 'you',
            'any', 'some', 'all', 'each', 'every', 'both', 'few', 'many', 'much',
            'take', 'looking', 'help', 'need', 'want', 'let', 'see', 'good', 'great',
            # Months
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            # Time units
            'years', 'year', 'months', 'month', 'days', 'day',
            # Common expressions
            'god', 'im', 've', 're', 's', 't', 'd', 'm',
        }
        
        # Find capitalized words (potential names/places)
        # Only consider words not at sentence start (to avoid false positives)
        words = text.split()
        proper_nouns = []
        
        for i, word in enumerate(words):
            # Clean word of punctuation for checking
            clean_word = re.sub(r'[^\w]', '', word)
            
            # Skip if empty after cleaning
            if not clean_word:
                continue
                
            # Check if it's capitalized
            if clean_word[0].isupper() and len(clean_word) > 1:
                # Skip if it's a common excluded word
                if clean_word.lower() in exclude_words:
                    continue
                
                # Skip if it's at the very beginning of text (likely sentence start)
                if i == 0:
                    continue
                
                # Check if previous word ends with sentence-ending punctuation
                if i > 0:
                    prev_word = words[i-1]
                    if prev_word.endswith(('.', '!', '?')):
                        continue
                
                proper_nouns.append(clean_word)
        
        for noun in proper_nouns:
            # Skip if it looks like a contraction artifact
            if len(noun) <= 2 and noun.lower() in {'im', 've', 're', 'll', 'd', 'm', 's', 't'}:
                continue
            
            # Check if it's a name or place
            entity_id = f"named_{noun.lower()}"
            
            if entity_id not in self.entities:
                # Guess entity type based on context - only keep if has clear context
                entity_type = None
                
                if re.search(rf'\b{noun}\b.*(city|country|state|place|street|avenue|road)', text, re.IGNORECASE):
                    entity_type = EntityType.LOCATION
                elif re.search(rf'\b{noun}\b.*(company|corporation|inc|llc|organization)', text, re.IGNORECASE):
                    entity_type = EntityType.ORGANIZATION
                elif re.search(rf'\b(mr|mrs|ms|dr|prof)\s+{noun}\b', text, re.IGNORECASE):
                    entity_type = EntityType.PERSON
                else:
                    # Skip ambiguous capitalized words - too noisy
                    continue
                
                # Only create entity if we have a clear type
                if entity_type:
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=entity_type,
                        canonical_name=noun,
                        importance_score=5.0 if entity_type == EntityType.PERSON else 3.0
                    )
                    self.entities[entity_id] = entity
                    self.entities[entity_id].add_mention(turn_num, noun)
    
    def resolve_coreferences(self):
        
        # Group entities by type
        person_entities = [e for e in self.entities.values() if e.entity_type == EntityType.PERSON]
        
        # Link "she/he" to most recently mentioned person
        # This is simplified; production would use more sophisticated NLP
        
        for entity in person_entities:
            # If entity is mentioned multiple times with different phrasings
            # consolidate them
            pass
    
    def build_user_profile(self, user_id: str, all_entities: List[Entity]) -> UserProfile:
        profile = UserProfile(
            user_id=user_id,
            conversation_count=1
        )
        
        # Add all entities to profile
        for entity in all_entities:
            profile.add_entity(entity)
        
        # Extract important facts from medical entities
        for entity in all_entities:
            if entity.entity_type == EntityType.MEDICAL_CONDITION:
                profile.add_important_fact(
                    fact=f"Has {entity.canonical_name}",
                    category="medical",
                    turn_num=entity.first_mentioned,
                    importance=entity.importance_score
                )
        
        return profile
    
    def build_profile(self, user_id: str, conversation_num: int = 1) -> UserProfile:
        
        profile = UserProfile(
            user_id=user_id,
            conversation_count=conversation_num
        )
        
        # Add all entities
        for entity in self.entities.values():
            profile.add_entity(entity)
        
        # Extract important facts from medical entities
        for entity in self.entities.values():
            if entity.entity_type == EntityType.MEDICAL_CONDITION:
                profile.add_important_fact(
                    fact=f"Has {entity.canonical_name}",
                    category="medical",
                    turn_num=entity.first_mentioned,
                    importance=entity.importance_score
                )
        
        return profile
    
    def format_entities(self) -> str:
        """Format entities for display"""
        output = []
        output.append("=" * 80)
        output.append("ENTITY LINKING RESULTS")
        output.append("=" * 80)
        output.append("")
        
        # Group by entity type
        by_type = defaultdict(list)
        for entity in self.entities.values():
            by_type[entity.entity_type].append(entity)
        
        for entity_type, entities in by_type.items():
            output.append(f"\n{entity_type.value.upper()} ENTITIES ({len(entities)}):")
            output.append("-" * 80)
            
            for entity in sorted(entities, key=lambda e: e.importance_score, reverse=True):
                output.append(f"\n  Entity: {entity.canonical_name}")
                output.append(f"  ID: {entity.entity_id}")
                output.append(f"  Importance: {entity.importance_score:.1f}")
                output.append(f"  Mentions: {len(entity.mentions)} times")
                output.append(f"  First: Turn {entity.first_mentioned}, Last: Turn {entity.last_mentioned}")
                
                if entity.attributes:
                    output.append("  Attributes:")
                    for key, value in entity.attributes.items():
                        if isinstance(value, dict):
                            output.append(f"    • {key}: {value['value']} (turn {value['first_mentioned']})")
                        else:
                            output.append(f"    • {key}: {value}")
                
                output.append(f"  Sample mentions:")
                for turn_num, mention in entity.mentions[:3]:  # Show first 3
                    output.append(f"    Turn {turn_num}: \"{mention[:60]}...\"")
        
        return "\n".join(output)


def main():
    """Demo entity linking"""
    import sys
    from memory_system import parse_conversation_file
    
    if len(sys.argv) < 2:
        print("Usage: python entity_linking.py <conversation_file>")
        sys.exit(1)
    
    conversation_file = sys.argv[1]
    
    print(f"Loading conversation from: {conversation_file}")
    conversation = parse_conversation_file(conversation_file)
    print(f"Loaded {len(conversation)} conversation turns\n")
    
    # Extract entities
    print("Extracting entities...")
    linker = EntityLinker()
    entities = linker.extract_entities(conversation)
    
    print(f"Found {len(entities)} entities\n")
    
    # Display results
    results = linker.format_entities()
    print(results)
    
    # Build user profile
    print("\n\nBuilding user profile...")
    profile = linker.build_profile("user_001", conversation_num=1)
    
    print("\n" + "=" * 80)
    print("USER PROFILE")
    print("=" * 80)
    print(f"User ID: {profile.user_id}")
    print(f"Conversations: {profile.conversation_count}")
    print(f"Entities tracked: {len(profile.entities)}")
    print(f"Important facts: {len(profile.important_facts)}")
    
    if profile.important_facts:
        print("\nKey Facts:")
        for fact in profile.important_facts[:5]:
            print(f"  • {fact['fact']} (importance: {fact['importance']:.1f})")
    
    # Save results
    output_file = conversation_file.replace('.txt', '_entities.txt')
    with open(output_file, 'w') as f:
        f.write(results)
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("USER PROFILE\n")
        f.write("=" * 80 + "\n")
        f.write(f"User ID: {profile.user_id}\n")
        f.write(f"Entities tracked: {len(profile.entities)}\n")
        f.write(f"Important facts: {len(profile.important_facts)}\n")
    
    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
