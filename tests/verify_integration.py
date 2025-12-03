import sys
import importlib
from typing import List, Dict

def color_text(text: str, color: str) -> str:
    """Add color to text"""
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['end']}"

def check_import(module_name: str) -> bool:
    """Check if a module can be imported"""
    try:
        importlib.import_module(module_name)
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False

def verify_entity_linking() -> Dict[str, bool]:
    """Verify entity linking integration"""
    results = {}
    
    print("\n" + "="*80)
    print("CODE INTEGRATION VERIFICATION")
    print("="*80)
    
    # 1. Check core entity_linking module
    print("\n1. Core Entity Linking Module")
    print("-" * 80)
    results['entity_linking'] = check_import('entity_linking')
    if results['entity_linking']:
        from entity_linking import EntityLinker, Entity, EntityType, UserProfile
        print(color_text("  ✓ entity_linking.py imports successfully", 'green'))
        print(f"    - EntityLinker: {EntityLinker is not None}")
        print(f"    - Entity: {Entity is not None}")
        print(f"    - EntityType: {EntityType is not None}")
        print(f"    - UserProfile: {UserProfile is not None}")
    else:
        print(color_text("  ✗ entity_linking.py import failed", 'red'))
    
    # 2. Check unified_memory_system integration
    print("\n2. Unified Memory System Integration")
    print("-" * 80)
    results['unified_system'] = check_import('unified_memory_system')
    if results['unified_system']:
        from unified_memory_system import UnifiedMemorySystem
        print(color_text("  ✓ unified_memory_system.py imports successfully", 'green'))
        
        # Check if entity linking is integrated
        try:
            system = UnifiedMemorySystem(
                user_id="test",
                enable_entities=True,
                enable_llm=False,
                enable_learning=False
            )
            has_entity_linker = hasattr(system, 'entity_linker')
            results['unified_has_entities'] = has_entity_linker
            
            if has_entity_linker:
                print(color_text("  ✓ UnifiedMemorySystem has entity_linker attribute", 'green'))
                print(f"    - enable_entities: {system.enable_entities}")
                print(f"    - entity_linker: {system.entity_linker.__class__.__name__}")
            else:
                print(color_text("  ✗ UnifiedMemorySystem missing entity_linker", 'red'))
        except Exception as e:
            print(color_text(f"  ✗ Error creating UnifiedMemorySystem: {e}", 'red'))
            results['unified_has_entities'] = False
    else:
        print(color_text("  ✗ unified_memory_system.py import failed", 'red'))
    
    # 3. Check production API integration
    print("\n3. Production API Integration")
    print("-" * 80)
    try:
        with open('production_api.py', 'r') as f:
            api_code = f.read()
        
        # Check for key integration points
        checks = {
            'imports_unified': 'from unified_memory_system import' in api_code,
            'enable_entities_param': 'enable_entities' in api_code,
            'entity_links_field': 'entity_links' in api_code,
            'entities_in_summary': 'entities_found' in api_code
        }
        
        results['production_api'] = all(checks.values())
        
        for check_name, passed in checks.items():
            status = color_text("✓", 'green') if passed else color_text("✗", 'red')
            print(f"  {status} {check_name.replace('_', ' ').title()}: {passed}")
        
        if results['production_api']:
            print(color_text("  ✓ Production API properly integrated", 'green'))
        else:
            print(color_text("  ⚠ Production API partially integrated", 'yellow'))
    except Exception as e:
        print(color_text(f"  ✗ Error checking production_api.py: {e}", 'red'))
        results['production_api'] = False
    
    # 4. Check Streamlit app integration
    print("\n4. Streamlit App Integration")
    print("-" * 80)
    try:
        with open('app.py', 'r') as f:
            app_code = f.read()
        
        checks = {
            'imports_unified': 'from unified_memory_system import' in app_code,
            'enable_entities_checkbox': 'enable_entities' in app_code and 'checkbox' in app_code,
            'entities_in_system': 'enable_entities=' in app_code,
            'entity_display': 'entities' in app_code.lower()
        }
        
        results['streamlit_app'] = all(checks.values())
        
        for check_name, passed in checks.items():
            status = color_text("✓", 'green') if passed else color_text("✗", 'red')
            print(f"  {status} {check_name.replace('_', ' ').title()}: {passed}")
        
        if results['streamlit_app']:
            print(color_text("  ✓ Streamlit app properly integrated", 'green'))
        else:
            print(color_text("  ⚠ Streamlit app partially integrated", 'yellow'))
    except Exception as e:
        print(color_text(f"  ✗ Error checking app.py: {e}", 'red'))
        results['streamlit_app'] = False
    
    # 5. Check test coverage
    print("\n5. Test Coverage")
    print("-" * 80)
    try:
        with open('test_comprehensive.py', 'r') as f:
            test_code = f.read()
        
        checks = {
            'tests_entities': 'enable_entities=True' in test_code,
            'imports_unified': 'UnifiedMemorySystem' in test_code
        }
        
        results['tests'] = all(checks.values())
        
        for check_name, passed in checks.items():
            status = color_text("✓", 'green') if passed else color_text("✗", 'red')
            print(f"  {status} {check_name.replace('_', ' ').title()}: {passed}")
        
        if results['tests']:
            print(color_text("  ✓ Tests cover entity linking", 'green'))
        else:
            print(color_text("  ⚠ Tests may not cover entity linking", 'yellow'))
    except Exception as e:
        print(color_text(f"  ✗ Error checking test_comprehensive.py: {e}", 'red'))
        results['tests'] = False
    
    # 6. Functional test
    print("\n6. Functional Test")
    print("-" * 80)
    try:
        from unified_memory_system import UnifiedMemorySystem
        
        system = UnifiedMemorySystem(
            user_id="verify_test",
            enable_entities=True,
            enable_llm=False,
            enable_learning=False
        )
        
        # Simple test conversation
        conversation = [
            {"speaker": "user", "content": "My daughter Emily is 5 years old"},
            {"speaker": "assistant", "content": "Nice to meet Emily!"},
            {"speaker": "user", "content": "She loves painting"}
        ]
        
        results_list = system.process_conversation(conversation)
        
        # Check if entities were extracted
        entities_found = any(len(r.entities) > 0 for r in results_list)
        
        results['functional'] = entities_found
        
        if entities_found:
            entity_count = sum(len(r.entities) for r in results_list)
            print(color_text(f"  ✓ Functional test passed: {entity_count} entities extracted", 'green'))
            
            # Show entities
            for result in results_list:
                if result.entities:
                    for entity in result.entities:
                        print(f"    - {entity.canonical_name} ({entity.entity_type.value})")
        else:
            print(color_text("  ✗ Functional test failed: No entities extracted", 'red'))
    except Exception as e:
        print(color_text(f"  ✗ Functional test error: {e}", 'red'))
        import traceback
        traceback.print_exc()
        results['functional'] = False
    
    return results

def print_summary(results: Dict[str, bool]):
    """Print verification summary"""
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTests Passed: {passed}/{total}")
    
    if passed == total:
        print(color_text("\n✓ ALL SYSTEMS INTEGRATED - Entity linking fully operational!", 'green'))
        print("\nWhat's working:")
        print("  ✓ Core entity linking module")
        print("  ✓ Unified memory system integration")
        print("  ✓ Production API support")
        print("  ✓ Streamlit UI integration")
        print("  ✓ Test coverage")
        print("  ✓ Functional verification")
        
        print("\nReady to use:")
        print("  • python3 demo_entity_resolution.py")
        print("  • python3 entity_linking.py test_conversation_1.txt")
        print("  • streamlit run app.py (with entity extraction enabled)")
        print("  • Production API with enable_entities=True")
        
    elif passed >= total * 0.7:
        print(color_text("\n⚠ MOSTLY INTEGRATED - Minor issues detected", 'yellow'))
        print("\nWorking:")
        for key, value in results.items():
            if value:
                print(f"  ✓ {key}")
        print("\nNeeds attention:")
        for key, value in results.items():
            if not value:
                print(f"  ✗ {key}")
    else:
        print(color_text("\n✗ INTEGRATION INCOMPLETE - Significant issues", 'red'))
        print("\nFailed checks:")
        for key, value in results.items():
            if not value:
                print(f"  ✗ {key}")

if __name__ == "__main__":
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + " "*20 + "Entity Linking Integration Check" + " "*26 + "║")
    print("║" + " "*78 + "║")
    print("╚" + "═"*78 + "╝")
    
    results = verify_entity_linking()
    print_summary(results)
    
    # Exit code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
