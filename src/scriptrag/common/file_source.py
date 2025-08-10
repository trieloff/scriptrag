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
    1. A user-specified directory (via environment variable or parameter)
    2. The .scriptrag directory in the git repository root (if in a git repo)
    3. The default application source directory
    """

    def __init__(
        self,
        file_type: str,
        env_var: str | None = None,
        default_subdir: str | None = None,
        file_extension: str = "*",
    ):
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

        Priority order:
        1. Custom directory (if provided)
        2. Environment variable directory (if set and exists)
        3. .scriptrag/<file_type> in git repository root (if in git repo)
        4. Default application source directory

        Args:
            custom_dir: Optional custom directory to search first

        Returns:
            List of existing directories to search, in priority order
        """
        directories: list[Path] = []

        # 1. Custom directory (highest priority)
        if custom_dir:
            if custom_dir.exists() and custom_dir.is_dir():
                directories.append(custom_dir)
                logger.debug(f"Using custom {self.file_type} directory: {custom_dir}")
            else:
                logger.warning(
                    f"Custom {self.file_type} directory doesn't exist: {custom_dir}"
                )

        # 2. Environment variable directory
        if self.env_var:
            env_dir = os.environ.get(self.env_var)
            if env_dir:
                path = Path(env_dir)
                if path.exists() and path.is_dir():
                    if not custom_dir or path != custom_dir:
                        directories.append(path)
                        logger.debug(
                            f"Using {self.file_type} directory from "
                            f"{self.env_var}: {path}"
                        )
                else:
                    logger.warning(
                        f"{self.env_var} set but path doesn't exist: {env_dir}"
                    )

        # 3. .scriptrag directory in git repository root
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

        # 4. Default application source directory
        if self.default_subdir:
            default_path = self._get_default_path()
            if (
                default_path.exists()
                and default_path.is_dir()
                and not any(default_path == d for d in directories)
            ):
                directories.append(default_path)
                logger.debug(
                    f"Using default {self.file_type} directory: {default_path}"
                )

        if not directories:
            logger.warning(f"No {self.file_type} directories found")

        return directories

    def discover_files(
        self, custom_dir: Path | None = None, pattern: str | None = None
    ) -> list[Path]:
        """Discover all files across search directories.

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

        for directory in directories:
            try:
                for file_path in directory.glob(pattern):
                    if file_path.is_file():
                        file_name = file_path.stem
                        # First directory in list has priority
                        if file_name not in discovered_files:
                            discovered_files[file_name] = file_path
                            logger.debug(
                                f"Discovered {self.file_type} '{file_name}' "
                                f"from {directory}"
                            )
                        else:
                            logger.debug(
                                f"Skipping duplicate {self.file_type} "
                                f"'{file_name}' from {directory}"
                            )
            except Exception as e:
                logger.error(f"Error scanning directory {directory}: {e}")

        logger.info(
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
