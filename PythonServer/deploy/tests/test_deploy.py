"""Offline deployment checks. Never load .env or connect to MySQL/external APIs.

Run: python -B -m unittest discover -s deploy/tests -v
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

DEPLOY = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, DEPLOY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("check_env")
smoke = load("smoke_test")


def valid_env():
    values = {}
    for line in (DEPLOY / "eodiego.env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    values.update(DB_HOST="db.invalid", DB_PASSWORD="test-only-password",
                  KTO_SERVICE_KEY="test-only-key", BFF_GATEWAY_TOKEN="a" * 64)
    return values


class ConfigurationTests(unittest.TestCase):
    def test_template_with_secrets_imports_real_configs_without_network(self):
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
        env.update(valid_env(), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-B", str(DEPLOY / "check_env.py")],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(env["DB_PASSWORD"], result.stdout + result.stderr)

    def test_missing_gateway_cannot_disable_production_auth(self):
        env = valid_env()
        del env["BFF_GATEWAY_TOKEN"]
        self.assertTrue(any("BFF_GATEWAY_TOKEN" in e for e in check.validate(env)))

    def test_blank_and_nonfinite_numeric_values_are_rejected(self):
        for key, value in [("LLM_MAX_OUTPUT_TOKENS", ""), ("DB_PORT", ""),
                           ("B_TIMEOUT_SECONDS", "nan"), ("UPSTREAM_TIMEOUT_SECONDS", "inf")]:
            with self.subTest(key=key):
                env = valid_env()
                env[key] = value
                self.assertTrue(any(key in e for e in check.validate(env)))

    def test_cookie_mismatch_and_insecure_origins_are_rejected(self):
        for key, value in [("COOKIE_SECURE", "false"), ("SESSION_COOKIE_NAME", "other"),
                           ("ALLOWED_ORIGINS", "*"), ("ALLOWED_ORIGINS", "http://example.com")]:
            with self.subTest(key=key, value=value):
                env = valid_env()
                env[key] = value
                self.assertTrue(any(key in e for e in check.validate(env)))

    def test_llm_requires_key_when_enabled(self):
        env = valid_env()
        env["USE_LLM"] = "true"
        self.assertTrue(any("LLM_API_KEY" in e for e in check.validate(env)))

    def test_errors_do_not_echo_secret_values(self):
        env = valid_env()
        env["BFF_GATEWAY_TOKEN"] = "private short value"
        self.assertNotIn(env["BFF_GATEWAY_TOKEN"], str(check.validate(env)))

    def test_database_check_issues_only_select_and_closes_connection(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        fake_database = SimpleNamespace(connect=lambda: connection)
        with patch.dict(sys.modules, {"shared.database": fake_database}), contextlib.redirect_stdout(io.StringIO()):
            check.check_database()
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(len(queries), 10)
        self.assertTrue(all(query.startswith("SELECT ") and query.endswith("LIMIT 0") for query in queries))
        connection.close.assert_called_once()


class SmokeTests(unittest.TestCase):
    def run_smoke(self, responses, origin="http://127.0.0.1:8003"):
        with patch.dict(os.environ, {"BFF_GATEWAY_TOKEN": "a" * 64}), \
                patch.object(sys, "argv", ["smoke_test.py", "--base-url", origin]), \
                patch.object(smoke, "request", side_effect=responses) as request, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return smoke.main(), request

    def test_success_requires_auth_rejections_and_regions(self):
        result, request = self.run_smoke([(403, {}), (403, {}), (200, {"status": "success", "data": [{"name": "test"}]})])
        self.assertEqual(result, 0)
        self.assertEqual(request.call_count, 3)

    def test_http_200_with_error_envelope_is_failure(self):
        result, _ = self.run_smoke([(403, {}), (403, {}), (200, {"status": "error"})])
        self.assertEqual(result, 1)

    def test_gateway_bypass_is_failure(self):
        result, request = self.run_smoke([(200, {"status": "success"})])
        self.assertEqual(result, 1)
        self.assertEqual(request.call_count, 1)

    def test_public_plain_http_is_rejected_before_sending_secret(self):
        with self.assertRaises(SystemExit):
            self.run_smoke([], "http://backend.example.com")

    def test_redirects_do_not_forward_secret(self):
        self.assertIsNone(smoke.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))


if __name__ == "__main__":
    unittest.main()
