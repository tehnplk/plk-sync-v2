from __future__ import annotations

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover
    pymysql = None
    DictCursor = None

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


ENV_FILE = ".env"
ENDPOINT_FILE = "drug_home_count_endpoint.txt"
DEFAULT_CHARSET = "utf8"
DEFAULT_TIMEOUT = 60
API_FIELDS = (
    "hospital",
    "vstdate",
    "total_cases",
    "count_self_pickup",
    "count_home_delivery",
    "count_other",
    "count_chronic_patients",
    "count_chronic_home_delivery",
    "delivery_company_details"
)
SQL_FILES = {
    "mysql": "drug_home_count_my.sql",
    "postgres": "drug_home_count_pg.sql",
}
DEFAULT_LOG_TIMEZONE = "Asia/Bangkok"


def log(level: str, message: str) -> None:
    timezone_name = os.getenv("SYNC_TIMEZONE", DEFAULT_LOG_TIMEZONE)
    timestamp = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {level.upper()} - {message}")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def get_db_type() -> str:
    db_type = os.getenv("DB_TYPE", "mysql").strip().lower()
    aliases = {
        "mariadb": "mysql",
        "mysql": "mysql",
        "postgres": "postgres",
        "postgresql": "postgres",
    }

    if db_type not in aliases:
        allowed = ", ".join(sorted(aliases))
        raise RuntimeError(f"Unsupported DB_TYPE={db_type!r}; use one of: {allowed}")

    return aliases[db_type]


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape_next = False

    for char in sql:
        current.append(char)

        if escape_next:
            escape_next = False
            continue

        if quote and char == "\\":
            escape_next = True
            continue

        if char in ("'", '"', "`"):
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            continue

        if char == ";" and quote is None:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement[:-1].strip())
            current = []

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def read_sql_statements(sql_path: Path, start_date: str, end_date: str) -> list[str]:
    sql = sql_path.read_text(encoding="utf-8-sig")
    
    # แทนที่ระบบ placeholder ด้วยค่าวันที่เหมาะสมสำหรับ Query
    sql = sql.replace("{start_date}", start_date).replace("{end_date}", end_date)
    
    statements = split_sql_statements(sql)
    if not statements:
        raise RuntimeError(f"No SQL statements found in {sql_path}")
    return statements


def read_endpoint_config(path: Path) -> tuple[str, str | None]:
    if not path.exists():
        raise RuntimeError(f"Missing endpoint file: {path}")

    url = None
    token = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            parts = line.split("=", 1)
            k = parts[0].strip().lower()
            v = parts[1].strip().strip('"').strip("'")
            if k == "url":
                url = v
            elif k in ("token", "key", "secret_key"):
                token = v
        elif line.startswith(("http://", "https://")):
            url = line

    if not url:
        raise RuntimeError(f"No endpoint URL found in {path}")

    return url, token


def fetch_mysql_rows(sql_path: Path, is_init_mode: bool) -> list[dict[str, Any]]:
    if pymysql is None or DictCursor is None:
        raise RuntimeError("Missing MySQL dependency: install with `pip install -r requirements.txt`")

    # กำหนดช่วงเวลาสำหรับ MySQL
    if is_init_mode:
        start_date = "'2025-10-01'"
        end_date = "CURRENT_DATE()"
    else:
        # ดึงข้อมูลวันก่อนหน้า (Yesterday) สำหรับการรันตอนเช้ามืด (ตี 5)
        start_date = "CURRENT_DATE() - INTERVAL 1 DAY"
        end_date = "CURRENT_DATE() - INTERVAL 1 DAY"

    statements = read_sql_statements(sql_path, start_date, end_date)

    connection = pymysql.connect(
        host=require_env("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=require_env("DB_USER"),
        password=require_env("DB_PASSWORD"),
        database=require_env("DB_NAME"),
        charset=os.getenv("DB_CHARSET", DEFAULT_CHARSET),
        cursorclass=DictCursor,
        autocommit=True,
    )

    try:
        rows: list[dict[str, Any]] = []
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
                if cursor.description:
                    rows = list(cursor.fetchall())
        return rows
    finally:
        connection.close()


def fetch_postgres_rows(sql_path: Path, is_init_mode: bool) -> list[dict[str, Any]]:
    if psycopg is None or dict_row is None:
        raise RuntimeError("Missing PostgreSQL dependency: install with `pip install -r requirements.txt`")

    # กำหนดช่วงเวลาสำหรับ PostgreSQL
    if is_init_mode:
        start_date = "DATE '2025-10-01'"
        end_date = "CURRENT_DATE"
    else:
        # ดึงข้อมูลวันก่อนหน้า (Yesterday) สำหรับการรันตอนเช้ามืด (ตี 5)
        start_date = "CURRENT_DATE - INTERVAL '1 day'"
        end_date = "CURRENT_DATE - INTERVAL '1 day'"

    statements = read_sql_statements(sql_path, start_date, end_date)

    connection = psycopg.connect(
        host=require_env("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=require_env("DB_USER"),
        password=require_env("DB_PASSWORD"),
        dbname=require_env("DB_NAME"),
        autocommit=True,
        row_factory=dict_row,
    )

    try:
        rows: list[dict[str, Any]] = []
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
                if cursor.description:
                    rows = list(cursor.fetchall())
        return rows
    finally:
        connection.close()


def fetch_rows(sql_path: Path, is_init_mode: bool) -> list[dict[str, Any]]:
    db_type = get_db_type()
    if db_type == "mysql":
        return fetch_mysql_rows(sql_path, is_init_mode)
    if db_type == "postgres":
        return fetch_postgres_rows(sql_path, is_init_mode)
    raise RuntimeError(f"Unsupported database type: {db_type}")


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    record = {field: row.get(field) for field in API_FIELDS}

    if not record["hospital"] or not record["vstdate"]:
        raise RuntimeError(f"SQL row is missing hospital or vstdate: {row}")

    record["hospital"] = str(record["hospital"])
    
    # Format vstdate to YYYY-MM-DD string
    if isinstance(record["vstdate"], (datetime, date)):
        record["vstdate"] = record["vstdate"].strftime("%Y-%m-%d")
    else:
        record["vstdate"] = str(record["vstdate"])

    for field in (
        "total_cases",
        "count_self_pickup",
        "count_home_delivery",
        "count_other",
        "count_chronic_patients",
        "count_chronic_home_delivery"
    ):
        record[field] = int(record[field] or 0)

    # Parse delivery_company_details JSON string to python object
    if isinstance(record["delivery_company_details"], str):
        try:
            record["delivery_company_details"] = json.loads(record["delivery_company_details"])
        except Exception:
            record["delivery_company_details"] = None
    elif record["delivery_company_details"] is None:
         record["delivery_company_details"] = None

    return record


def post_payload(url: str, payload: list[dict[str, Any]], timeout: int, token: str | None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["X-API-Key"] = token

    request = Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return {
                "status_code": response.status,
                "body": json.loads(response_body) if response_body else None,
            }
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not connect to API: {exc.reason}") from exc


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=base_dir / ENV_FILE, override=False)

    db_type = get_db_type()
    sql_path = Path(os.getenv("SQL_FILE", SQL_FILES[db_type]))
    if not sql_path.is_absolute():
        sql_path = base_dir / sql_path

    endpoint_path = Path(os.getenv("DRUG_HOME_ENDPOINT_FILE", ENDPOINT_FILE))
    if not endpoint_path.is_absolute():
        endpoint_path = base_dir / endpoint_path

    timeout = env_int("DRUG_HOME_TIMEOUT", DEFAULT_TIMEOUT)
    dry_run = env_bool("DRUG_HOME_DRY_RUN", default=False)
    pretty = env_bool("DRUG_HOME_PRETTY", default=True)

    # ตรวจเช็ค Parameter หรือ Env ว่าเป็นการรันครั้งแรกหรือไม่ (Initial Run vs Cron Job)
    is_init_mode = "--init" in sys.argv or env_bool("DRUG_HOME_SYNC_INIT", default=False)
    
    log("info", f"Syncing mode: {'INITIAL (full historical sync)' if is_init_mode else 'CRON JOB (yesterday date only)'}")

    rows = fetch_rows(sql_path, is_init_mode)
    payload = [normalize_record(row) for row in rows]

    log("info", f"Fetched {len(rows)} rows from {sql_path.name}")
    log("info", f"Prepared {len(payload)} API records")

    if dry_run:
        log("info", "Dry-run enabled; payload below")
        payload_text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None)
        log("info", f"Payload:\n{payload_text}")
        return 0

    if not payload:
        log("info", "No records to post; skipped API request.")
        return 0

    endpoint, token = read_endpoint_config(endpoint_path)
    endpoint = os.getenv("DRUG_HOME_API_URL") or endpoint
    token = os.getenv("DRUG_HOME_API_TOKEN") or token

    result = post_payload(endpoint, payload, timeout, token)
    log("info", f"POST completed with status_code={result['status_code']}")
    result_text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    log("info", f"Response: {result_text}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("error", str(exc))
        raise SystemExit(1)
