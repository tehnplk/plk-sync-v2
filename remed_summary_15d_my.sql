-- ============================================================================
-- ชื่อไฟล์    : remed_summary_15d_my.sql
-- ฐานข้อมูล  : HOSxP (MySQL/MariaDB)
-- วัตถุประสงค์ : สรุปจำนวนผู้ป่วยกลุ่มโรคความดันโลหิตสูง (HT) และเบาหวาน (DM)
--                ที่เข้ารับบริการในแต่ละวัน ย้อนหลัง 15 วันนับจากวันปัจจุบัน
--                และได้รับการสั่งจ่ายรายการยาเช่นเดียวกับการเข้ารับบริการครั้งก่อนหน้า
--                (Re-medication) — แสดงผลเป็นรายวัน
--
-- เกณฑ์การนับ (ผู้ป่วยต้องเข้าเงื่อนไขครบทุกข้อ) :
--   1) วันที่เข้ารับบริการ (visit) อยู่ในช่วง 15 วันย้อนหลังจาก CURRENT_DATE
--      (รวมวันปัจจุบัน คือ CURRENT_DATE-14 ถึง CURRENT_DATE)
--   2) รหัสวินิจฉัยโรค (ICD-10) ครอบคลุมกลุ่มโรค HT (I10-I15)
--      หรือ DM (E10-E14) อย่างน้อยหนึ่งรหัส (รองรับรหัส 3-5 หลัก)
--   3) การเข้ารับบริการครั้งดังกล่าวไม่มีการบันทึกหัตถการ
--      (ไม่ปรากฏข้อมูลในตาราง doctor_operation)
--   4) มีการเข้ารับบริการครั้งก่อนหน้าของผู้ป่วยรายเดียวกัน
--      โดยมีระยะห่างระหว่าง 20-100 วัน
--   5) ชุดรหัสวินิจฉัย (DX) ของการเข้ารับบริการทั้งสองครั้งต้องตรงกันทุกประการ
--   6) ชุดรายการยา (รหัสยา icode และจำนวน qty) ของทั้งสองครั้ง
--      ต้องตรงกันทุกประการ โดยพิจารณาเฉพาะรหัสที่ปรากฏในตาราง drugitems
--
-- ตารางที่อ้างอิง :
--   - opitemrece        : รายการเวชภัณฑ์และค่าใช้จ่ายผู้ป่วยนอก
--   - drugitems         : ทะเบียนรหัสยา
--   - ovstdiag          : ข้อมูลการวินิจฉัยโรคต่อการเข้ารับบริการ
--   - doctor_operation  : ข้อมูลหัตถการของแพทย์ต่อการเข้ารับบริการ
--   - opdconfig         : ข้อมูลพื้นฐานของหน่วยบริการ
--
-- พารามิเตอร์ : ไม่มี (ใช้ CURRENT_DATE)
--
-- โครงสร้างผลลัพธ์ (สูงสุด 15 ระเบียน เรียงจากวันใหม่สุดไปเก่าสุด) :
--   hoscode                          รหัสสถานพยาบาล
--   visit_date                       วันที่เข้ารับบริการ
--   count_case_dx_rx_same_prev_vst   จำนวนผู้ป่วยที่เข้าเกณฑ์ในวันนั้น
--
-- ตัวอย่างผลลัพธ์ :
--   hoscode | visit_date | count_case_dx_rx_same_prev_vst
--   --------+------------+-------------------------------
--   07547   | 2026-05-02 | 0
--   07547   | 2026-05-01 | 2
--   07547   | 2026-04-30 | 1
-- ============================================================================

WITH RECURSIVE date_range AS (
  SELECT DATE_SUB(CURRENT_DATE, INTERVAL 14 DAY) AS d
  UNION ALL
  SELECT DATE_ADD(d, INTERVAL 1 DAY) FROM date_range WHERE d < CURRENT_DATE
),
visit_dr AS (
  SELECT hn, vn, vstdate,
         GROUP_CONCAT(CONCAT(icode,':',qty) ORDER BY icode SEPARATOR '|') AS dr
  FROM (SELECT o.hn, o.vn, o.vstdate, o.icode, SUM(o.qty) AS qty
        FROM opitemrece o
        JOIN drugitems d ON d.icode = o.icode
        WHERE o.hn IS NOT NULL
        GROUP BY o.hn, o.vn, o.vstdate, o.icode) x
  GROUP BY hn, vn, vstdate
),
visit_dx AS (
  SELECT vn, GROUP_CONCAT(DISTINCT icd10 ORDER BY icd10 SEPARATOR ', ') AS dx
  FROM ovstdiag
  GROUP BY vn
),
last_pick AS (
  SELECT vd.hn, vd.vn AS last_vn, vd.vstdate AS last_date, vd.dr AS last_dr,
         dx.dx AS last_dx
  FROM visit_dr vd
  JOIN visit_dx dx ON dx.vn = vd.vn
  WHERE vd.vstdate BETWEEN DATE_SUB(CURRENT_DATE, INTERVAL 14 DAY) AND CURRENT_DATE
    AND NOT EXISTS (SELECT 1 FROM doctor_operation op WHERE op.vn = vd.vn)
    AND dx.dx REGEXP '(^|, )(I1[0-5]|E1[0-4])([0-9][0-9]?)?(,|$)'
),
prev_pick AS (
  SELECT lp.hn, lp.last_vn, lp.last_date, lp.last_dr, lp.last_dx,
         vd.vn AS prev_vn, vd.vstdate AS prev_date, vd.dr AS prev_dr,
         ROW_NUMBER() OVER (PARTITION BY lp.hn, lp.last_vn ORDER BY vd.vstdate DESC) AS rn
  FROM last_pick lp
  JOIN visit_dr vd
    ON vd.hn = lp.hn
   AND vd.vstdate < lp.last_date
   AND DATEDIFF(lp.last_date, vd.vstdate) BETWEEN 20 AND 100
),
matched AS (
  SELECT pp.hn, pp.last_date
  FROM prev_pick pp
  JOIN visit_dx dp ON dp.vn = pp.prev_vn
  WHERE pp.rn = 1
    AND pp.last_dr = pp.prev_dr
    AND pp.last_dx = dp.dx
)
SELECT (SELECT hospitalcode FROM opdconfig LIMIT 1) AS hoscode,
       dr.d AS visit_date,
       COUNT(DISTINCT m.hn) AS count_case_dx_rx_same_prev_vst
FROM date_range dr
LEFT JOIN matched m ON m.last_date = dr.d
GROUP BY dr.d
ORDER BY dr.d DESC;
