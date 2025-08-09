# Query Command

Run pre-authored parameterized SQL queries against the ScriptRAG SQLite DB.

Usage:

```
scriptrag query --help
scriptrag query <name> [--<param> ...] [--limit N] [--offset N] [--json]
```

Queries are discovered from `SCRIPTRAG_QUERY_DIR` (default: `src/scriptrag/storage/database/queries`).

Each `.sql` file can declare a header describing its parameters:

```
-- name: list_scenes
-- description: List scenes by project and optional episode range
-- param: project str optional help="Filter by project title"
-- param: season int optional
-- param: episode int optional
-- param: limit int optional default=10
-- param: offset int optional default=0

SELECT ... WHERE ... LIMIT :limit OFFSET :offset
```

Supported param types: `str`, `int`, `float`, `bool`. Booleans accept `true/false/1/0/yes/no` (case-insensitive). When `limit`/`offset` are declared but not used in the SQL, the engine wraps the query as `SELECT * FROM (<sql>) LIMIT :limit OFFSET :offset`.

Security: queries run via read-only connections and always use SQLite parameter binding (no string interpolation).
