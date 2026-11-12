import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The plugin runs from its root directory, so the tests do the same.
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


class FakeResponse:
    def __init__(self, status_code, body=None, content=b"", content_type="application/json"):
        self.status_code = status_code
        self._body = body
        self.content = content
        self.text = content.decode("utf-8", "replace") if isinstance(content, bytes) else ""
        self.headers = {"Content-Type": content_type}

    def json(self):
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


class FakeHTTP:
    """Replaces requests.request. It records each call and returns queued responses."""

    def __init__(self):
        self.calls = []
        self.responses = []

    def reply(self, status_code, body=None, content=b"", content_type="application/json"):
        self.responses.append(FakeResponse(status_code, body, content, content_type))

    def raise_error(self, error):
        self.responses.append(error)

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "params": params, "json": json, "headers": headers, "timeout": timeout}
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def http(monkeypatch):
    import huntapi_api

    fake = FakeHTTP()
    monkeypatch.setattr(huntapi_api.requests, "request", fake)
    return fake
