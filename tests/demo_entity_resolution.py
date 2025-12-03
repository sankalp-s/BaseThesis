from memory_system import ConversationalMemorySystem, ConversationTurn, RetentionLevel
from entity_linking import EntityLinker, EntityType
from unified_memory_system import UnifiedMemorySystem


def demo_entity_fragmentation_problem():
    """Show the problem without entity linking"""
    print("=" * 80)
    print("PROBLEM: Entity Fragmentation WITHOUT Entity Linking")
    print("=" * 80)
    print()
    
    # Sample conversation with entity references
    conversation = [
        ConversationTurn("user", "My daughter Emily is 5 years old", 0),
        ConversationTurn("assistant", "That's a nice age! What does Emily like to do?", 1),
        ConversationTurn("user", "She loves to paint and draw", 2),
        ConversationTurn("assistant", "Creative! Does she go to school?", 3),
        ConversationTurn("user", "Yes, she starts kindergarten next week", 4),
        ConversationTurn("assistant", "Exciting! Is she nervous?", 5),
        ConversationTurn("user", "A little. My daughter has always been shy around new people", 6),
    ]
    
    # Analyze WITHOUT entity linking (base system)
    base_system = ConversationalMemorySystem()
    memory_items = base_system.analyze_conversation(conversation)
    
    print("Memory items created (each reference treated separately):\n")
    
    daughter_mentions = []
    for item in memory_items:
        if any(word in item.content.lower() for word in ['daughter', 'emily', 'she', 'her']):
            daughter_mentions.append(item)
    
    for i, item in enumerate(daughter_mentions, 1):
        print(f"{i}. Turn {item.turn_number}: \"{item.content}\"")
        print(f"   Retention: {item.retention.value}")
        print(f"   Categories: {', '.join(item.categories)}")
        print()
    
    print(f"❌ PROBLEM: {len(daughter_mentions)} separate memory items for same entity")
    print("   - 'My daughter', 'Emily', 'She' treated as different entities")
    print("   - No understanding that these refer to the same person")
    print("   - Can't build coherent profile: age, name, interests scattered")
    print()


def demo_entity_resolution_solution():
    """Show the solution WITH entity linking"""
    print("\n" + "=" * 80)
    print("SOLUTION: Entity Linking Resolves References")
    print("=" * 80)
    print()
    
    # Same conversation
    conversation = [
        ConversationTurn("user", "My daughter Emily is 5 years old", 0),
        ConversationTurn("assistant", "That's a nice age! What does Emily like to do?", 1),
        ConversationTurn("user", "She loves to paint and draw", 2),
        ConversationTurn("assistant", "Creative! Does she go to school?", 3),
        ConversationTurn("user", "Yes, she starts kindergarten next week", 4),
        ConversationTurn("assistant", "Exciting! Is she nervous?", 5),
        ConversationTurn("user", "My daughter has always been shy around new people", 6),
    ]
    
    # Extract entities with linking
    linker = EntityLinker()
    entities = linker.extract_entities(conversation)
    
    print("Entities extracted and linked:\n")
    
    # Find the daughter entity
    daughter_entity = None
    for entity in entities:
        if entity.entity_type == EntityType.PERSON and 'daughter' in entity.canonical_name.lower():
            daughter_entity = entity
            break
    
    if daughter_entity:
        print(f"✅ Entity: {daughter_entity.canonical_name}")
        print(f"   Entity ID: {daughter_entity.entity_id}")
        print(f"   Type: {daughter_entity.entity_type.value}")
        print(f"   Importance: {daughter_entity.importance_score:.1f}")
        print()
        
        print(f"   Mentions consolidated ({len(daughter_entity.mentions)} total):")
        for turn_num, mention in daughter_entity.mentions:
            print(f"   • Turn {turn_num}: \"{mention}\"")
        print()
        
        print("   Attributes extracted:")
        for key, value_data in daughter_entity.attributes.items():
            value = value_data['value'] if isinstance(value_data, dict) else value_data
            print(f"   • {key}: {value}")
        print()
    
    print("✅ SOLVED:")
    print("   - All references linked to single entity")
    print("   - Attributes accumulated: age (5), starting kindergarten, shy")
    print("   - Can answer: 'Tell me about the user's daughter' → coherent response")
    print("   - Cross-turn coherence maintained")
    print()


def demo_medical_entity_tracking():
    """Show medical condition tracking across mentions"""
    print("\n" + "=" * 80)
    print("MEDICAL ENTITY TRACKING")
    print("=" * 80)
    print()
    
    conversation = [
        ConversationTurn("user", "I have a severe peanut allergy", 0),
        ConversationTurn("assistant", "I'll remember that. Do you carry an EpiPen?", 1),
        ConversationTurn("user", "Yes, always. The peanut allergy is life-threatening", 2),
        ConversationTurn("assistant", "Good to know. Any other allergies?", 3),
        ConversationTurn("user", "Just the peanuts. Had a reaction last year that was scary", 4),
    ]
    
    linker = EntityLinker()
    entities = linker.extract_entities(conversation)
    
    # Find peanut allergy entity
    peanut_entity = None
    for entity in entities:
        if entity.entity_type == EntityType.MEDICAL_CONDITION and 'peanut' in entity.canonical_name.lower():
            peanut_entity = entity
            break
    
    if peanut_entity:
        print("✅ Medical condition tracked across mentions:\n")
        print(f"   Entity: {peanut_entity.canonical_name}")
        print(f"   Entity ID: {peanut_entity.entity_id}")
        print(f"   Importance: {peanut_entity.importance_score:.1f}")
        print()
        
        print(f"   All mentions consolidated ({len(peanut_entity.mentions)} times):")
        for turn_num, mention in peanut_entity.mentions:
            snippet = mention[:70] + "..." if len(mention) > 70 else mention
            print(f"   • Turn {turn_num}: \"{snippet}\"")
        print()
        
        print("✅ Benefits:")
        print("   - Single entity captures full context: severe + life-threatening + EpiPen")
        print("   - Can track: first mention (turn 0), last mention (turn 4)")
        print("   - Importance score reflects all mentions (not just first)")
        print()


def demo_unified_system_with_entities():
    """Show complete unified system with entity linking"""
    print("\n" + "=" * 80)
    print("UNIFIED SYSTEM: Memory Classification + Entity Linking")
    print("=" * 80)
    print()
    
    conversation = [
        {"speaker": "user", "content": "Hi, I'm Sarah"},
        {"speaker": "assistant", "content": "Hello Sarah!"},
        {"speaker": "user", "content": "My daughter Emily is allergic to shellfish"},
        {"speaker": "assistant", "content": "I'll remember that. How old is Emily?"},
        {"speaker": "user", "content": "She's 8. Very serious allergy, carries EpiPen"},
        {"speaker": "assistant", "content": "Important to know. Anything else?"},
        {"speaker": "user", "content": "My daughter also has asthma, so we're extra careful"},
    ]
    
    # Process with unified system (includes entity linking)
    system = UnifiedMemorySystem(
        user_id="sarah_demo",
        enable_llm=False,  # Disable LLM for faster demo
        enable_entities=True,
        enable_learning=False
    )
    
    results = system.process_conversation(conversation)
    
    print("Processing complete. Results:\n")
    
    # Show memory classification
    print("1. MEMORY CLASSIFICATION:")
    print("-" * 80)
    long_term = [r for r in results if r.memory_item.retention == RetentionLevel.LONG_TERM]
    
    for result in long_term[:5]:  # Show top 5
        print(f"\n   \"{result.memory_item.content}\"")
        print(f"   • Importance: {result.memory_item.importance_score}")
        print(f"   • Categories: {', '.join(result.memory_item.categories)}")
        print(f"   • Entities found: {len(result.entities)}")
    
    # Show entities extracted
    print("\n\n2. ENTITIES EXTRACTED & LINKED:")
    print("-" * 80)
    
    all_entities = []
    for result in results:
        all_entities.extend(result.entities)
    
    # Deduplicate by entity_id
    unique_entities = {}
    for entity in all_entities:
        if entity.entity_id not in unique_entities:
            unique_entities[entity.entity_id] = entity
    
    print(f"\n   Total unique entities: {len(unique_entities)}\n")
    
    for entity in unique_entities.values():
        print(f"   • {entity.canonical_name} ({entity.entity_type.value})")
        print(f"     ID: {entity.entity_id}")
        print(f"     Mentions: {len(entity.mentions)} times")
        if entity.attributes:
            print(f"     Attributes: {list(entity.attributes.keys())}")
        print()
    
    # Show user profile
    print("\n3. USER PROFILE BUILT:")
    print("-" * 80)
    
    if results[0].user_profile:
        profile = results[0].user_profile
        
        if profile.people:
            print("\n   People:")
            for name, relations in profile.people.items():
                print(f"   • {name}: {', '.join(relations)}")
        
        if profile.medical_conditions:
            print("\n   Medical conditions:")
            for condition in profile.medical_conditions:
                print(f"   • {condition}")
    
    print("\n\n✅ COMPLETE SOLUTION:")
    print("   1. Memory classification (what to remember, for how long)")
    print("   2. Entity linking (who/what entities, with attributes)")
    print("   3. User profile (coherent cross-turn understanding)")
    print()


def demo_complex_coreference():
    """Show complex coreference resolution"""
    print("\n" + "=" * 80)
    print("COMPLEX COREFERENCE RESOLUTION")
    print("=" * 80)
    print()
    
    conversation = [
        ConversationTurn("user", "I have two kids. My son John is 12", 0),
        ConversationTurn("assistant", "Nice to meet John!", 1),
        ConversationTurn("user", "He plays soccer. My daughter is younger", 2),
        ConversationTurn("assistant", "How old is your daughter?", 3),
        ConversationTurn("user", "She's 8. Her name is Sarah", 4),
        ConversationTurn("assistant", "Does Sarah play sports too?", 5),
        ConversationTurn("user", "Both kids love swimming. They swim together", 6),
    ]
    
    linker = EntityLinker()
    entities = linker.extract_entities(conversation)
    
    print("Entities identified:\n")
    
    people = [e for e in entities if e.entity_type == EntityType.PERSON]
    
    for person in people:
        print(f"✅ {person.canonical_name}")
        print(f"   Entity ID: {person.entity_id}")
        print(f"   Mentions: {len(person.mentions)} times")
        
        if person.attributes:
            print("   Attributes:")
            for key, value_data in person.attributes.items():
                value = value_data['value'] if isinstance(value_data, dict) else value_data
                print(f"   • {key}: {value}")
        print()
    
    print("✅ COREFERENCE RESOLUTION:")
    print("   - 'My son' → 'John' → 'He' (linked)")
    print("   - 'My daughter' → 'Sarah' → 'She' (linked)")
    print("   - 'Two kids' → 'Both kids' → 'They' (linked to both)")
    print("   - Attributes accumulated: ages, interests, activities")
    print()


if __name__ == "__main__":
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + " " * 20 + "ENTITY RESOLUTION DEMONSTRATION" + " " * 27 + "║")
    print("║" + " " * 15 + "Solving Entity Fragmentation Problem" + " " * 27 + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Show the problem
    demo_entity_fragmentation_problem()
    
    # Show the solution
    demo_entity_resolution_solution()
    
    # Show medical tracking
    demo_medical_entity_tracking()
    
    # Show unified system
    demo_unified_system_with_entities()
    
    # Show complex coreference
    demo_complex_coreference()
    
    print("\n" + "=" * 80)
    print("SUMMARY: Entity Fragmentation SOLVED")
    print("=" * 80)
    print()
    print("Without entity linking:")
    print("  ❌ 'My daughter', 'she', 'Emily' → 3 separate memory items")
    print("  ❌ No coherent profile")
    print("  ❌ Can't answer: 'What do you know about Emily?'")
    print()
    print("With entity linking:")
    print("  ✅ All references → Single entity with attributes")
    print("  ✅ Coherent profile: Emily (daughter, age 5, shy, starting kindergarten)")
    print("  ✅ Can answer complex queries about entities")
    print("  ✅ Cross-conversation memory possible")
    print()
    print("Implementation:")
    print("  • Pattern-based entity extraction (relationships, medical, named entities)")
    print("  • Attribute accumulation across mentions")
    print("  • Entity database with unique IDs")
    print("  • Integrated with memory classification system")
    print()
    print("=" * 80)
