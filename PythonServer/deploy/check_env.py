"""systemd가 주입한 설정 검사 (비밀 값 미출력, --database는 SELECT만 실행)"""
from __future__ import annotations

import argparse
import importlib
import math
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate(env: dict[str, str]) -> list[str]:
    errors = []
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "KTO_SERVICE_KEY", "BFF_GATEWAY_TOKEN"]
    if env.get("USE_LLM", "").lower() == "true":
        required += ["LLM_API_KEY", "LLM_MODEL"]
    for key in required:
        value = env.get(key, "").strip()
        if not value or value.startswith("<") or value.lower() in {"change-me", "changeme"}:
            errors.append(f"{key}: a real non-empty value is required")
    for key, expected in {"USE_MOCK": "false", "COOKIE_SECURE": "true"}.items():
        if env.get(key, "").lower() != expected:
            errors.append(f"{key}: must be {expected} in production")
    if env.get("USE_LLM", "") not in {"true", "false"}:
        errors.append("USE_LLM: use true or false")
    token = env.get("BFF_GATEWAY_TOKEN", "")
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        errors.append("BFF_GATEWAY_TOKEN: use at least 32 ASCII characters without whitespace")
    if env.get("SESSION_COOKIE_NAME", "session_id") != "session_id":
        errors.append("SESSION_COOKIE_NAME: must match A's fixed session_id")
    if env.get("COOKIE_SAMESITE") != "lax":
        errors.append("COOKIE_SAMESITE: use lax for the same-origin frontend proxy")
    origins = [s.strip() for s in env.get("ALLOWED_ORIGINS", "").split(",") if s.strip()]
    if not origins:
        errors.append("ALLOWED_ORIGINS: at least one HTTPS frontend origin is required")
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or "*" in origin
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            errors.append("ALLOWED_ORIGINS: use exact HTTPS origins, without paths or wildcards")
    for key, expected in {
        "A_BASE_URL": "http://127.0.0.1:8000",
        "B_BASE_URL": "http://127.0.0.1:8001",
        "C_BASE_URL": "http://127.0.0.1:8002",
    }.items():
        if env.get(key) != expected:
            errors.append(f"{key}: must match the loopback address in the installed units")
    # 배포 템플릿의 숫자 설정은 모두 명시 필요
    integer_keys = {
        "DB_PORT": (1, 65535), "SESSION_TTL_SECONDS": (1, None),
        "KTO_NUM_OF_ROWS": (1, None), "MAX_DETAIL_BATCH": (1, None),
        "KTO_MAX_RETRY": (0, None), "MAX_CANDIDATES": (1, None),
        "KTO_MAX_CONCURRENCY": (1, None), "KTO_DAILY_QUOTA": (1, None),
        "LLM_MAX_OUTPUT_TOKENS": (1, None), "LLM_DAILY_REQUEST_LIMIT": (1, 45),
        "LLM_MAX_RETRIES": (0, None), "LLM_OVERVIEW_MAX_CHARS": (1, None),
    }
    for key, (minimum, maximum) in integer_keys.items():
        try:
            number = int(env.get(key, ""))
            if number < minimum or (maximum is not None and number > maximum):
                raise ValueError
        except ValueError:
            errors.append(f"{key}: invalid or empty integer")
    timeouts = {}
    for key in ["KTO_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", "B_TIMEOUT_SECONDS", "UPSTREAM_TIMEOUT_SECONDS"]:
        try:
            number = float(env.get(key, ""))
            if not math.isfinite(number) or number <= 0:
                raise ValueError
            timeouts[key] = number
        except ValueError:
            errors.append(f"{key}: must be a positive finite number")
    if len(timeouts) == 4:
        if not (timeouts["KTO_TIMEOUT_SECONDS"] < timeouts["B_TIMEOUT_SECONDS"] < timeouts["UPSTREAM_TIMEOUT_SECONDS"] < 120):
            errors.append("timeouts: require KTO < B < UPSTREAM < nginx's 120 seconds")
        if timeouts["LLM_TIMEOUT_SECONDS"] >= timeouts["UPSTREAM_TIMEOUT_SECONDS"]:
            errors.append("LLM_TIMEOUT_SECONDS: must be below UPSTREAM_TIMEOUT_SECONDS")
    if env.get("DB_SSL_CA") and not Path(env["DB_SSL_CA"]).is_file():
        errors.append("DB_SSL_CA: certificate file is missing or unreadable")
    return errors


def check_database() -> None:
    from shared import database

    tables = ("user", "session", "session_revocation", "plan", "plan_item",
              "plan_deletion", "kto_api_call", "llm_request", "llm_token_usage")
    connection = database.connect()
    try:
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT * FROM `{table}` LIMIT 0")
            cursor.execute("SELECT `visit_time` FROM `plan_item` LIMIT 0")
        print("PASS: database connection and all nine tables (SELECT only)")
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", action="store_true")
    args = parser.parse_args()
    try:
        errors = validate(dict(os.environ))
    except ValueError:
        errors = ["configuration contains an invalid URL"]
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    try:
        for module in ["A_backend.config", "B_openapi.config", "C_ai_planner.config", "D_frontend.config"]:
            importlib.import_module(module)
        if args.database:
            check_database()
    except Exception as exc:
        # 드라이버 예외 메시지에 호스트/계정이 섞일 수 있어 미출력
        print(f"FAIL: {'database/configuration' if args.database else 'configuration'} check ({type(exc).__name__}); check settings, dependencies and connectivity", file=sys.stderr)
        return 1
    print("PASS: production configuration (secret values not displayed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
