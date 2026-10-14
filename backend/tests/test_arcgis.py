import httpx
import pytest

from app.sources import arcgis


def client_answering(*statuses: int) -> tuple[httpx.Client, list[int]]:
    served: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses[min(len(served), len(statuses) - 1)]
        served.append(status)
        return httpx.Response(status, json={"features": [], "ok": True} if status == 200 else None)

    return httpx.Client(transport=httpx.MockTransport(handler)), served


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(arcgis.time, "sleep", lambda _seconds: None)


@pytest.mark.parametrize("transient", [304, 500, 503])
def test_get_json_retries_transient_status(transient):
    client, served = client_answering(transient, 200)
    assert arcgis._get_json(client, "https://example.test/query", {})["ok"] is True
    assert served == [transient, 200]


def test_get_json_gives_up_after_all_attempts():
    client, served = client_answering(503)
    with pytest.raises(httpx.HTTPStatusError):
        arcgis._get_json(client, "https://example.test/query", {}, attempts=3)
    assert served == [503, 503, 503]


def test_get_json_does_not_retry_client_error():
    client, served = client_answering(404)
    with pytest.raises(httpx.HTTPStatusError):
        arcgis._get_json(client, "https://example.test/query", {})
    assert served == [404]
