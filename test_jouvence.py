#!/usr/bin/env python3
"""
Test script to explore Jouvence fountain parser data structure.
This helps us understand how to integrate with ScriptRAG's data models.
"""

from jouvence.parser import JouvenceParser

# Sample fountain script for testing
SAMPLE_FOUNTAIN = """
Title: Test Script
Author: ScriptRAG Test
Format: screenplay

FADE IN:

EXT. COFFEE SHOP - DAY

A busy coffee shop on a sunny morning. ALICE (30s, determined) sits at a table with her laptop.

                    ALICE
          (muttering to herself)
     This code has to work.

BARISTA approaches with a steaming cup.

                    BARISTA
     One large coffee for the lady
     who's been here since dawn?

                    ALICE
                    (looking up)
     Thanks. I'm trying to build
     something revolutionary.

                    BARISTA
     Aren't we all?

CUT TO:

INT. ALICE'S APARTMENT - NIGHT

Alice reviews her work on multiple monitors.

                    ALICE
     Finally! It's working!

FADE OUT.
"""

def debug_title_parsing():
    """Debug title page parsing specifically."""
    print("=== Title Page Parsing Debug ===\n")

    # Test with explicit title page format
    title_page_content = """Title: Test Script
Author: Test Author
Format: screenplay

FADE IN:

EXT. COFFEE SHOP - DAY

A simple scene.

FADE OUT.
"""

    parser = JouvenceParser()
    document = parser.parseString(title_page_content)

    print("Raw content being parsed:")
    print(repr(title_page_content[:100]) + "...")
    print()

    print("Title values found:", document.title_values)
    print("Type:", type(document.title_values))
    print("Length:", len(document.title_values) if document.title_values else 0)
    print()

    if document.title_values:
        for key, value in document.title_values.items():
            print(f"Key: {key!r} -> Value: {value!r}")
    else:
        print("No title values found!")

    print("\nFirst scene header:", document.scenes[0].header if document.scenes else "No scenes")
    print("Number of scenes:", len(document.scenes))

    # Check if title info is buried in the first scene
    if document.scenes and document.scenes[0].paragraphs:
        print("\nFirst scene first paragraph:")
        first_para = document.scenes[0].paragraphs[0]
        print(f"Type: {first_para.type}")
        print(f"Text: {first_para.text[:200]!r}...")

def explore_jouvence_structure():
    """Explore the structure of Jouvence parsed documents."""
    print("=== Jouvence Structure Exploration ===\n")

    # Element type mapping (these appear to be constants from Jouvence)
    ELEMENT_TYPE_NAMES = {
        0: 'ACTION',
        1: 'SCENE_HEADING',
        2: 'CHARACTER',
        3: 'DIALOGUE',
        4: 'PARENTHETICAL',
        5: 'TRANSITION',
        6: 'SHOT',
        7: 'BONEYARD',
        8: 'PAGE_BREAK',
        9: 'SYNOPSIS',
        10: 'SECTION',
    }

    parser = JouvenceParser()
    document = parser.parseString(SAMPLE_FOUNTAIN)

    print("Document type:", type(document))
    print("Document attributes:", [attr for attr in dir(document) if not attr.startswith('_')])
    print()

    # Explore title page
    if hasattr(document, 'title_values'):
        print("Title values:", document.title_values)
        print("Title values type:", type(document.title_values))
        print("Title values keys:", list(document.title_values.keys()) if document.title_values else "No keys")
        for key, value in (document.title_values.items() if document.title_values else []):
            print(f"  {key!r}: {value!r}")
        print()

    # Explore scenes
    if hasattr(document, 'scenes'):
        print(f"Number of scenes: {len(document.scenes)}")
        print("Scenes type:", type(document.scenes))
        print()

        for i, scene in enumerate(document.scenes):
            print(f"--- Scene {i} ---")
            print("Scene type:", type(scene))
            print("Scene attributes:", [attr for attr in dir(scene) if not attr.startswith('_')])

            if hasattr(scene, 'header'):
                print("Scene header:", scene.header)
                print("Header type:", type(scene.header) if scene.header else "None")

            if hasattr(scene, 'paragraphs'):
                print(f"Number of paragraphs: {len(scene.paragraphs)}")

                for j, paragraph in enumerate(scene.paragraphs[:5]):  # Show first 5 paragraphs
                    print(f"  Paragraph {j}:")
                    print(f"    Type: {type(paragraph)}")
                    print(f"    Attributes: {[attr for attr in dir(paragraph) if not attr.startswith('_')]}")

                    if hasattr(paragraph, 'type'):
                        print(f"    Element type: {paragraph.type}")
                    if hasattr(paragraph, 'paragraph_type'):
                        print(f"    Paragraph type: {paragraph.paragraph_type}")
                    if hasattr(paragraph, 'text'):
                        print(f"    Text: {repr(paragraph.text[:50])}...")
                    if hasattr(paragraph, 'character'):
                        print(f"    Character: {paragraph.character}")

                    print()

                if len(scene.paragraphs) > 5:
                    print(f"  ... and {len(scene.paragraphs) - 5} more paragraphs")

            print()

    # Try to understand the paragraph types
    print("=== Element Type Analysis ===")
    element_types = set()
    element_examples = {}

    for scene in document.scenes:
        if hasattr(scene, 'paragraphs'):
            for paragraph in scene.paragraphs:
                if hasattr(paragraph, 'type'):
                    elem_type = paragraph.type
                    element_types.add(elem_type)
                    if elem_type not in element_examples:
                        element_examples[elem_type] = paragraph.text[:30] + "..." if len(paragraph.text) > 30 else paragraph.text
                else:
                    element_types.add(str(type(paragraph)))

    print("All element types found:", sorted(element_types))
    print("\nElement type examples:")
    for elem_type in sorted(element_examples.keys()):
        elem_name = ELEMENT_TYPE_NAMES.get(elem_type, f'UNKNOWN({elem_type})')
        print(f"  {elem_type} ({elem_name}): {repr(element_examples[elem_type])}")

    # Show detailed breakdown by element type
    print("\n=== Detailed Element Breakdown ===")
    for scene_idx, scene in enumerate(document.scenes):
        print(f"Scene {scene_idx} ({scene.header if scene.header else 'No header'}):")
        if hasattr(scene, 'paragraphs'):
            for para_idx, paragraph in enumerate(scene.paragraphs):
                elem_type_num = getattr(paragraph, 'type', -1)
                elem_type_name = ELEMENT_TYPE_NAMES.get(elem_type_num, f'UNKNOWN({elem_type_num})')
                text_preview = paragraph.text.strip()[:40].replace('\n', '\\n')
                print(f"  {para_idx:2d}. {elem_type_name:15s} | {text_preview}...")
        print()

if __name__ == "__main__":
    debug_title_parsing()
    print("\n" + "="*50 + "\n")
    explore_jouvence_structure()
