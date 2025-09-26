"""Common file source resolution for ScriptRAG components."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from scriptrag.config import get_logger

logger = get_logger(__name__)


class FileSourceResolver:
    """Resolves file sources from multiple locations for ScriptRAG components.

    This class provides a common pattern for finding files in:
    1. The default application source directory (built-ins, cannot be overridden)
    2. The .scriptrag directory in the git repository root (if in a git repo)
    3. A user-specified directory (via environment variable or parameter)

    Built-in files have the highest priority and cannot be overridden by user
    files for security reasons. User files can only add new items.
    """

    def __init__(
        self,
        file_type: str,
        env_var: str | None = None,
        default_subdir: str | None = None,
        file_extension: str = "*",
    ) -> None:
        """Initialize the file source resolver.

        Args:
            file_type: Type of files being resolved (e.g., "query", "agent", "analyzer")
            env_var: Optional environment variable name for custom directory
            default_subdir: Subdirectory under src/scriptrag for default location
            file_extension: File extension pattern to search for (default "*")
        """
        self.file_type = file_type
        self.env_var = env_var
        self.default_subdir = default_subdir
        self.file_extension = file_extension
        self._git_root: Path | None = None
        self._cache_git_root_checked = False

    def get_search_directories(self, custom_dir: Path | None = None) -> list[Path]:
        """Get all directories to search for files.

        Priority order (first in list = highest priority, cannot be overridden):
        1. Default application source directory (built-ins, highest priority)
        2. .scriptrag/<file_type> in git repository root (if in git repo)
        3. Environment variable directory (if set and exists)
        4. Custom directory (if provided, lowest priority for discovery)

        Args:
            custom_dir: Optional custom directory to search

        Returns:
            List of existing directories to search, in priority order
        """
        directories: list[Path] = []

        # 1. Default application source directory (highest priority - built-ins)
        if self.default_subdir:
            default_path = self._get_default_path()
            if default_path.exists() and default_path.is_dir():
                directories.append(default_path)
                logger.debug(
                    f"Using default {self.file_type} directory: {default_path}"
                )

        # 2. .scriptrag directory in git repository root
        git_root = self._find_git_root()
        if git_root:
            scriptrag_dir = git_root / ".scriptrag" / self.file_type
            if (
                scriptrag_dir.exists()
                and scriptrag_dir.is_dir()
                and not any(scriptrag_dir == d for d in directories)
            ):
                directories.append(scriptrag_dir)
                logger.debug(
                    f"Using {self.file_type} directory from git repo: {scriptrag_dir}"
                )

        # 3. Environment variable directory
        if self.env_var:
            env_dir = os.environ.get(self.env_var)
            if env_dir:
                path = Path(env_dir)
                if path.exists() and path.is_dir():
                    if not any(path == d for d in directories):
                        directories.append(path)
                        logger.debug(
                            f"Using {self.file_type} directory from "
                            f"{self.env_var}: {path}"
                        )
                else:
                    logger.warning(
                        f"{self.env_var} set but path doesn't exist: {env_dir}"
                    )

        # 4. Custom directory (lowest priority for discovery)
        if custom_dir:
            if custom_dir.exists() and custom_dir.is_dir():
                if not any(custom_dir == d for d in directories):
                    directories.append(custom_dir)
                    logger.debug(
                        f"Using custom {self.file_type} directory: {custom_dir}"
                    )
            else:
                logger.warning(
                    f"Custom {self.file_type} directory doesn't exist: {custom_dir}"
                )

        if not directories:
            logger.warning(f"No {self.file_type} directories found")

        return directories

    def discover_files(
        self, custom_dir: Path | None = None, pattern: str | None = None
    ) -> list[Path]:
        """Discover all files across search directories.

        Built-in files from the default application directory have the highest
        priority and cannot be overridden by user files. User files with the
        same name as built-ins will be skipped with a warning.

        Args:
            custom_dir: Optional custom directory to search
            pattern: Optional glob pattern (defaults to file_extension)

        Returns:
            List of discovered file paths (deduplicated by name)
        """
        if pattern is None:
            pattern = f"*.{self.file_extension}" if self.file_extension != "*" else "*"

        directories = self.get_search_directories(custom_dir)
        discovered_files: dict[str, Path] = {}  # name -> path mapping
        builtin_names: set[str] = set()  # Track built-in file names

        # Check if the first directory is the default (built-in) directory
        default_path = self._get_default_path() if self.default_subdir else None

        for directory in directories:
            is_builtin_dir = default_path and directory == default_path

            try:
                for file_path in directory.glob(pattern):
                    if file_path.is_file():
                        file_name = file_path.stem

                        # Track built-in names
                        if is_builtin_dir:
                            builtin_names.add(file_name)

                        # First directory in list has priority
                        if file_name not in discovered_files:
                            discovered_files[file_name] = file_path
                            logger.debug(
                                f"Discovered {self.file_type} '{file_name}' "
                                f"from {directory}"
                            )
                        else:
                            # Warn if user file tries to override built-in
                            if file_name in builtin_names and not is_builtin_dir:
                                logger.warning(
                                    f"User {self.file_type} '{file_name}' from "
                                    f"{directory} cannot override built-in. Skipping."
                                )
                            else:
                                logger.debug(
                                    f"Skipping duplicate {self.file_type} "
                                    f"'{file_name}' from {directory}"
                                )
            except Exception as e:
                logger.error(f"Error scanning directory {directory}: {e}")

        logger.debug(
            f"Discovered {len(discovered_files)} {self.file_type} files across "
            f"{len(directories)} directories"
        )

        return list(discovered_files.values())

    def _find_git_root(self) -> Path | None:
        """Find the git repository root if we're in a git repo.

        Returns:
            Path to git repository root, or None if not in a git repo
        """
        # Cache the result to avoid repeated git operations
        if self._cache_git_root_checked:
            return self._git_root

        self._cache_git_root_checked = True

        try:
            import git

            # Try to find git repo from current directory
            repo = git.Repo(".", search_parent_directories=True)
            # Handle bare repositories or edge cases where working_dir is None
            if repo.working_dir is None:
                logger.debug("Git repository has no working directory (bare repo?)")
                return None
            self._git_root = Path(repo.working_dir)
            logger.debug(f"Found git repository root: {self._git_root}")
            return self._git_root
        except ImportError:
            logger.debug("GitPython not available, skipping git repository search")
            return None
        except git.InvalidGitRepositoryError:
            logger.debug("Not in a git repository")
            return None
        except Exception as e:
            logger.warning(f"Error finding git repository: {e}")
            return None

    def _get_default_path(self) -> Path:
        """Get the default path for files based on the package location.

        Returns:
            Path to default directory
        """
        from scriptrag import __file__ as pkg_file

        pkg_dir = Path(pkg_file).parent
        return pkg_dir / self.default_subdir if self.default_subdir else pkg_dir
