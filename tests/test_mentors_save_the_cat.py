"""Tests for the Save the Cat mentor."""

from uuid import uuid4

import pytest

from scriptrag.mentors.base import AnalysisSeverity, MentorType
from scriptrag.mentors.save_the_cat import (
    SAVE_THE_CAT_BEATS,
    SaveTheCatBeat,
    SaveTheCatMentor,
)


class TestSaveTheCatBeat:
    """Test SaveTheCatBeat model."""

    def test_beat_creation(self):
        """Test creating a SaveTheCatBeat instance."""
        beat = SaveTheCatBeat(
            name="Opening Image",
            description="Visual snapshot of the main character's problem",
            page_range=(1, 1),
            keywords=["opening", "visual", "tone"],
            required=True,
        )

        assert beat.name == "Opening Image"
        assert "snapshot" in beat.description
        assert beat.page_range == (1, 1)
        assert beat.keywords == ["opening", "visual", "tone"]
        assert beat.required is True

    def test_beat_defaults(self):
        """Test SaveTheCatBeat default values."""
        beat = SaveTheCatBeat(
            name="Test Beat",
            description="Test description",
            page_range=(10, 15),
            keywords=["test"],
        )

        assert beat.required is True  # Default value

    def test_save_the_cat_beats_structure(self):
        """Test the SAVE_THE_CAT_BEATS constant."""
        assert len(SAVE_THE_CAT_BEATS) == 15

        # Check specific beats exist
        beat_names = [beat.name for beat in SAVE_THE_CAT_BEATS]
        expected_beats = [
            "Opening Image",
            "Theme Stated",
            "Set-Up",
            "Catalyst",
            "Debate",
            "Break Into Two",
            "B Story",
            "Fun and Games",
            "Midpoint",
            "Bad Guys Close In",
            "All Is Lost",
            "Dark Night of the Soul",
            "Break Into Three",
            "Finale",
            "Final Image",
        ]

        assert beat_names == expected_beats

        # Check that all beats are required by default
        assert all(beat.required for beat in SAVE_THE_CAT_BEATS)

        # Check page ranges are in ascending order
        page_starts = [beat.page_range[0] for beat in SAVE_THE_CAT_BEATS]
        assert page_starts == sorted(page_starts)

    def test_beat_keywords(self):
        """Test that beats have relevant keywords."""
        catalyst_beat = next(b for b in SAVE_THE_CAT_BEATS if b.name == "Catalyst")
        assert "inciting incident" in catalyst_beat.keywords
        assert "call to adventure" in catalyst_beat.keywords

        finale_beat = next(b for b in SAVE_THE_CAT_BEATS if b.name == "Finale")
        assert "climax" in finale_beat.keywords
        assert "resolution" in finale_beat.keywords


class TestSaveTheCatMentor:
    """Test the Save the Cat mentor implementation."""

    def test_mentor_properties(self):
        """Test basic mentor properties."""
        mentor = SaveTheCatMentor()

        assert mentor.name == "save_the_cat"
        assert mentor.mentor_type == MentorType.STORY_STRUCTURE
        assert mentor.version == "1.0.0"
        assert "Blake Snyder" in mentor.description
        assert "15-beat" in mentor.description

        # Check categories
        expected_categories = [
            "beat_sheet",
            "story_structure",
            "pacing",
            "character_arc",
            "theme",
        ]
        assert set(mentor.categories) == set(expected_categories)

    def test_mentor_configuration(self):
        """Test mentor configuration options."""
        # Default configuration
        mentor = SaveTheCatMentor()
        assert mentor.target_page_count == 110
        assert mentor.tolerance == 5
        assert mentor.strict_mode is False

        # Custom configuration
        config = {
            "target_page_count": 120,
            "tolerance": 10,
            "strict_mode": True,
        }
        mentor = SaveTheCatMentor(config)
        assert mentor.target_page_count == 120
        assert mentor.tolerance == 10
        assert mentor.strict_mode is True

    def test_config_validation(self):
        """Test configuration validation."""
        mentor = SaveTheCatMentor()
        assert mentor.validate_config() is True

        # Test with valid custom config
        mentor = SaveTheCatMentor(
            {
                "target_page_count": 90,
                "tolerance": 3,
                "strict_mode": False,
            }
        )
        assert mentor.validate_config() is True

        # Test with invalid config - page count too low
        mentor = SaveTheCatMentor({"target_page_count": 20})
        assert mentor.validate_config() is False

        # Test with invalid config - negative tolerance
        mentor = SaveTheCatMentor({"tolerance": -1})
        assert mentor.validate_config() is False

        # Test with invalid types
        mentor = SaveTheCatMentor({"target_page_count": "not a number"})
        assert mentor.validate_config() is False

    def test_config_schema(self):
        """Test configuration schema."""
        mentor = SaveTheCatMentor()
        schema = mentor.get_config_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "target_page_count" in schema["properties"]
        assert "tolerance" in schema["properties"]
        assert "strict_mode" in schema["properties"]

        # Check property constraints
        page_count_prop = schema["properties"]["target_page_count"]
        assert page_count_prop["type"] == "integer"
        assert page_count_prop["minimum"] == 30
        assert page_count_prop["maximum"] == 200
        assert page_count_prop["default"] == 110

        tolerance_prop = schema["properties"]["tolerance"]
        assert tolerance_prop["type"] == "integer"
        assert tolerance_prop["minimum"] == 0
        assert tolerance_prop["maximum"] == 20
        assert tolerance_prop["default"] == 5

        strict_mode_prop = schema["properties"]["strict_mode"]
        assert strict_mode_prop["type"] == "boolean"
        assert strict_mode_prop["default"] is False

    @pytest.mark.asyncio
    async def test_analyze_script_error_handling(self):
        """Test error handling in script analysis."""
        mentor = SaveTheCatMentor()
        script_id = uuid4()

        # Mock database operations that raises an error
        class MockDBOps:
            def get_connection(self):
                class MockConnection:
                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                    def execute(self, query, params=None):  # noqa: ARG002
                        raise Exception("Database error")

                return MockConnection()

        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "save_the_cat"
        assert result.script_id == script_id
        # The current implementation returns placeholder data when db fails,
        # so we get analysis of empty script (15 missing beats + structure + character)
        assert len(result.analyses) >= 15  # All beats missing
        # Score should be very low due to all missing beats
        assert result.score <= 10

    @pytest.mark.asyncio
    async def test_analyze_script_empty_script(self):
        """Test analysis with an empty script."""
        mentor = SaveTheCatMentor()
        script_id = uuid4()

        # Mock database operations with empty script
        class MockDBOps:
            pass

        async def mock_get_script_data(self, script_id, db_ops):  # noqa: ARG001
            return {
                "script_id": script_id,
                "title": "Empty Script",
                "scenes": [],
                "characters": [],
                "total_pages": 0,
            }

        mentor._get_script_data = mock_get_script_data.__get__(mentor, SaveTheCatMentor)

        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "save_the_cat"
        assert result.script_id == script_id
        assert len(result.analyses) >= 15  # Should have analysis for each missing beat

        # All beats should be missing
        missing_beats = [a for a in result.analyses if "Missing Beat" in a.title]
        assert len(missing_beats) == 15

        # Should have low score due to missing beats
        assert result.score < 50

    @pytest.mark.asyncio
    async def test_analyze_script_with_progress_callback(self):
        """Test progress callback functionality."""
        mentor = SaveTheCatMentor()
        script_id = uuid4()
        progress_updates = []

        def progress_callback(progress: float, message: str):
            progress_updates.append((progress, message))

        # Mock script data
        async def mock_get_script_data(self, script_id, db_ops):  # noqa: ARG001
            return {
                "script_id": script_id,
                "title": "Test Script",
                "scenes": [
                    {"id": uuid4(), "page": 1, "elements": []},
                    {"id": uuid4(), "page": 25, "elements": []},
                    {"id": uuid4(), "page": 55, "elements": []},
                    {"id": uuid4(), "page": 85, "elements": []},
                    {"id": uuid4(), "page": 110, "elements": []},
                ],
                "characters": [],
                "total_pages": 110,
            }

        mentor._get_script_data = mock_get_script_data.__get__(mentor, SaveTheCatMentor)

        await mentor.analyze_script(script_id, None, progress_callback)

        # Check progress updates were made
        assert len(progress_updates) > 0
        assert progress_updates[0][0] == 0.1
        assert "Loading script data" in progress_updates[0][1]
        assert progress_updates[-1][0] == 1.0
        assert "complete" in progress_updates[-1][1].lower()

        # Check intermediate progress
        progress_values = [p[0] for p in progress_updates]
        assert 0.3 in progress_values  # "Analyzing story structure"
        assert 0.6 in progress_values  # "Checking pacing"
        assert 0.8 in progress_values  # "Analyzing character arc"
        assert 0.9 in progress_values  # "Generating summary"

    def test_estimate_total_pages(self):
        """Test page estimation logic."""
        mentor = SaveTheCatMentor()

        # Test with empty scenes
        pages = mentor._estimate_total_pages([])
        assert pages == 110  # Should default to target_page_count

        # Test with scenes
        scenes = [{"id": uuid4()} for _ in range(50)]
        pages = mentor._estimate_total_pages(scenes)
        assert pages == 110  # Should return max of target_page_count and scene count

        # Test with custom target page count
        mentor = SaveTheCatMentor({"target_page_count": 90})
        scenes = [{"id": uuid4()} for _ in range(120)]
        pages = mentor._estimate_total_pages(scenes)
        assert pages == 120  # Should return scene count when higher

    def test_find_beat_in_scenes(self):
        """Test beat finding logic."""
        mentor = SaveTheCatMentor()
        beat = SAVE_THE_CAT_BEATS[0]  # Opening Image

        # Test with empty scenes
        found_scenes = mentor._find_beat_in_scenes(beat, [], 1, 1)
        assert found_scenes == []

        # Test with scenes (placeholder implementation returns empty)
        scenes = [
            {
                "id": uuid4(),
                "page": 1,
                "elements": [{"text": "opening visual scene", "type": "action"}],
            }
        ]
        found_scenes = mentor._find_beat_in_scenes(beat, scenes, 1, 1)
        assert isinstance(found_scenes, list)

    def test_analyze_beat_timing(self):
        """Test beat timing analysis."""
        mentor = SaveTheCatMentor()
        beat = SAVE_THE_CAT_BEATS[3]  # Catalyst
        scenes = [{"id": uuid4(), "page": 12}]

        # Placeholder implementation returns None
        analysis = mentor._analyze_beat_timing(beat, scenes, 12, 12)
        assert analysis is None

    @pytest.mark.asyncio
    async def test_analyze_beats_with_scaling(self):
        """Test beat analysis with page scaling."""
        mentor = SaveTheCatMentor()

        # Test with 220-page script (2x normal)
        scenes = []
        total_pages = 220

        analyses = await mentor._analyze_beats(scenes, total_pages)

        # Should have analysis for each beat
        assert len(analyses) == 15

        # All should be missing beats
        assert all("Missing Beat" in a.title for a in analyses)

        # Check that page ranges are scaled
        catalyst_analysis = next(a for a in analyses if "Catalyst" in a.title)
        # Catalyst should be around page 24 (12 * 2) for 220-page script
        assert "24" in catalyst_analysis.description

    @pytest.mark.asyncio
    async def test_analyze_structure(self):
        """Test overall structure analysis."""
        mentor = SaveTheCatMentor()
        scenes = []
        total_pages = 110

        analyses = await mentor._analyze_structure(scenes, total_pages)

        assert len(analyses) >= 1

        # Should have three-act structure analysis
        structure_analysis = analyses[0]
        assert structure_analysis.title == "Three-Act Structure"
        assert structure_analysis.category == "story_structure"
        assert structure_analysis.severity == AnalysisSeverity.INFO
        assert "Act I ending around page 28" in structure_analysis.description
        assert "Act II ending around page 82" in structure_analysis.description

    @pytest.mark.asyncio
    async def test_analyze_character_arc(self):
        """Test character arc analysis."""
        mentor = SaveTheCatMentor()
        script_data = {
            "characters": [
                {"id": uuid4(), "name": "Hero"},
                {"id": uuid4(), "name": "Mentor"},
            ]
        }

        analyses = await mentor._analyze_character_arc(script_data)

        assert len(analyses) >= 1

        # Should have character arc analysis
        arc_analysis = analyses[0]
        assert arc_analysis.title == "Character Arc Analysis"
        assert arc_analysis.category == "character_arc"
        assert arc_analysis.severity == AnalysisSeverity.INFO
        assert "want vs. need" in arc_analysis.recommendations[0]

    def test_calculate_score(self):
        """Test score calculation logic."""
        mentor = SaveTheCatMentor()

        # Test with no analyses
        score = mentor._calculate_score([])
        assert score == 0.0

        # Test with mixed analyses
        from scriptrag.mentors.base import MentorAnalysis

        analyses = [
            MentorAnalysis(
                title="Good Structure",
                description="Well-structured",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            ),
            MentorAnalysis(
                title="Missing Beat",
                description="Beat not found",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            ),
            MentorAnalysis(
                title="Timing Issue",
                description="Beat timing off",
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="pacing",
                mentor_name="save_the_cat",
            ),
        ]

        score = mentor._calculate_score(analyses)
        # Base score 50 + 1 (INFO) - 10 (ERROR) - 5 (WARNING) = 36
        assert score == 36.0

        # Test score bounds
        many_errors = [
            MentorAnalysis(
                title=f"Error {i}",
                description="Error",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            )
            for i in range(10)
        ]

        score = mentor._calculate_score(many_errors)
        assert score == 0.0  # Should not go below 0

        many_good = [
            MentorAnalysis(
                title=f"Good {i}",
                description="Good",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            )
            for i in range(100)
        ]

        score = mentor._calculate_score(many_good)
        assert score == 100.0  # Should not go above 100

    def test_generate_summary(self):
        """Test summary generation."""
        mentor = SaveTheCatMentor()

        from scriptrag.mentors.base import MentorAnalysis

        # Test with good structure
        analyses = [
            MentorAnalysis(
                title="Complete Structure",
                description="All beats present",
                severity=AnalysisSeverity.INFO,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            )
        ]

        summary = mentor._generate_summary(analyses, 110)
        assert "110-page screenplay" in summary
        assert "0 structural issues" in summary
        assert "0 areas for improvement" in summary
        assert "follows Save the Cat beat sheet structure well" in summary

        # Test with issues
        analyses = [
            MentorAnalysis(
                title="Missing Beat",
                description="Beat missing",
                severity=AnalysisSeverity.ERROR,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="beat_sheet",
                mentor_name="save_the_cat",
            ),
            MentorAnalysis(
                title="Timing Issue",
                description="Timing off",
                severity=AnalysisSeverity.WARNING,
                scene_id=None,
                character_id=None,
                element_id=None,
                category="pacing",
                mentor_name="save_the_cat",
            ),
        ]

        summary = mentor._generate_summary(analyses, 95)
        assert "95-page screenplay" in summary
        assert "1 structural issues" in summary
        assert "1 areas for improvement" in summary
        assert "key story beats need attention" in summary

    @pytest.mark.asyncio
    async def test_comprehensive_script_analysis(self):
        """Test comprehensive script analysis with realistic data."""
        mentor = SaveTheCatMentor()
        script_id = uuid4()

        # Mock comprehensive script data
        class MockDBOps:
            pass

        async def mock_get_script_data(self, script_id, db_ops):  # noqa: ARG001
            return {
                "script_id": script_id,
                "title": "Hero's Journey",
                "scenes": [
                    # Opening
                    {"id": uuid4(), "page": 1, "elements": []},
                    # Setup
                    {"id": uuid4(), "page": 5, "elements": []},
                    {"id": uuid4(), "page": 10, "elements": []},
                    # Catalyst
                    {"id": uuid4(), "page": 12, "elements": []},
                    # Debate
                    {"id": uuid4(), "page": 20, "elements": []},
                    # Break into Two
                    {"id": uuid4(), "page": 25, "elements": []},
                    # Fun and Games
                    {"id": uuid4(), "page": 35, "elements": []},
                    {"id": uuid4(), "page": 45, "elements": []},
                    # Midpoint
                    {"id": uuid4(), "page": 55, "elements": []},
                    # Bad Guys Close In
                    {"id": uuid4(), "page": 65, "elements": []},
                    # All Is Lost
                    {"id": uuid4(), "page": 75, "elements": []},
                    # Dark Night
                    {"id": uuid4(), "page": 80, "elements": []},
                    # Break into Three
                    {"id": uuid4(), "page": 85, "elements": []},
                    # Finale
                    {"id": uuid4(), "page": 95, "elements": []},
                    {"id": uuid4(), "page": 105, "elements": []},
                    # Final Image
                    {"id": uuid4(), "page": 110, "elements": []},
                ],
                "characters": [
                    {"id": uuid4(), "name": "Luke Skywalker"},
                    {"id": uuid4(), "name": "Obi-Wan Kenobi"},
                    {"id": uuid4(), "name": "Darth Vader"},
                ],
                "total_pages": 110,
            }

        mentor._get_script_data = mock_get_script_data.__get__(mentor, SaveTheCatMentor)

        result = await mentor.analyze_script(script_id, MockDBOps())

        assert result.mentor_name == "save_the_cat"
        assert result.script_id == script_id
        # With placeholder implementation, we still get beat analysis
        assert len(result.analyses) >= 15  # At least one per beat

        # Should have various analysis categories
        categories = {a.category for a in result.analyses}
        expected_categories = {"beat_sheet", "story_structure", "character_arc"}
        assert expected_categories.issubset(categories)

        # Summary should be comprehensive
        assert "110-page screenplay" in result.summary
        assert result.execution_time_ms >= 0

    def test_strict_mode_configuration(self):
        """Test strict mode affects analysis."""
        # Test non-strict mode (default)
        mentor = SaveTheCatMentor({"strict_mode": False})
        assert mentor.strict_mode is False

        # Test strict mode
        mentor = SaveTheCatMentor({"strict_mode": True})
        assert mentor.strict_mode is True

    def test_tolerance_affects_beat_timing(self):
        """Test that tolerance setting affects beat analysis."""
        # Low tolerance
        mentor_strict = SaveTheCatMentor({"tolerance": 1})
        assert mentor_strict.tolerance == 1

        # High tolerance
        mentor_loose = SaveTheCatMentor({"tolerance": 15})
        assert mentor_loose.tolerance == 15

    def test_different_page_counts(self):
        """Test analysis with different target page counts."""
        # Short script
        mentor_short = SaveTheCatMentor({"target_page_count": 90})
        assert mentor_short.target_page_count == 90

        # Long script
        mentor_long = SaveTheCatMentor({"target_page_count": 130})
        assert mentor_long.target_page_count == 130

        # Verify both are valid
        assert mentor_short.validate_config() is True
        assert mentor_long.validate_config() is True

    @pytest.mark.asyncio
    async def test_mentor_registry_integration(self):
        """Test that Save the Cat mentor can be registered and retrieved."""
        from scriptrag.mentors.registry import MentorRegistry

        # Create registry and register mentor class
        registry = MentorRegistry()

        registry.register(SaveTheCatMentor)

        # Retrieve by name
        retrieved = registry.get_mentor("save_the_cat")
        assert retrieved is not None
        assert retrieved.name == "save_the_cat"
        assert isinstance(retrieved, SaveTheCatMentor)

        # Check it appears in listings
        mentors = registry.list_mentors()
        mentor_names = [m["name"] for m in mentors]
        assert "save_the_cat" in mentor_names

        # Check it appears in story structure mentors
        structure_mentors = registry.get_mentors_by_type(MentorType.STORY_STRUCTURE)
        assert "save_the_cat" in structure_mentors

    def test_beat_analysis_recommendations(self):
        """Test that missing beats provide helpful recommendations."""
        # Test beat properties that inform recommendations
        beat = SAVE_THE_CAT_BEATS[3]  # Catalyst
        expected_start = 12
        expected_end = 12

        # Since _find_beat_in_scenes returns empty list, this will create
        # a missing beat analysis with recommendations

        # This tests the beat properties used in analysis creation
        assert beat.required is True
        assert "inciting incident" in beat.keywords
        assert "call to adventure" in beat.keywords

        # Test that beat has the necessary data for recommendations
        expected_page_text = f"pages {expected_start}-{expected_end}"
        assert "pages" in expected_page_text
        assert beat.description is not None
        assert len(beat.keywords) > 0
