"""Unit tests for generic query formatter."""

from scriptrag.query.formatter import _looks_like_scene_rows, format_rows


def test_scene_like_detection():
    rows = [
        {
            "script_title": "A",
            "scene_number": 1,
            "scene_heading": "INT. TEST - DAY",
            "scene_content": "Hello",
        }
    ]
    assert _looks_like_scene_rows(rows)
    assert not _looks_like_scene_rows([])


def test_generic_table_formatting():
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    out = format_rows(rows, json_output=False, title="T")
    assert out is None

    # JSON output returns a string
    j = format_rows(rows, json_output=True)
    assert isinstance(j, str)
    assert "\n" in j
