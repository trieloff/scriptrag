-- name: character_lines
-- description: All dialogue lines for a character
-- param: character str required help="Character name (exact or partial)"
-- param: project str optional
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
    d.dialogue_text dialogue,
    CAST(JSON_EXTRACT(sc.metadata, '$.season') AS INTEGER) season,
    CAST(JSON_EXTRACT(sc.metadata, '$.episode') AS INTEGER) episode
FROM dialogues d
INNER JOIN characters c ON d.character_id = c.id
INNER JOIN scenes s ON d.scene_id = s.id
INNER JOIN scripts sc ON s.script_id = sc.id
WHERE
    1 = 1
    AND (:project IS NULL OR sc.title LIKE :project)
    AND (:character IS NOT NULL AND c.name LIKE :character || '%')
ORDER BY
    COALESCE(CAST(JSON_EXTRACT(sc.metadata, '$.season') AS INTEGER), 9999),
    COALESCE(CAST(JSON_EXTRACT(sc.metadata, '$.episode') AS INTEGER), 9999),
    s.scene_number,
    d.order_in_scene
LIMIT :limit OFFSET :offset
