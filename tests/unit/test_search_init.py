"""Unit tests for scriptrag.search module initialization.

Tests the search module's __init__.py file to ensure proper module
initialization, imports, and public interface exposure.
"""

import scriptrag.search
from scriptrag.search import SearchQuery, SearchResponse, SearchResult


class TestSearchModuleInit:
    """Test search module initialization and exports."""

    def test_module_imports_successfully(self):
        """Test that the search module can be imported without errors."""
        # This test covers the import statement in __init__.py line 3

        # Verify the module is properly imported
        assert scriptrag.search is not None
        assert hasattr(scriptrag.search, "__name__")
        assert scriptrag.search.__name__ == "scriptrag.search"

    def test_public_interface_exports(self):
        """Test that all items in __all__ are properly exported."""
        # This test covers the __all__ declaration in __init__.py line 5

        # Verify __all__ is defined and contains expected items
        assert hasattr(scriptrag.search, "__all__")
        expected_exports = ["SearchQuery", "SearchResponse", "SearchResult"]
        assert scriptrag.search.__all__ == expected_exports

    def test_search_query_available(self):
        """Test that SearchQuery is available from the module."""
        # Test direct import access

        # Verify it's the correct class from models
        from scriptrag.search.models import SearchQuery as ModelsSearchQuery

        assert SearchQuery is ModelsSearchQuery

        # Test module attribute access
        import scriptrag.search

        assert hasattr(scriptrag.search, "SearchQuery")
        assert scriptrag.search.SearchQuery is SearchQuery

    def test_search_response_available(self):
        """Test that SearchResponse is available from the module."""
        # Test direct import access

        # Verify it's the correct class from models
        from scriptrag.search.models import SearchResponse as ModelsSearchResponse

        assert SearchResponse is ModelsSearchResponse

        # Test module attribute access
        import scriptrag.search

        assert hasattr(scriptrag.search, "SearchResponse")
        assert scriptrag.search.SearchResponse is SearchResponse

    def test_search_result_available(self):
        """Test that SearchResult is available from the module."""
        # Test direct import access

        # Verify it's the correct class from models
        from scriptrag.search.models import SearchResult as ModelsSearchResult

        assert SearchResult is ModelsSearchResult

        # Test module attribute access
        import scriptrag.search

        assert hasattr(scriptrag.search, "SearchResult")
        assert scriptrag.search.SearchResult is SearchResult

    def test_all_exports_are_importable(self):
        """Test that all items in __all__ can be imported."""

        # Test each export individually
        for export_name in scriptrag.search.__all__:
            assert hasattr(scriptrag.search, export_name), (
                f"{export_name} not found in module"
            )

            # Verify the attribute is not None
            attr = getattr(scriptrag.search, export_name)
            assert attr is not None, f"{export_name} is None"

            # Verify it's a class (all our exports are classes)
            assert isinstance(attr, type), f"{export_name} is not a class"

    def test_module_docstring(self):
        """Test that the module has proper documentation."""

        assert hasattr(scriptrag.search, "__doc__")
        assert scriptrag.search.__doc__ is not None
        assert "ScriptRAG search functionality" in scriptrag.search.__doc__

    def test_import_star_functionality(self):
        """Test that 'from scriptrag.search import *' works correctly."""
        # Create a namespace to test star import
        namespace = {}

        # Execute star import
        exec("from scriptrag.search import *", namespace)  # noqa: S102

        # Verify all __all__ items are in namespace
        expected_exports = ["SearchQuery", "SearchResponse", "SearchResult"]
        for export_name in expected_exports:
            assert export_name in namespace, (
                f"{export_name} not imported with star import"
            )
            assert namespace[export_name] is not None

    def test_no_private_exports(self):
        """Test that no private attributes are accidentally exported."""

        # Check that __all__ doesn't contain private attributes
        for export_name in scriptrag.search.__all__:
            assert not export_name.startswith("_"), (
                f"Private attribute {export_name} in __all__"
            )

    def test_models_consistency(self):
        """Test that exported classes match those in the models module."""
        # Import from main module

        # Import from models module
        from scriptrag.search.models import SearchQuery as ModelsSearchQuery
        from scriptrag.search.models import SearchResponse as ModelsSearchResponse
        from scriptrag.search.models import SearchResult as ModelsSearchResult

        # Verify they're the same objects
        assert SearchQuery is ModelsSearchQuery
        assert SearchResponse is ModelsSearchResponse
        assert SearchResult is ModelsSearchResult

    def test_class_instantiation(self):
        """Test that exported classes can be instantiated."""

        # Test SearchQuery instantiation
        query = SearchQuery(raw_query="test query")
        assert query.raw_query == "test query"

        # Test SearchResult instantiation
        result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. TEST - DAY",
            scene_location="Test Location",
            scene_time="DAY",
            scene_content="Test content",
        )
        assert result.script_title == "Test Script"

        # Test SearchResponse instantiation
        response = SearchResponse(
            query=query, results=[result], total_count=1, has_more=False
        )
        assert response.total_count == 1
        assert len(response.results) == 1

    def test_module_path_consistency(self):
        """Test that the module path is consistent."""
        import scriptrag.search

        # Verify module path
        assert scriptrag.search.__name__ == "scriptrag.search"

        # Verify package structure
        assert scriptrag.search.__package__ == "scriptrag.search"

        # Verify it's part of the scriptrag package
        import scriptrag

        assert hasattr(scriptrag, "search")
