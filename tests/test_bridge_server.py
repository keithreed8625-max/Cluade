"""End-to-end checks of the bridge over real HTTP, no device required."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iphone_tk.bridge.server import create_app

TOKEN = "test-token-value"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "inbox", TOKEN))


def test_status_endpoint_reports_the_inbox(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "iphone-tk bridge"


def test_text_requires_a_token(client: TestClient) -> None:
    assert client.post("/text", data={"text": "hi"}).status_code == 401


def test_text_rejects_a_wrong_token(client: TestClient) -> None:
    response = client.post("/text", data={"text": "hi"}, headers={"X-Token": "nope"})
    assert response.status_code == 401


def test_text_is_saved_with_a_header_token(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/text", data={"text": "hello"}, headers={"X-Token": TOKEN})
    assert response.status_code == 200
    saved = (tmp_path / "inbox" / response.json()["saved"])
    assert saved.read_text() == "hello"


def test_text_accepts_the_token_as_a_form_field(client: TestClient) -> None:
    # Shortcuts' simpler actions send everything as form fields.
    response = client.post("/text", data={"text": "hello", "token": TOKEN})
    assert response.status_code == 200


def test_upload_saves_a_file_and_sanitizes_its_name(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/upload",
        files={"file": ("../../escape.heic", b"\x00\x01binary", "image/heic")},
        headers={"X-Token": TOKEN},
    )
    assert response.status_code == 200
    name = response.json()["saved"]
    assert ".." not in name and "/" not in name
    assert (tmp_path / "inbox" / name).read_bytes() == b"\x00\x01binary"


def test_upload_requires_a_token(client: TestClient) -> None:
    response = client.post("/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert response.status_code == 401


def test_oversized_upload_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import iphone_tk.bridge.server as server

    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 16)
    client = TestClient(server.create_app(tmp_path / "inbox", TOKEN))
    response = client.post(
        "/upload",
        files={"file": ("big.bin", b"x" * 64, "application/octet-stream")},
        headers={"X-Token": TOKEN},
    )
    assert response.status_code == 413
