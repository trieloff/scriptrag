-- name: character_lines
-- description: Get all dialogue lines for a character
-- param: character str required help="Character name (exact or partial match)"
-- param: project str optional help="Filter by project title"
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
    d.character,
    d.dialogue,
    d.parenthetical,
    CAST(JSON_EXTRACT(s.metadata, '$.season') AS INTEGER) season,
    CAST(JSON_EXTRACT(s.metadata, '$.episode') AS INTEGER) episode
FROM
    dialogues d
INNER JOIN scenes sc ON d.scene_id = sc.id
INNER JOIN scripts s ON sc.script_id = s.id
WHERE
    d.character LIKE :character || '%'
    AND (:project IS NULL OR s.title LIKE '%' || :project || '%')
ORDER BY
    COALESCE(
        CAST(JSON_EXTRACT(s.metadata, '$.season') AS INTEGER),
        9999
    ),
    COALESCE(
        CAST(JSON_EXTRACT(s.metadata, '$.episode') AS INTEGER),
        9999
    ),
    sc.scene_number,
    d.dialogue_order
LIMIT :limit OFFSET :offset
