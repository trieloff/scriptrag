"""Knowledge Graph Builder for ScriptRAG.

This module implements the knowledge graph construction pipeline that parses
screenplays into rich graph structures with entity extraction, relationship
building, and LLM-powered metadata enrichment.
"""

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from scriptrag.config import get_logger
from scriptrag.llm.client import LLMClient
from scriptrag.models import (
    Action,
    Character,
    Dialogue,
    Location,
    Parenthetical,
    Scene,
    SceneOrderType,
    Script,
)
from scriptrag.parser import FountainParser

from .connection import DatabaseConnection
from .content_extractor import ContentExtractor
from .embedding_pipeline import EmbeddingPipeline
from .operations import GraphOperations

logger = get_logger(__name__)


class KnowledgeGraphBuilder:
    """Builds knowledge graphs from parsed screenplays.

    This class orchestrates the transformation of screenplay data into a rich
    graph structure with nodes for scenes, characters, locations, and their
    relationships. It also enriches the graph with LLM-generated metadata.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        llm_client: LLMClient | None = None,
        embedding_pipeline: EmbeddingPipeline | None = None,
    ) -> None:
        """Initialize the knowledge graph builder.

        Args:
            connection: Database connection
            llm_client: Optional LLM client for metadata enrichment
            embedding_pipeline: Optional embedding pipeline for semantic enrichment
        """
        self.connection = connection
        self.graph_ops = GraphOperations(connection)
        self.content_extractor = ContentExtractor(connection)
        self.llm_client = llm_client
        self.embedding_pipeline = embedding_pipeline
        self.logger = logger

        # Caches for deduplication
        self._location_nodes: dict[str, str] = {}  # location_str -> node_id
        self._character_nodes: dict[UUID, str] = {}  # character.id -> node_id

    async def build_from_script(
        self, script: Script, enrich_with_llm: bool = True
    ) -> dict[str, Any]:
        """Build a complete knowledge graph from a Script model.

        Args:
            script: Parsed script model
            enrich_with_llm: Whether to enrich with LLM-generated metadata

        Returns:
            Dictionary with build statistics and node mappings
        """
        self.logger.info(f"Building knowledge graph for script: {script.title}")

        # Clear caches for new script
        self._location_nodes.clear()
        self._character_nodes.clear()

        stats: dict[str, Any] = {
            "script_node_id": "",
            "total_nodes": 0,
            "total_edges": 0,
            "scene_nodes": 0,
            "character_nodes": 0,
            "location_nodes": 0,
            "enrichment_status": "not_attempted",
        }

        try:
            # Create script node
            script_node_id = self.graph_ops.create_script_graph(script)
            stats["script_node_id"] = script_node_id
            stats["total_nodes"] += 1

            # Extract entities from the parser
            parser = FountainParser()
            characters = list(parser._characters_cache.values())
            scenes = []

            # Parse scenes from script
            if script.fountain_source:
                parsed_script = parser.parse_string(script.fountain_source)
                scenes = [
                    scene
                    for scene_id in parsed_script.scenes
                    for scene in [self._get_scene_by_id(scene_id, script)]
                    if scene
                ]

            # Build character nodes
            for character in characters:
                await self._create_character_node(character, script_node_id)
                stats["character_nodes"] += 1
                stats["total_nodes"] += 1

            # Build scene nodes and relationships
            scene_node_ids = []
            for scene_idx, scene in enumerate(scenes):
                scene_node_id = await self._create_scene_node(
                    scene, script_node_id, scene_idx
                )
                scene_node_ids.append(scene_node_id)
                stats["scene_nodes"] += 1
                stats["total_nodes"] += 1

            # Create scene sequences
            if scene_node_ids:
                # Script order (as written)
                edges = self.graph_ops.create_scene_sequence(
                    scene_node_ids, SceneOrderType.SCRIPT
                )
                stats["total_edges"] += len(edges)

            # Enrich with LLM if requested
            if enrich_with_llm and self.llm_client:
                try:
                    await self._enrich_with_llm(
                        script_node_id,
                        scene_node_ids,
                        list(self._character_nodes.values()),
                    )
                    stats["enrichment_status"] = "completed"
                except Exception as e:
                    self.logger.error(f"LLM enrichment failed: {e}")
                    stats["enrichment_status"] = "failed"

            # Generate embeddings if pipeline available
            if self.embedding_pipeline:
                try:
                    await self._generate_embeddings(script_node_id)
                    stats["embeddings_generated"] = True
                except Exception as e:
                    self.logger.error(f"Embedding generation failed: {e}")
                    stats["embeddings_generated"] = False

            self.logger.info(
                f"Knowledge graph built successfully: {stats['total_nodes']} nodes, "
                f"{stats['total_edges']} edges"
            )

        except Exception as e:
            self.logger.error(f"Failed to build knowledge graph: {e}")
            raise

        return stats

    async def build_from_fountain_file(
        self, file_path: str, enrich_with_llm: bool = True
    ) -> dict[str, Any]:
        """Build knowledge graph from a fountain file.

        Args:
            file_path: Path to fountain file
            enrich_with_llm: Whether to enrich with LLM-generated metadata

        Returns:
            Dictionary with build statistics
        """
        parser = FountainParser()
        script = parser.parse_file(file_path)
        return await self.build_from_script(script, enrich_with_llm)

    def _get_scene_by_id(self, scene_id: UUID, script: Script) -> Scene | None:
        """Helper to retrieve a scene by ID (mock implementation)."""
        # In real implementation, this would fetch from database
        # For now, return None as scenes are embedded in script
        _ = scene_id  # Unused in mock implementation
        _ = script  # Unused in mock implementation
        return None

    async def _create_character_node(
        self, character: Character, script_node_id: str
    ) -> str:
        """Create a character node with relationships."""
        if character.id in self._character_nodes:
            return self._character_nodes[character.id]

        node_id = self.graph_ops.create_character_node(character, script_node_id)
        self._character_nodes[character.id] = node_id

        self.logger.debug(f"Created character node: {character.name}")
        return node_id

    async def _create_scene_node(
        self, scene: Scene, script_node_id: str, scene_idx: int
    ) -> str:
        """Create a scene node with all its relationships."""
        # Create scene node
        scene_node_id = self.graph_ops.create_scene_node(scene, script_node_id)

        # Create/link location if present
        if scene.location:
            location_node_id = await self._get_or_create_location_node(
                scene.location, script_node_id
            )
            self.graph_ops.connect_scene_to_location(scene_node_id, location_node_id)

        # Process scene elements and extract relationships
        character_stats = await self._process_scene_elements(scene, scene_node_id)

        # Connect characters to scene
        for char_id, stats in character_stats.items():
            if char_id in self._character_nodes:
                self.graph_ops.connect_character_to_scene(
                    self._character_nodes[char_id],
                    scene_node_id,
                    speaking_lines=stats["dialogues"],
                    action_mentions=stats["mentions"],
                )

        # Extract character interactions
        await self._extract_character_interactions(scene, scene_node_id)

        self.logger.debug(
            f"Created scene node: {scene.heading or f'Scene {scene_idx}'}"
        )
        return scene_node_id

    async def _get_or_create_location_node(
        self, location: Location, script_node_id: str
    ) -> str:
        """Get existing or create new location node."""
        location_key = str(location)
        if location_key in self._location_nodes:
            return self._location_nodes[location_key]

        node_id = self.graph_ops.create_location_node(location, script_node_id)
        self._location_nodes[location_key] = node_id
        return node_id

    async def _process_scene_elements(
        self, scene: Scene, scene_node_id: str
    ) -> dict[UUID, dict[str, int]]:
        """Process scene elements and extract character statistics.

        Returns:
            Dictionary mapping character_id to stats (dialogues, mentions)
        """
        _ = scene_node_id  # Currently unused, may be used for future enhancements
        character_stats: dict[UUID, dict[str, int]] = defaultdict(
            lambda: {"dialogues": 0, "mentions": 0}
        )

        current_speaker_id: UUID | None = None

        for element in scene.elements:
            if isinstance(element, Dialogue):
                # Count dialogue for character
                if element.character_id:
                    character_stats[element.character_id]["dialogues"] += 1
                    current_speaker_id = element.character_id

            elif isinstance(element, Action):
                # Extract character mentions from action
                mentioned_chars = self._extract_character_mentions(element.text)
                for char_id in mentioned_chars:
                    character_stats[char_id]["mentions"] += 1

            elif isinstance(element, Parenthetical) and current_speaker_id:
                # Parentheticals belong to current speaker
                pass

        return dict(character_stats)

    def _extract_character_mentions(self, action_text: str) -> set[UUID]:
        """Extract character mentions from action text."""
        mentioned_ids = set()

        # Simple heuristic: look for character names in uppercase
        words = action_text.split()
        for char_id, node_id in self._character_nodes.items():
            # Get character name from node
            node = self.graph_ops.graph.get_node(node_id)
            if node and node.label:
                char_name = node.label.upper()
                # Check if character name appears in action
                if any(char_name in word.upper() for word in words):
                    mentioned_ids.add(char_id)

        return mentioned_ids

    async def _extract_character_interactions(
        self, scene: Scene, scene_node_id: str
    ) -> None:
        """Extract character-to-character interactions from dialogue patterns."""
        dialogue_elements = [
            elem for elem in scene.elements if isinstance(elem, Dialogue)
        ]

        if len(dialogue_elements) < 2:
            return

        # Track dialogue exchanges between characters
        for i in range(len(dialogue_elements) - 1):
            current_dialogue = dialogue_elements[i]
            next_dialogue = dialogue_elements[i + 1]

            # If different characters, create SPEAKS_TO relationship
            if (
                current_dialogue.character_id
                and next_dialogue.character_id
                and current_dialogue.character_id != next_dialogue.character_id
                and current_dialogue.character_id in self._character_nodes
                and next_dialogue.character_id in self._character_nodes
            ):
                self.graph_ops.connect_character_interaction(
                    self._character_nodes[current_dialogue.character_id],
                    self._character_nodes[next_dialogue.character_id],
                    scene_node_id,
                    dialogue_count=1,
                )

    async def _enrich_with_llm(
        self,
        script_node_id: str,
        scene_node_ids: list[str],
        character_node_ids: list[str],
    ) -> None:
        """Enrich graph nodes with LLM-generated metadata."""
        _ = script_node_id  # Currently unused, may be used for script-level enrichment
        if not self.llm_client:
            return

        self.logger.info("Enriching graph with LLM-generated metadata")

        # Enrich scenes with summaries and themes
        scene_tasks = []
        for scene_node_id in scene_node_ids[:10]:  # Limit to first 10 for demo
            scene_tasks.append(self._enrich_scene_node(scene_node_id))

        # Enrich characters with descriptions
        character_tasks = []
        for char_node_id in character_node_ids[:5]:  # Limit to first 5 for demo
            character_tasks.append(self._enrich_character_node(char_node_id))

        # Run enrichment tasks concurrently
        all_tasks = scene_tasks + character_tasks
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

    async def _enrich_scene_node(self, scene_node_id: str) -> None:
        """Enrich a scene node with LLM-generated metadata."""
        try:
            node = self.graph_ops.graph.get_node(scene_node_id)
            if not node:
                return

            # Get scene content
            scene_text = self._get_scene_content(node)
            if not scene_text:
                return

            # Generate scene summary and themes
            prompt = f"""Analyze this screenplay scene and provide:
1. A brief one-sentence summary
2. The main theme or dramatic purpose
3. The emotional tone

Scene:
{scene_text[:1000]}  # Limit context length

Respond in this format:
Summary: [one sentence]
Theme: [main theme]
Tone: [emotional tone]"""

            if not self.llm_client:
                return

            response = await self.llm_client.generate_text(
                prompt,
                max_tokens=150,
                temperature=0.7,
                system_prompt=(
                    "You are a screenplay analyst. Be concise and insightful."
                ),
            )

            # Parse response and update node properties
            properties = node.properties.copy()
            for line in response.strip().split("\n"):
                if line.startswith("Summary:"):
                    properties["summary"] = line.replace("Summary:", "").strip()
                elif line.startswith("Theme:"):
                    properties["theme"] = line.replace("Theme:", "").strip()
                elif line.startswith("Tone:"):
                    properties["emotional_tone"] = line.replace("Tone:", "").strip()

            # Update node
            self.graph_ops.graph.update_node(scene_node_id, properties=properties)

        except Exception as e:
            self.logger.error(f"Failed to enrich scene {scene_node_id}: {e}")

    async def _enrich_character_node(self, character_node_id: str) -> None:
        """Enrich a character node with LLM-generated metadata."""
        try:
            node = self.graph_ops.graph.get_node(character_node_id)
            if not node or not node.label:
                return

            # Get character's scenes and dialogue
            scenes = self.graph_ops.get_character_scenes(character_node_id)
            if not scenes:
                return

            # Sample some dialogue
            dialogue_samples = self._get_character_dialogue_samples(
                node.label, scenes[:3]
            )

            prompt = f"""Analyze this character from a screenplay:
Character: {node.label}
Appears in {len(scenes)} scenes

Sample dialogue:
{dialogue_samples[:500]}

Provide:
1. A brief character description (personality/role)
2. Their main motivation
3. Their character arc potential

Respond in this format:
Description: [one sentence]
Motivation: [main drive]
Arc: [potential character development]"""

            if not self.llm_client:
                return

            response = await self.llm_client.generate_text(
                prompt,
                max_tokens=150,
                temperature=0.7,
                system_prompt=(
                    "You are a screenplay analyst. Be concise and insightful."
                ),
            )

            # Parse response and update node
            properties = node.properties.copy()
            for line in response.strip().split("\n"):
                if line.startswith("Description:"):
                    properties["description"] = line.replace("Description:", "").strip()
                elif line.startswith("Motivation:"):
                    properties["motivation"] = line.replace("Motivation:", "").strip()
                elif line.startswith("Arc:"):
                    properties["character_arc"] = line.replace("Arc:", "").strip()

            self.graph_ops.graph.update_node(character_node_id, properties=properties)

        except Exception as e:
            self.logger.error(f"Failed to enrich character {character_node_id}: {e}")

    def _get_scene_content(self, scene_node: Any) -> str:
        """Extract scene content for analysis."""
        # In a real implementation, this would fetch scene elements
        # For now, return heading if available
        return scene_node.properties.get("heading", "") or scene_node.label or ""

    def _get_character_dialogue_samples(
        self, character_name: str, scene_nodes: list[Any]
    ) -> str:
        """Extract sample dialogue for a character."""
        # In a real implementation, this would fetch actual dialogue
        # For now, return placeholder
        return f"[Dialogue samples for {character_name} from {len(scene_nodes)} scenes]"

    async def _generate_embeddings(self, script_node_id: str) -> None:
        """Generate embeddings for all entities in the script."""
        if not self.embedding_pipeline:
            return

        self.logger.info("Generating embeddings for graph entities")

        # Get all scenes
        scenes = self.graph_ops.get_script_scenes(script_node_id)

        # Generate scene embeddings
        for scene_node in scenes:
            if scene_node.entity_id:
                content = self._get_scene_content(scene_node)
                if content:
                    await self.embedding_pipeline.process_scene(
                        scene_node.entity_id, force_refresh=False
                    )

        # Get all characters and generate embeddings
        characters = self.graph_ops.graph.get_neighbors(
            script_node_id, edge_type="HAS_CHARACTER", direction="out"
        )

        for char_node in characters:
            if char_node.entity_id and char_node.label:
                # Create character description for embedding
                properties = char_node.properties
                description = properties.get("description", "")
                motivation = properties.get("motivation", "")
                content = f"{char_node.label}: {description} {motivation}".strip()

                if content:
                    await self.embedding_pipeline.process_character(
                        char_node.entity_id, force_refresh=False
                    )

    async def build_temporal_graph(self, script_node_id: str) -> int:
        """Build temporal ordering relationships between scenes.

        Args:
            script_node_id: Script node ID

        Returns:
            Number of temporal edges created
        """
        scenes = self.graph_ops.get_script_scenes(script_node_id)

        # For now, use simple heuristics for temporal ordering
        # In production, this would use more sophisticated analysis
        temporal_order = self._analyze_temporal_order(scenes)

        # Create temporal sequence
        if temporal_order:
            edges = self.graph_ops.create_scene_sequence(
                temporal_order, SceneOrderType.TEMPORAL
            )
            self.logger.info(f"Created {len(edges)} temporal relationships")
            return len(edges)

        return 0

    async def build_logical_dependencies(self, script_node_id: str) -> int:
        """Build logical dependency relationships between scenes.

        Args:
            script_node_id: Script node ID

        Returns:
            Number of logical edges created
        """
        scenes = self.graph_ops.get_script_scenes(script_node_id)

        # Analyze logical dependencies (cause-effect, setup-payoff)
        dependencies = self._analyze_logical_dependencies(scenes)

        edges_created = 0
        for from_scene, to_scene in dependencies:
            edge_id = self.graph_ops.graph.add_edge(
                from_node_id=from_scene,
                to_node_id=to_scene,
                edge_type="DEPENDS_ON",
                properties={"dependency_type": "logical"},
            )
            if edge_id:
                edges_created += 1

        self.logger.info(f"Created {edges_created} logical dependency relationships")
        return edges_created

    def _analyze_temporal_order(self, scenes: list[Any]) -> list[str]:
        """Analyze and determine temporal order of scenes."""
        # Simple implementation: use script order with day/night analysis
        # In production, would use more sophisticated temporal reasoning

        temporal_scenes = []
        for scene in scenes:
            time_of_day = scene.properties.get("time_of_day", "")
            temporal_scenes.append((scene.id, time_of_day, scene))

        # Sort by implied temporal order (simplified)
        # Morning -> Day -> Evening -> Night
        time_order = {"MORNING": 1, "DAY": 2, "AFTERNOON": 3, "EVENING": 4, "NIGHT": 5}

        temporal_scenes.sort(
            key=lambda x: (
                time_order.get(x[1].upper(), 99),
                x[2].properties.get("script_order", 0),
            )
        )

        return [scene_id for scene_id, _, _ in temporal_scenes]

    def _analyze_logical_dependencies(self, scenes: list[Any]) -> list[tuple[str, str]]:
        """Analyze logical dependencies between scenes."""
        dependencies = []

        # Simple implementation: look for setup/payoff patterns
        # In production, would use NLP and story structure analysis

        for i, scene in enumerate(scenes[:-1]):
            # Check if scene introduces something that's resolved later
            scene_chars = {
                edge.from_node_id
                for edge in self.graph_ops.graph.find_edges(
                    to_node_id=scene.id, edge_type="APPEARS_IN"
                )
            }

            for _j, later_scene in enumerate(scenes[i + 1 :], i + 1):
                later_chars = {
                    edge.from_node_id
                    for edge in self.graph_ops.graph.find_edges(
                        to_node_id=later_scene.id, edge_type="APPEARS_IN"
                    )
                }

                # If significant character overlap, might have dependency
                if len(scene_chars & later_chars) >= 2:
                    dependencies.append((scene.id, later_scene.id))
                    break  # Only one dependency per scene for now

        return dependencies
