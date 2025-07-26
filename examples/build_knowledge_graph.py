#!/usr/bin/env python3
"""Example script demonstrating knowledge graph construction from a screenplay.

This script shows how to:
1. Parse a Fountain screenplay file
2. Build a rich knowledge graph with entities and relationships
3. Enrich the graph with LLM-generated metadata
4. Generate embeddings for semantic search
5. Query and analyze the resulting graph structure
"""

import argparse
import asyncio
import json
from pathlib import Path

from scriptrag.database import (
    DatabaseConnection,
    KnowledgeGraphBuilder,
    initialize_database,
)
from scriptrag.database.embedding_pipeline import EmbeddingPipeline
from scriptrag.llm.client import LLMClient
from scriptrag.parser import FountainParser


async def main(keep_existing: bool = False) -> None:
    """Build and analyze a screenplay knowledge graph.

    Args:
        keep_existing: If True, keep existing database instead of starting fresh
    """
    # Configuration
    db_path = Path("example_knowledge_graph.db")
    fountain_file = Path("examples/data/sample_screenplay.fountain")

    # Ensure we have a sample screenplay
    if not fountain_file.exists():
        print(f"Creating sample screenplay at {fountain_file}")
        fountain_file.parent.mkdir(parents=True, exist_ok=True)
        fountain_file.write_text(SAMPLE_SCREENPLAY)

    # Initialize database
    print(f"Initializing database at {db_path}")

    # Option to start fresh (controlled by parameter)
    if not keep_existing and db_path.exists():
        print("Removing existing database to start fresh")
        db_path.unlink()
    elif keep_existing and db_path.exists():
        print("Keeping existing database")

    conn = DatabaseConnection(str(db_path))
    initialize_database(str(db_path))

    # Initialize LLM client (optional - will use if available)
    llm_client = None
    try:
        llm_client = LLMClient()
        print("LLM client initialized for metadata enrichment")
    except Exception as e:
        print(f"LLM client not available: {e}")
        print("Proceeding without LLM enrichment")

    # Initialize embedding pipeline (optional)
    embedding_pipeline = None
    if llm_client:
        try:
            embedding_pipeline = EmbeddingPipeline(conn, llm_client)
            print("Embedding pipeline initialized")
        except Exception as e:
            print(f"Embedding pipeline not available: {e}")

    # Build knowledge graph
    # Set limits for enrichment (for demo purposes)
    builder = KnowledgeGraphBuilder(
        conn,
        llm_client,
        embedding_pipeline,
        max_scenes_to_enrich=10,  # Limit to first 10 scenes
        max_characters_to_enrich=5,  # Limit to first 5 characters
    )

    print(f"\nParsing screenplay: {fountain_file}")
    parser = FountainParser()
    script = parser.parse_file(fountain_file)

    # Get the actual Character and Scene objects from the parser
    characters = parser.get_characters()
    scenes = parser.get_scenes()

    print(f"\nBuilding knowledge graph for: {script.title}")
    stats = await builder.build_from_script(
        script, enrich_with_llm=bool(llm_client), characters=characters, scenes=scenes
    )

    print("\nGraph Construction Statistics:")
    print(json.dumps(stats, indent=2))

    # Build additional graph layers
    if stats["script_node_id"]:
        print("\nBuilding temporal relationships...")
        temporal_edges = await builder.build_temporal_graph(stats["script_node_id"])
        print(f"Created {temporal_edges} temporal edges")

        print("\nBuilding logical dependencies...")
        logical_edges = await builder.build_logical_dependencies(
            stats["script_node_id"]
        )
        print(f"Created {logical_edges} logical dependency edges")

    # Analyze the graph
    print("\n\nGraph Analysis:")
    analyze_graph(conn, stats["script_node_id"])

    # Clean up
    if llm_client:
        await llm_client.close()

    conn.close()
    print(f"\nKnowledge graph saved to: {db_path}")


def analyze_graph(conn: DatabaseConnection, script_node_id: str) -> None:
    """Analyze and display graph statistics."""
    from scriptrag.database.operations import GraphOperations

    ops = GraphOperations(conn)

    # Get all characters
    characters = ops.graph.find_nodes(node_type="character")
    print(f"\nCharacters ({len(characters)}):")
    for char in characters:
        degree = ops.graph.get_node_degree(char.id)
        scenes = ops.get_character_scenes(char.id)
        print(
            f"  - {char.label}: appears in {len(scenes)} scenes, {degree} connections"
        )

    # Get all locations
    locations = ops.graph.find_nodes(node_type="location")
    print(f"\nLocations ({len(locations)}):")
    for loc in locations:
        scenes = ops.get_location_scenes(loc.id)
        print(f"  - {loc.label}: {len(scenes)} scenes")

    # Get scene statistics
    scenes = ops.get_script_scenes(script_node_id)
    print(f"\nScenes ({len(scenes)}):")
    for i, scene in enumerate(scenes[:5]):  # Show first 5
        chars_in_scene = ops.graph.get_neighbors(
            scene.id, edge_type="APPEARS_IN", direction="in"
        )
        print(f"  - Scene {i + 1}: {scene.label} ({len(chars_in_scene)} characters)")

    # Character centrality analysis
    if characters:
        print("\nCharacter Centrality Analysis:")
        centrality = ops.analyze_character_centrality(script_node_id)

        # Sort by degree centrality
        sorted_chars = sorted(
            centrality.items(), key=lambda x: x[1]["degree_centrality"], reverse=True
        )

        for _char_id, metrics in sorted_chars[:5]:  # Top 5
            print(f"  - {metrics['character_name']}:")
            print(f"    Degree: {metrics['degree_centrality']:.2f}")
            print(f"    Scenes: {metrics['scene_frequency']}")
            print(f"    Interactions: {metrics['interaction_diversity']}")


# Sample screenplay for demonstration
SAMPLE_SCREENPLAY = """Title: The Coffee Shop Encounter
Author: ScriptRAG Demo
Format: Short Film

FADE IN:

INT. COFFEE SHOP - DAY

A cozy neighborhood coffee shop. Warm lighting, the sound of
espresso machines. SARAH (28), a writer with horn-rimmed
glasses, sits at a corner table with her laptop.

JOHN (32), slightly disheveled but charming, enters and
approaches the counter.

BARISTA
The usual, John?

JOHN
Actually, make it two lattes today.

John glances at Sarah, who's deeply focused on her screen.

JOHN (CONT'D)
(to himself)
Here goes nothing.

John approaches Sarah's table with both lattes.

JOHN (CONT'D)
Excuse me, I couldn't help but notice
you've been staring at that blank page
for twenty minutes.

SARAH
(looking up, surprised)
Were you watching me?

JOHN
(embarrassed)
No, I mean... I'm a writer too. I know
that look. Writer's block?

Sarah closes her laptop slightly, intrigued.

SARAH
Something like that. And the second
latte is...?

JOHN
A peace offering for interrupting. May I?

He gestures to the empty chair. Sarah considers, then nods.

SARAH
Five minutes. But the coffee better be
good.

John sits, sliding the latte across to her.

JOHN
Best in the neighborhood. I'm John.

SARAH
Sarah. So, what do you write?

JOHN
Screenplays, mostly. You?

SARAH
Fiction. Though lately it's more like
fiction about writing fiction.

They both laugh. The ice breaks.

MONTAGE - COFFEE SHOP CONVERSATIONS

- John and Sarah deep in animated discussion
- Sarah showing John something on her laptop
- Both laughing over coffee
- The barista bringing them refills

INT. COFFEE SHOP - LATER

The afternoon light has shifted. Multiple empty coffee cups
on the table.

SARAH
I can't believe we've been talking for
three hours.

JOHN
Time flies when you're solving the
world's literary problems.

SARAH
Or avoiding them.

JOHN
(grinning)
That too.

Sarah starts packing up her laptop.

SARAH
This was... unexpected. But nice.

JOHN
Nice enough to do again? Same time
tomorrow?

SARAH
(smiling)
I'll bring the coffee this time.

JOHN
Deal. And Sarah? Thanks for the five
minutes.

SARAH
Best writer's block I've ever had.

She leaves. John watches her go, then opens his own laptop,
suddenly inspired.

FADE OUT.

THE END
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a knowledge graph from a screenplay"
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing database instead of starting fresh",
    )
    args = parser.parse_args()

    asyncio.run(main(keep_existing=args.keep_existing))
