-- name: character_stats
-- description: Get dialogue statistics for characters
-- param: project str optional help="Filter by project title"
-- param: min_lines int optional default=5 help="Minimum lines to include"
-- param: limit int optional default=20 help="Maximum characters to return"

SELECT
    d.character,
    COUNT(DISTINCT sc.id) scene_count,
    COUNT(*) dialogue_count,
    SUM(LENGTH(d.dialogue)) total_dialogue_length,
    AVG(LENGTH(d.dialogue)) avg_dialogue_length,
    GROUP_CONCAT(DISTINCT s.title) projects
FROM
    dialogues d
INNER JOIN scenes sc ON d.scene_id = sc.id
INNER JOIN scripts s ON sc.script_id = s.id
WHERE
    :project IS NULL OR s.title LIKE '%' || :project || '%'
GROUP BY
    d.character
HAVING
    COUNT(*) >= :min_lines
ORDER BY
    dialogue_count DESC
LIMIT :limit
