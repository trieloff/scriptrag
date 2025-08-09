-- name: test_list_scripts
-- description: List all indexed scripts
-- param: limit int optional default=10 help="Maximum number of rows to return"
-- param: offset int optional default=0 help="Number of rows to skip"

SELECT
    scripts.id,
    scripts.title,
    scripts.author,
    scripts.file_path,
    scripts.created_at
FROM
    scripts
ORDER BY
    scripts.created_at DESC
LIMIT :limit OFFSET :offset
