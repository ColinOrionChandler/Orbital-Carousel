"""Keep the ordinary test suite independent of remote ephemeris services."""

import pytest
import requests


@pytest.fixture(autouse=True)
def block_http_requests(monkeypatch):
    """Fail immediately if a test accidentally attempts an HTTP request."""

    def fail_request(*args, **kwargs):
        raise AssertionError("Unit tests must mock remote HTTP requests")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)
