# plk-sync-v2

ส่งข้อมูล visit type จาก HOSxP ไป API อัตโนมัติด้วย Docker + Cron

## Quick Deploy

1. สร้างไฟล์ env

```bash
cp .env.example .env
```

2. แก้ค่าใน `.env` ให้ถูกต้อง (DB host/user/password/database)

3. Build + Start

```bash
docker compose up -d --build
```

## การทำงาน

- รันทันที 1 ครั้งตอน container start
- รันตาม cron ทุกวันเวลา `07:30` และ `16:00` (Asia/Bangkok)

## คำสั่งเช็ก

```bash
docker compose ps
docker exec plk-sync-v2 crontab -l
tail -f logs/visit_type_count_sync.log
tail -f logs/remed_sync.log
```

## อัปเดตโค้ด

- ถ้าแก้ `.py`, `.sql`, `.env` ไม่ต้อง build ใหม่
- ถ้าแก้ `Dockerfile` หรือ `docker/cron/plk-sync.cron` ให้รัน:

```bash
docker compose up -d --build
```
