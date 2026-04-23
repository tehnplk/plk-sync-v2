-- Count HOSxP visits by ovstist.export_code for PostgreSQL.
-- Output columns match VISIT_TYPE_DAILY_API.md payload.

SELECT
    COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)) AS hoscode,
    TO_CHAR(o.vstdate::date, 'YYYY-MM-DD') AS visit_date,
    SUM(CASE WHEN i.export_code = '2' THEN 1 ELSE 0 END) AS visit_type_2,
    SUM(CASE WHEN i.export_code = '3' THEN 1 ELSE 0 END) AS visit_type_3,
    SUM(CASE WHEN i.export_code = '5' THEN 1 ELSE 0 END) AS visit_type_5
FROM ovst o
LEFT JOIN ovstist i ON o.ovstist = i.ovstist
WHERE o.vstdate >= DATE '2026-03-23'
GROUP BY COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)), o.vstdate::date
ORDER BY COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)), o.vstdate::date;
