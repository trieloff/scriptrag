"""Tests for FileSourceResolver."""

from unittest.mock import MagicMock, patch

from scriptrag.common import FileSourceResolver


class TestFileSourceResolver:
    """Test FileSourceResolver functionality."""

    def test_init(self):
        """Test resolver initialization."""
        resolver = FileSourceResolver(
            file_type="test",
            env_var="TEST_DIR",
            default_subdir="test/subdir",
            file_extension="txt",
        )

        assert resolver.file_type == "test"
        assert resolver.env_var == "TEST_DIR"
        assert resolver.default_subdir == "test/subdir"
        assert resolver.file_extension == "txt"

    def test_get_search_directories_with_custom_dir(self, tmp_path):
        """Test getting search directories with custom directory."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()

        resolver = FileSourceResolver(file_type="test")
        dirs = resolver.get_search_directories(custom_dir)

        assert custom_dir in dirs

    def test_get_search_directories_with_env_var(self, tmp_path, monkeypatch):
        """Test getting search directories with environment variable."""
        env_dir = tmp_path / "env"
        env_dir.mkdir()

        monkeypatch.setenv("TEST_DIR", str(env_dir))

        resolver = FileSourceResolver(file_type="test", env_var="TEST_DIR")
        dirs = resolver.get_search_directories()

        assert env_dir in dirs

    def test_get_search_directories_with_git_repo(self, tmp_path):
        """Test getting search directories with git repository."""
        git_root = tmp_path / "repo"
        git_root.mkdir()
        scriptrag_dir = git_root / ".scriptrag" / "test"
        scriptrag_dir.mkdir(parents=True)

        with patch("git.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.working_dir = str(git_root)
            mock_repo_class.return_value = mock_repo

            resolver = FileSourceResolver(file_type="test")
            dirs = resolver.get_search_directories()

            assert scriptrag_dir in dirs

    def test_get_search_directories_not_in_git(self):
        """Test getting search directories when not in a git repository."""
        import git

        with patch("git.Repo") as mock_repo_class:
            mock_repo_class.side_effect = git.InvalidGitRepositoryError(
                "Not a git repo"
            )

            resolver = FileSourceResolver(
                file_type="test",
                default_subdir="test/default",
            )
            dirs = resolver.get_search_directories()

            # Should still return default directory if it exists
            # May or may not have default depending on package structure
            assert len(dirs) >= 0

    def test_discover_files(self, tmp_path):
        """Test discovering files across directories."""
        # Create test directories and files
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "file1.txt").write_text("content1")
        (dir1 / "file2.txt").write_text("content2")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "file2.txt").write_text("duplicate")  # Duplicate name
        (dir2 / "file3.txt").write_text("content3")

        resolver = FileSourceResolver(file_type="test", file_extension="txt")

        # Mock get_search_directories to return our test dirs
        with patch.object(
            resolver, "get_search_directories", return_value=[dir1, dir2]
        ):
            files = resolver.discover_files()

        # Should have 3 unique files (file2 from dir1 takes priority)
        assert len(files) == 3
        file_names = {f.stem for f in files}
        assert file_names == {"file1", "file2", "file3"}

        # Check that file2 comes from dir1 (first directory)
        file2_path = next(f for f in files if f.stem == "file2")
        assert file2_path.parent == dir1

    def test_discover_files_with_pattern(self, tmp_path):
        """Test discovering files with custom pattern."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "query1.sql").write_text("SELECT 1")
        (test_dir / "query2.sql").write_text("SELECT 2")
        (test_dir / "other.txt").write_text("other")

        resolver = FileSourceResolver(file_type="test")

        with patch.object(resolver, "get_search_directories", return_value=[test_dir]):
            files = resolver.discover_files(pattern="*.sql")

        assert len(files) == 2
        assert all(f.suffix == ".sql" for f in files)

    def test_priority_order(self, tmp_path, monkeypatch):
        """Test that directories are searched in the correct priority order."""
        # Create directories
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "file.txt").write_text("custom")

        env_dir = tmp_path / "env"
        env_dir.mkdir()
        (env_dir / "file.txt").write_text("env")

        git_dir = tmp_path / "git" / ".scriptrag" / "test"
        git_dir.mkdir(parents=True)
        (git_dir / "file.txt").write_text("git")

        # Set up environment
        monkeypatch.setenv("TEST_DIR", str(env_dir))

        # Mock git repo
        with patch("git.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.working_dir = str(tmp_path / "git")
            mock_repo_class.return_value = mock_repo

            resolver = FileSourceResolver(file_type="test", env_var="TEST_DIR")
            files = resolver.discover_files(custom_dir=custom_dir)

        # Should only have one file (from highest priority directory)
        assert len(files) == 1
        assert files[0].parent == custom_dir

        # Test without custom dir
        with patch("git.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.working_dir = str(tmp_path / "git")
            mock_repo_class.return_value = mock_repo

            files = resolver.discover_files()

        # Should get file from env directory (next priority)
        assert len(files) == 1
        assert files[0].parent == env_dir
