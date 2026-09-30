"""Check D -> B through /ui/regions without paid calls or database writes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the gateway secret to a redirect destination.
        return None


def request(base: str, token: str | None) -> tuple[int, dict]:
    headers = {"x-bff-token": token} if token else {}
    req = Request(base.rstrip("/") + "/ui/regions", headers=headers)
    try:
        with build_opener(NoRedirect).open(req, timeout=35) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    args = parser.parse_args()
    base = urlsplit(args.base_url)
    if (base.scheme not in {"http", "https"} or not base.hostname
            or base.username or base.password or base.path not in {"", "/"}
            or base.query or base.fragment
            or (base.scheme == "http" and base.hostname not in {"127.0.0.1", "localhost", "::1"})):
        parser.error("use an HTTPS origin, or HTTP loopback for a local check")
    token = os.environ.get("BFF_GATEWAY_TOKEN", "")
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        print("FAIL: valid BFF_GATEWAY_TOKEN must be injected through EnvironmentFile", file=sys.stderr)
        return 1
    try:
        for name, supplied in [("missing token", None), ("wrong token", "invalid-" + token)]:
            code, _ = request(args.base_url, supplied)
            if code != 403:
                raise ValueError(f"{name}: expected HTTP 403, got {code}")
            print(f"PASS: {name} rejected")
        code, body = request(args.base_url, token)
        if (code != 200 or not isinstance(body, dict) or body.get("status") != "success"
                or not isinstance(body.get("data"), list) or not body["data"]):
            raise ValueError("valid token: expected a success envelope with non-empty regions")
        print("PASS: authenticated /ui/regions, including D -> B")
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        # Do not print response bodies, headers, credentials or driver errors.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        print(f"FAIL: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
