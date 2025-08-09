-- name: simple_scene_list
-- description: List scenes with basic information
-- param: limit int optional default=10 help="Maximum number of rows to return"
-- param: offset int optional default=0 help="Number of rows to skip"

SELECT
    sc.id,
    sc.scene_number,
    sc.heading,
    sc.location,
    sc.time_of_day,
    s.title script_title
FROM
    scenes sc
INNER JOIN scripts s ON sc.script_id = s.id
ORDER BY
    s.title,
    sc.scene_number
LIMIT :limit OFFSET :offset
