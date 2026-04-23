from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover - shown only when dependency is missing.
    pymysql = None
    DictCursor = None

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - shown only when dependency is missing.
    psycopg = None
    dict_row = None


ENV_FILE = ".env"
DEFAULT_CHARSET = "utf8"
DEFAULT_TIMEOUT = 60
API_FIELDS = ("hoscode", "visit_date", "visit_type_2", "visit_type_3", "visit_type_5")
SQL_FILES = {
    "mysql": "mysql_visit_type_count.sql",
    "postgres": "postgres_visit_type_count.sql",
}
DEFAULT_LOG_TIMEZONE = "Asia/Bangkok"


def log(level: str, message: str) -> None:
    timezone_name = os.getenv("SYNC_TIMEZONE", DEFAULT_LOG_TIMEZONE)
    timestamp = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {level.upper()} - {message}")


def load_env(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


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


def read_sql_statements(sql_path: Path) -> list[str]:
    sql = sql_path.read_text(encoding="utf-8-sig")
    statements = split_sql_statements(sql)
    if not statements:
        raise RuntimeError(f"No SQL statements found in {sql_path}")
    return statements


def fetch_mysql_rows(sql_path: Path) -> list[dict[str, Any]]:
    if pymysql is None or DictCursor is None:
        raise RuntimeError("Missing MySQL dependency: install with `pip install -r requirements.txt`")

    statements = read_sql_statements(sql_path)

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


def fetch_postgres_rows(sql_path: Path) -> list[dict[str, Any]]:
    if psycopg is None or dict_row is None:
        raise RuntimeError("Missing PostgreSQL dependency: install with `pip install -r requirements.txt`")

    statements = read_sql_statements(sql_path)

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


def fetch_rows(sql_path: Path) -> list[dict[str, Any]]:
    db_type = get_db_type()
    if db_type == "mysql":
        return fetch_mysql_rows(sql_path)
    if db_type == "postgres":
        return fetch_postgres_rows(sql_path)
    raise RuntimeError(f"Unsupported database type: {db_type}")


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    record = {field: row.get(field) for field in API_FIELDS}

    if not record["hoscode"] or not record["visit_date"]:
        raise RuntimeError(f"SQL row is missing hoscode or visit_date: {row}")

    record["hoscode"] = str(record["hoscode"])
    record["visit_date"] = str(record["visit_date"])

    for field in ("visit_type_2", "visit_type_3", "visit_type_5"):
        record[field] = int(record[field] or 0)

    return record


def post_payload(url: str, payload: list[dict[str, Any]], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
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
    env_path = base_dir / ENV_FILE

    load_env(env_path)

    db_type = get_db_type()
    sql_path = Path(os.getenv("SQL_FILE", SQL_FILES[db_type]))
    if not sql_path.is_absolute():
        sql_path = base_dir / sql_path

    timeout = env_int("VISIT_TYPE_DAILY_TIMEOUT", DEFAULT_TIMEOUT)
    dry_run = env_bool("VISIT_TYPE_DAILY_DRY_RUN", default=False)
    pretty = env_bool("VISIT_TYPE_DAILY_PRETTY", default=True)

    rows = fetch_rows(sql_path)
    payload = [normalize_record(row) for row in rows]
    json_indent = 2 if pretty else None

    log("info", f"Fetched {len(rows)} rows from {sql_path.name}")
    log("info", f"Prepared {len(payload)} API records")

    if dry_run:
        log("info", "Dry-run enabled; payload below")
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        log("info", f"Payload: {payload_text}")
        return 0

    if not payload:
        log("info", "No records to post; skipped API request.")
        return 0

    endpoint = require_env("VISIT_TYPE_DAILY_API_URL")
    result = post_payload(endpoint, payload, timeout)
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
