.headers on
.mode csv
.output pending_actions_$(date +%Y%m%d).csv
SELECT
    action_id AS "#",
    action_type AS "Action",
    mouse_id AS "Mouse",
    old_cage_id AS "From",
    new_cage_id AS "To",
    substr(details, 1, 40) AS "Notes"
FROM pending_actions
WHERE executed_at IS NULL
ORDER BY action_type, mouse_id;
.quit