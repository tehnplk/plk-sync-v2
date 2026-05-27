-- คิวรี่สำหรับดึงข้อมูลสรุปการจ่ายยารายวันจากตาราง HOSxP (PostgreSQL)
-- ใช้ระบบ placeholder {start_date} และ {end_date} สำหรับจัดการช่วงวันที่ซิงค์

SELECT 
    (SELECT hospitalcode FROM opdconfig LIMIT 1) AS hospital,
    o.vstdate,
    
    -- นับจำนวนรวมเฉพาะคนที่มีข้อมูลจ่ายยา
    COUNT(DISTINCT hr.vn) AS total_cases,
    
    -- แยกนับจำนวนตามเงื่อนไขการรับยา
    COUNT(DISTINCT CASE WHEN hr.home_rx_status_id = '1' THEN hr.vn END) AS count_self_pickup,
    COUNT(DISTINCT CASE WHEN hr.home_rx_status_id = '2' THEN hr.vn END) AS count_home_delivery,
    COUNT(DISTINCT CASE WHEN hr.home_rx_status_id NOT IN ('1', '2') OR hr.home_rx_status_id IS NULL THEN hr.vn END) AS count_other,
    
    -- นับจำนวนผู้ป่วยทั้งหมดที่มีระบุประเภทโรคเรื้อรัง
    COUNT(DISTINCT CASE WHEN c.chronic_type IS NOT NULL AND c.chronic_type <> '' THEN hr.vn END) AS count_chronic_patients,
    
    -- นับจำนวนผู้ป่วย "โรคเรื้อรัง" ที่ "รับยาที่บ้าน"
    COUNT(DISTINCT CASE WHEN (c.chronic_type IS NOT NULL AND c.chronic_type <> '') 
                         AND hr.home_rx_status_id = '2' THEN hr.vn END) AS count_chronic_home_delivery,
    
    -- ดึงข้อมูลชื่อบริษัทขนส่งและจำนวน ในรูปแบบ JSON Array
    comp_summary.company_json AS delivery_company_details

FROM ovst_home_rx hr
INNER JOIN ovst o ON o.vn = hr.vn
LEFT JOIN clinicmember c ON c.hn = o.hn

-- Subquery สำหรับสร้าง JSON รายชื่อบริษัทขนส่ง
LEFT JOIN (
    SELECT 
        sub.vstdate,
        -- สร้างโครงสร้าง JSON Array โดยใช้ string_agg และ concatenation ใน PostgreSQL
        '[' || STRING_AGG(
            '{"company": "' || COALESCE(sub.company_name, 'ไม่ระบุ') || '", "count": ' || sub.qty || '}', 
            ','
        ) || ']' AS company_json
    FROM (
        -- นับจำนวน vn แยกตามบริษัทขนส่งในวันนั้น
        SELECT 
            o2.vstdate,
            dc.prscrpt_delivery_company_name AS company_name,
            COUNT(DISTINCT hr2.vn) AS qty
        FROM ovst_home_rx hr2
        INNER JOIN ovst o2 ON o2.vn = hr2.vn
        INNER JOIN prscrpt_delivery_med dm ON dm.vn = hr2.vn
        INNER JOIN prscrpt_delivery_company dc ON dc.prscrpt_delivery_company_id = dm.prscrpt_delivery_company_id
        WHERE o2.vstdate BETWEEN {start_date} AND {end_date}
        GROUP BY o2.vstdate, dc.prscrpt_delivery_company_name
    ) sub
    GROUP BY sub.vstdate
) comp_summary ON comp_summary.vstdate = o.vstdate

WHERE o.vstdate BETWEEN {start_date} AND {end_date}

GROUP BY o.vstdate, comp_summary.company_json;
