"""Tiny stdlib-only JSON HTTP client with cookies, retries and readiness waits."""

from __future__ import annotations

import json
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class Http:
    def __init__(self, base: str, headers: dict | None = None, name: str = ""):
        self.base = base.rstrip("/")
        self.headers = dict(headers or {})
        self.name = name or base
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method, path, body=None, params=None, form=None, headers=None, timeout=60):
        url = self.base + path
        if params:
            url += "?" + urlencode(params, doseq=True)
        hdrs = {"Accept": "application/json", **self.headers, **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode()
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=data, method=method, headers=hdrs)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                payload = resp.read()
        except HTTPError as e:
            text = e.read().decode(errors="replace")
            raise ApiError(f"{self.name}: {method} {path} -> HTTP {e.code}: {text[:400]}", e.code, text) from None
        if not payload:
            return None
        try:
            return json.loads(payload)
        except ValueError:
            return payload.decode(errors="replace")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body=body, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def wait(self, path: str, timeout: int = 600, accept=(200,)) -> None:
        """Block until `path` answers with an accepted status code."""
        deadline = time.monotonic() + timeout
        last = "no answer"
        while time.monotonic() < deadline:
            try:
                self.get(path, timeout=10)
                return
            except ApiError as e:
                if e.status in accept:
                    return
                last = f"HTTP {e.status}"
            except (URLError, ConnectionError, TimeoutError, OSError) as e:
                last = str(getattr(e, "reason", e))
            time.sleep(3)
        raise ApiError(f"{self.name} not ready after {timeout}s ({last})")
