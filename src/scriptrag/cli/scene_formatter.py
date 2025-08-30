"""Scene output formatting utilities for CLI display."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.config import get_logger
from scriptrag.parser import Scene

logger = get_logger(__name__)


class SceneFormatter:
    """Formats scene data for various output types."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the formatter.

        Args:
            console: Rich console for output (creates one if not provided)
        """
        self.console = console or Console()

    def format_scene_display(
        self,
        scene: Scene,
        scene_id: SceneIdentifier,
        last_read: datetime | None = None,
        json_output: bool = False,
    ) -> None:
        """Format and display a scene.

        Args:
            scene: Scene object to display
            scene_id: Scene identifier
            last_read: Optional last read timestamp
            json_output: If True, output as JSON
        """
        if json_output:
            self._output_scene_json(scene, scene_id, last_read)
        else:
            self._output_scene_rich(scene, scene_id, last_read)

    def format_bible_display(
        self,
        content: str | None,
        bible_files: list[dict[str, Any]],
        project: str,
        bible_name: str | None = None,
        json_output: bool = False,
    ) -> None:
        """Format and display bible content or file list.

        Args:
            content: Bible content if reading specific file
            bible_files: List of available bible files
            project: Project name
            bible_name: Name of specific bible file
            json_output: If True, output as JSON
        """
        if json_output:
            self._output_bible_json(content, bible_files)
        else:
            self._output_bible_rich(content, bible_files, project, bible_name)

    def format_operation_result(
        self,
        operation: str,
        success: bool,
        scene_id: SceneIdentifier,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Format operation result message.

        Args:
            operation: Operation name (add, update, delete)
            success: Whether operation succeeded
            scene_id: Scene identifier
            message: Optional message
            details: Optional additional details
        """
        if success:
            # Handle operation name formatting correctly
            if operation == "add":
                operation_text = "added"
            elif operation == "update":
                operation_text = "updated"
            elif operation == "delete":
                operation_text = "deleted"
            else:
                operation_text = f"{operation}d"  # fallback

            self.console.print(
                f"[green]✓[/green] Scene {operation_text}: {scene_id.key}"
            )
            if details:
                self._display_operation_details(details)
        else:
            self.console.print(
                f"[red]✗[/red] Failed to {operation} scene: {scene_id.key}"
            )
            if message:
                self.console.print(f"[red]Error: {message}[/red]")

    def format_validation_errors(
        self,
        errors: list[str],
        warnings: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Format and display validation errors and warnings.

        Args:
            errors: List of validation errors
            warnings: Optional list of warnings
            suggestions: Optional list of suggestions
        """
        if errors:
            self.console.print("[red]Validation errors:[/red]")
            for error in errors:
                self.console.print(f"  • {error}")

        if warnings:
            self.console.print("[yellow]Warnings:[/yellow]")
            for warning in warnings:
                self.console.print(f"  • {warning}")

        if suggestions:
            self.console.print("[cyan]Suggestions:[/cyan]")
            for suggestion in suggestions:
                self.console.print(f"  • {suggestion}")

    def format_scene_list(
        self,
        scenes: list[dict[str, Any]],
        project: str,
        json_output: bool = False,
    ) -> None:
        """Format and display a list of scenes.

        Args:
            scenes: List of scene data
            project: Project name
            json_output: If True, output as JSON
        """
        if json_output:
            self.console.print_json(data={"project": project, "scenes": scenes})
        else:
            self._display_scene_table(scenes, project)

    def _output_scene_json(
        self,
        scene: Scene,
        scene_id: SceneIdentifier,
        last_read: datetime | None,
    ) -> None:
        """Output scene as JSON.

        Args:
            scene: Scene object
            scene_id: Scene identifier
            last_read: Optional last read timestamp
        """
        output = {
            "success": True,
            "scene_number": scene.number,
            "heading": scene.heading,
            "content": scene.content,
            "location": scene.location,
            "time_of_day": scene.time_of_day,
            "scene_id": scene_id.key,
            "last_read": last_read.isoformat() if last_read else None,
        }
        self.console.print_json(data=output)

    def _output_scene_rich(
        self,
        scene: Scene,
        scene_id: SceneIdentifier,
        last_read: datetime | None,
    ) -> None:
        """Output scene with rich formatting.

        Args:
            scene: Scene object
            scene_id: Scene identifier
            last_read: Optional last read timestamp
        """
        # Display scene content in a panel
        self.console.print(
            Panel(
                Syntax(scene.content, "text", theme="monokai"),
                title=f"Scene {scene_id.key}",
                subtitle=scene.heading,
            )
        )

        # Display metadata
        if scene.location or scene.time_of_day:
            metadata = []
            if scene.location:
                metadata.append(f"[cyan]Location:[/cyan] {scene.location}")
            if scene.time_of_day:
                metadata.append(f"[cyan]Time:[/cyan] {scene.time_of_day}")
            self.console.print("\n".join(metadata))

        # Display timestamp
        if last_read:
            self.console.print(f"\n[green]Last read:[/green] {last_read.isoformat()}")

    def _output_bible_json(
        self,
        content: str | None,
        bible_files: list[dict[str, Any]],
    ) -> None:
        """Output bible data as JSON.

        Args:
            content: Bible content if available
            bible_files: List of bible files
        """
        if content:
            output = {"success": True, "content": content}
        else:
            output = {"success": True, "bible_files": bible_files}
        self.console.print_json(data=output)

    def _output_bible_rich(
        self,
        content: str | None,
        bible_files: list[dict[str, Any]],
        project: str,
        bible_name: str | None,
    ) -> None:
        """Output bible data with rich formatting.

        Args:
            content: Bible content if available
            bible_files: List of bible files
            project: Project name
            bible_name: Name of specific bible file
        """
        if content:
            # Display bible content
            self.console.print(
                Panel(
                    Syntax(content, "markdown", theme="monokai"),
                    title=f"Bible: {bible_name or 'Content'}",
                    subtitle=f"Project: {project}",
                )
            )
        else:
            # Display list of available bible files
            self.console.print(
                f"\n[green]Available bible files for project '{project}':[/green]\n"
            )
            for bible_file in bible_files:
                size_kb = bible_file["size"] / 1024
                self.console.print(
                    f"  • [cyan]{bible_file['name']}[/cyan] "
                    f"({bible_file['path']}) - {size_kb:.1f} KB"
                )
            self.console.print(
                "\n[dim]Use --bible-name <filename> to read a specific bible file[/dim]"
            )

    def _display_operation_details(self, details: dict[str, Any]) -> None:
        """Display operation details.

        Args:
            details: Operation details dictionary
        """
        if renumbered := details.get("renumbered_scenes"):
            self.console.print(
                f"[yellow]Renumbered scenes:[/yellow] {', '.join(map(str, renumbered))}"
            )

        if validation_errors := details.get("validation_errors"):
            self.format_validation_errors(validation_errors)

    def _display_scene_table(self, scenes: list[dict[str, Any]], project: str) -> None:
        """Display scenes in a table format.

        Args:
            scenes: List of scene data
            project: Project name
        """
        table = Table(title=f"Scenes for {project}")
        table.add_column("Scene #", style="cyan", no_wrap=True)
        table.add_column("Heading", style="white")
        table.add_column("Location", style="yellow")
        table.add_column("Time", style="magenta")

        for scene in scenes:
            table.add_row(
                str(scene.get("number", "")),
                scene.get("heading", ""),
                scene.get("location", ""),
                scene.get("time_of_day", ""),
            )

        self.console.print(table)

    def format_conflict_error(
        self,
        scene_id: SceneIdentifier,
        last_modified: datetime | None,
        last_read: datetime | None,
    ) -> None:
        """Format conflict error message.

        Args:
            scene_id: Scene identifier
            last_modified: When scene was last modified
            last_read: When scene was last read
        """
        self.console.print(f"[red]Conflict detected for scene {scene_id.key}[/red]")
        if last_modified and last_read:
            self.console.print(f"  Scene modified at: {last_modified.isoformat()}")
            self.console.print(f"  Your last read: {last_read.isoformat()}")
        self.console.print("[yellow]Please re-read the scene and try again.[/yellow]")
