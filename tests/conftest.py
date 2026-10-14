"""Keep the suite off the network. Collectors receive fakes in their own tests."""

import pytest
import requests


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def deny(*args, **kwargs):
        raise requests.ConnectionError("network disabled in tests")

    monkeypatch.setattr("newspaper.http.requests.get", deny)
    monkeypatch.setattr("newspaper.http.requests.post", deny)
