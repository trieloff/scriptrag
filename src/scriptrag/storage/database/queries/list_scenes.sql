-- name: list_scenes
-- description: List scenes by project and optional episode range
-- param: project str optional help="Filter by project title (partial match)"
-- param: season int optional help="Filter by season number"
-- param: episode int optional help="Filter by episode number"
-- param: limit int optional default=10 help="Maximum number of rows to return"
-- param: offset int optional default=0 help="Number of rows to skip"

SELECT
    s.id script_id,
    s.title script_title,
    s.author script_author,
    sc.id scene_id,
    sc.scene_number,
    sc.heading scene_heading,
    sc.location scene_location,
    sc.time_of_day scene_time,
    sc.content scene_content,
    CAST(JSON_EXTRACT(s.metadata, '$.season') AS INTEGER) season,
    CAST(JSON_EXTRACT(s.metadata, '$.episode') AS INTEGER) episode
FROM
    scenes sc
INNER JOIN scripts s ON sc.script_id = s.id
WHERE
    1 = 1
    AND (:project IS NULL OR s.title LIKE '%' || :project || '%')
    AND (
        :season IS NULL
        OR CAST(JSON_EXTRACT(s.metadata, '$.season') AS INTEGER) = :season
    )
    AND (
        :episode IS NULL
        OR CAST(JSON_EXTRACT(s.metadata, '$.episode') AS INTEGER) = :episode
    )
ORDER BY
    COALESCE(
        CAST(JSON_EXTRACT(s.metadata, '$.season') AS INTEGER),
        9999
    ),
    COALESCE(
        CAST(JSON_EXTRACT(s.metadata, '$.episode') AS INTEGER),
        9999
    ),
    sc.scene_number
LIMIT :limit OFFSET :offset
