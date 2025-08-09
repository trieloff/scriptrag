"""Unit tests for SQL header parser (QuerySpec/ParamSpec)."""

from pathlib import Path

from scriptrag.query.spec import QuerySpec, parse_query_file


def test_parse_basic_headers(tmp_path: Path):
    sql = (
        "-- name: test_query\n"
        "-- description: A test query\n"
        '-- param: foo str required help="Foo help" choices=a|b\n'
        "-- param: bar int optional default=5\n\n"
        "SELECT :foo as f, :bar as b;\n"
    )
    p = tmp_path / "q.sql"
    p.write_text(sql, encoding="utf-8")

    spec = parse_query_file(p)
    assert isinstance(spec, QuerySpec)
    assert spec.name == "test_query"
    assert spec.description == "A test query"
    assert len(spec.params) == 2
    foo = next(x for x in spec.params if x.name == "foo")
    bar = next(x for x in spec.params if x.name == "bar")
    assert foo.required and foo.type == "str" and foo.help == "Foo help"
    assert foo.choices == ["a", "b"]
    assert not bar.required and bar.type == "int" and bar.default == 5


def test_missing_name_falls_back_to_filename(tmp_path: Path):
    sql = "-- description: No name present\nSELECT 1;\n"
    p = tmp_path / "fallback.sql"
    p.write_text(sql, encoding="utf-8")
    spec = parse_query_file(p)
    assert spec.name == "fallback"
