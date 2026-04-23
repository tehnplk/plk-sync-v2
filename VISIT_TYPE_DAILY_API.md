# POST Visit Type Daily API

## Endpoint

```http
POST https://dashboard.plkhealth.go.th/telemedicine/api/visit-type-daily
```

## Headers

```http
Content-Type: application/json
```

## Authentication

ไม่ต้องใช้ token

Endpoint นี้เป็น public API

## Request Body

รองรับ 2 รูปแบบ

## 1. ส่งข้อมูล 1 รายการ

```json
{
  "hoscode": "10666",
  "visit_date": "2026-04-23",
  "visit_type_2": 10,
  "visit_type_3": 5,
  "visit_type_5": 2
}
```

## 2. ส่งข้อมูลหลายรายการ

```json
[
  {
    "hoscode": "10666",
    "visit_date": "2026-04-23",
    "visit_type_2": 10,
    "visit_type_3": 5,
    "visit_type_5": 2
  },
  {
    "hoscode": "10667",
    "visit_date": "2026-04-23",
    "visit_type_2": 3,
    "visit_type_3": 1,
    "visit_type_5": 4
  }
]
```

## Field Description

| Field | Required | Type | Description |
|---|---:|---|---|
| `hoscode` | Yes | string | รหัสหน่วยบริการ 5 หลัก ต้องตรงกับ `hospital.hospcode` |
| `visit_date` | Yes | string | วันที่รูปแบบ `YYYY-MM-DD` |
| `visit_type_2` | No | number | มาตามนัด(2), ถ้าไม่ส่งจะเป็น `0` |
| `visit_type_3` | No | number | รับส่งต่อ(3), ถ้าไม่ส่งจะเป็น `0` |
| `visit_type_5` | No | number | แพทย์ทางไกล(5), ถ้าไม่ส่งจะเป็น `0` |

## Success Response

```json
{
  "code": 200,
  "status": "success",
  "message": "Data processed successfully",
  "data": {
    "affectedRows": 1,
    "recordsProcessed": 1
  }
}
```

## Error Response

กรณีไม่ส่ง `hoscode` หรือ `visit_date`

```json
{
  "code": 400,
  "status": "error",
  "message": "hoscode and visit_date are required for each record"
}
```

กรณี payload ว่าง

```json
{
  "code": 400,
  "status": "error",
  "message": "Payload is empty or invalid"
}
```

## Behavior

ระบบบันทึกข้อมูลด้วย `REPLACE INTO visit_type_daily`

ดังนั้นถ้าส่งข้อมูลที่มี `hoscode` และ `visit_date` เดิมซ้ำ ระบบจะเขียนทับข้อมูลเดิมของวันนั้น

## Primary Key

ตาราง `visit_type_daily` ใช้ primary key จาก

| Field |
|---|
| `hoscode` |
| `visit_date` |

## Example Minimal Payload

```json
{
  "hoscode": "10666",
  "visit_date": "2026-04-23"
}
```

ถ้าไม่ส่ง `visit_type_2`, `visit_type_3`, `visit_type_5` ระบบจะบันทึกเป็น `0`
