-- name: list_scenes
-- description: List scenes by project and optional episode range
-- param: project str optional help="Filter by project title"
-- param: season int optional
-- param: episode int optional
-- param: limit int optional default=10
-- param: offset int optional default=0

SELECT
    sc.id script_id,
    sc.title script_title,
    sc.author script_author,
    s.id scene_id,
    s.scene_number,
    s.heading scene_heading,
    s.location scene_location,
    s.time_of_day scene_time,
    s.content scene_content,
    CAST(JSON_EXTRACT(sc.metadata, '$.season') AS INTEGER) season,
    CAST(JSON_EXTRACT(sc.metadata, '$.episode') AS INTEGER) episode
FROM scenes s
INNER JOIN scripts sc ON s.script_id = sc.id
WHERE
    1 = 1
    AND (:project IS NULL OR sc.title LIKE :project)
    AND (
        :season IS NULL
        OR CAST(JSON_EXTRACT(sc.metadata, '$.season') AS INTEGER) = :season
    )
    AND (
        :episode IS NULL
        OR CAST(JSON_EXTRACT(sc.metadata, '$.episode') AS INTEGER) = :episode
    )
ORDER BY
    COALESCE(CAST(JSON_EXTRACT(sc.metadata, '$.season') AS INTEGER), 9999),
    COALESCE(CAST(JSON_EXTRACT(sc.metadata, '$.episode') AS INTEGER), 9999),
    s.scene_number
LIMIT :limit OFFSET :offset
