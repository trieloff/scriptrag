"""Scene output formatter for CLI."""

import json
from typing import Any

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from scriptrag.api.scene_models import (
    BibleReadResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.cli.formatters.base import OutputFormat, OutputFormatter
from scriptrag.parser import Scene as SceneData


class SceneFormatter(OutputFormatter[Any]):
    """Formatter for scene-related output."""

    def format(self, data: Any, format_type: OutputFormat = OutputFormat.TEXT) -> str:
        """Format scene data for output.

        Args:
            data: Scene data to format
            format_type: Output format type

        Returns:
            Formatted string
        """
        if isinstance(data, ReadSceneResult):
            return self._format_read_result(data, format_type)
        if isinstance(data, UpdateSceneResult):
            return self._format_update_result(data, format_type)
        if isinstance(data, BibleReadResult):
            return self._format_bible_result(data, format_type)
        if isinstance(data, SceneData):
            return self._format_scene(data, format_type)
        return str(data)

    def _format_read_result(
        self, result: ReadSceneResult, format_type: OutputFormat
    ) -> str:
        """Format scene read result."""
        if not result.success:
            return self.format_error(result.error or "Unknown error")

        if format_type == OutputFormat.JSON:
            output = {
                "success": True,
                "scene_number": result.scene.number if result.scene else None,
                "heading": result.scene.heading if result.scene else None,
                "content": result.scene.content if result.scene else None,
                "last_read": result.last_read.isoformat() if result.last_read else None,
            }
            return json.dumps(output)

        # Text format - return formatted panel
        if result.scene:
            return self._create_scene_panel(result.scene)
        return ""

    def _format_update_result(
        self, result: UpdateSceneResult, format_type: OutputFormat
    ) -> str:
        """Format scene update result."""
        if not result.success:
            return self.format_error(result.error or "Unknown error")

        if format_type == OutputFormat.JSON:
            output = {
                "success": True,
                "updated_scene": (
                    {
                        "number": result.updated_scene.number,
                        "heading": result.updated_scene.heading,
                    }
                    if result.updated_scene
                    else None
                ),
                "validation_errors": result.validation_errors,
            }
            return json.dumps(output)

        # Text format
        if result.validation_errors:
            return (
                f"[yellow]Warning: Validation errors: "
                f"{', '.join(result.validation_errors)}[/yellow]\n"
                f"[green]Scene updated successfully[/green]"
            )
        return "[green]Scene updated successfully[/green]"

    def _format_bible_result(
        self, result: BibleReadResult, format_type: OutputFormat
    ) -> str:
        """Format bible read result."""
        if not result.success:
            return self.format_error(result.error or "Unknown error")

        if format_type == OutputFormat.JSON:
            if result.content:
                output = {"success": True, "content": result.content}
            else:
                output = {"success": True, "bible_files": result.bible_files}
            return json.dumps(output)

        # Text format
        if result.content:
            # Bible content as panel
            panel = Panel(
                Syntax(result.content, "markdown", theme="monokai"),
                title="Bible Content",
            )
            return str(panel)
        # List of bible files
        lines = ["[green]Available bible files:[/green]", ""]
        for file_info in result.bible_files:
            size_kb = file_info["size"] / 1024
            lines.append(
                f"  • [cyan]{file_info['name']}[/cyan] "
                f"({file_info['path']}) - {size_kb:.1f} KB"
            )
        return "\n".join(lines)

    def _format_scene(self, scene: SceneData, format_type: OutputFormat) -> str:
        """Format a single scene."""
        if format_type == OutputFormat.JSON:
            output = {
                "number": scene.number,
                "heading": scene.heading,
                "content": scene.content,
            }
            return json.dumps(output)

        return self._create_scene_panel(scene)

    def _create_scene_panel(self, scene: SceneData) -> str:
        """Create a rich panel for scene display."""
        panel = Panel(
            Syntax(scene.content, "text", theme="monokai"),
            title=f"Scene {scene.number}",
            subtitle=scene.heading,
        )
        # Convert panel to string for return
        from io import StringIO

        from rich.console import Console

        string_io = StringIO()
        temp_console = Console(file=string_io, force_terminal=True)
        temp_console.print(panel)
        return string_io.getvalue()

    def format_scene_list(
        self, scenes: list[SceneData], format_type: OutputFormat = OutputFormat.TABLE
    ) -> str:
        """Format a list of scenes.

        Args:
            scenes: List of scenes to format
            format_type: Output format type

        Returns:
            Formatted string
        """
        if format_type == OutputFormat.JSON:
            output = [
                {"number": s.number, "heading": s.heading, "content": s.content[:100]}
                for s in scenes
            ]
            return json.dumps(output)

        if format_type == OutputFormat.TABLE:
            table = Table(title="Scenes")
            table.add_column("Number", style="cyan", no_wrap=True)
            table.add_column("Heading", style="magenta")
            table.add_column("Preview", style="dim")

            for scene in scenes:
                preview = (
                    scene.content[:50] + "..."
                    if len(scene.content) > 50
                    else scene.content
                )
                table.add_row(str(scene.number), scene.heading, preview)

            # Convert table to string
            from io import StringIO

            from rich.console import Console

            string_io = StringIO()
            temp_console = Console(file=string_io, force_terminal=True)
            temp_console.print(table)
            return string_io.getvalue()

        # Default text format
        lines = []
        for scene in scenes:
            lines.append(f"Scene {scene.number}: {scene.heading}")
            lines.append(f"  {scene.content[:100]}...")
            lines.append("")
        return "\n".join(lines)
