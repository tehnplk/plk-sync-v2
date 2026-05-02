-- Count HOSxP visits by ovstist.export_code for MySQL/MariaDB.
-- Output columns match VISIT_TYPE_DAILY_API.md payload.

SELECT
    COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)) AS hoscode,
    DATE_FORMAT(o.vstdate, '%Y-%m-%d') AS visit_date,
    SUM(CASE WHEN i.export_code = '2' THEN 1 ELSE 0 END) AS visit_type_2,
    SUM(CASE WHEN i.export_code = '3' THEN 1 ELSE 0 END) AS visit_type_3,
    SUM(CASE WHEN i.export_code = '5' THEN 1 ELSE 0 END) AS visit_type_5
FROM ovst o
LEFT JOIN ovstist i ON o.ovstist = i.ovstist
WHERE DATE(o.vstdate) BETWEEN '2026-03-23' AND CURRENT_DATE()
GROUP BY COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)), DATE(o.vstdate)
ORDER BY COALESCE(NULLIF(o.hcode, ''), (SELECT hospitalcode FROM opdconfig LIMIT 1)), DATE(o.vstdate);
