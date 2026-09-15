"""End-to-end checks of the bridge over real HTTP, no device required."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iphone_tk.bridge.server import create_app
from iphone_tk.bridge.token import resolve_token

TOKEN = "test-token-value"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "inbox", TOKEN))


def test_status_endpoint_reports_the_inbox(client: TestClient) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["service"] == "iphone-tk bridge"


def test_home_without_a_token_does_not_expose_the_uploader(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 401
    assert "Almost there" in response.text
    assert TOKEN not in response.text


def test_home_with_a_wrong_token_is_refused(client: TestClient) -> None:
    response = client.get("/", params={"t": "wrong"})
    assert response.status_code == 401
    assert TOKEN not in response.text


def test_home_with_the_token_serves_the_uploader(client: TestClient) -> None:
    response = client.get("/", params={"t": TOKEN})
    assert response.status_code == 200
    assert "Send to PC" in response.text
    # The page posts on the phone's behalf, so it must carry the token.
    assert TOKEN in response.text


def test_uploader_page_escapes_the_token_into_the_attribute(tmp_path: Path) -> None:
    from iphone_tk.bridge.server import create_app as build

    nasty = 'a"><script>x</script>'
    client = TestClient(build(tmp_path / "inbox", nasty))
    response = client.get("/", params={"t": nasty})
    assert response.status_code == 200
    assert "<script>x</script>" not in response.text


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


def test_a_saved_link_still_opens_after_a_restart(tmp_path: Path) -> None:
    """The regression this whole token file exists for.

    Before the token was persisted, every start minted a new one, so the link
    the phone saved to its home screen authenticated exactly once and then fell
    back to the help page forever.
    """
    token_file = tmp_path / "bridge-token"

    # First start: the user adds the printed link to the home screen.
    first_token, _ = resolve_token(path=token_file)
    saved_link = f"/?t={first_token}"
    first_run = TestClient(create_app(tmp_path / "inbox", first_token))
    assert first_run.get(saved_link).status_code == 200

    # Second start, fresh process, same saved link.
    second_token, _ = resolve_token(path=token_file)
    second_run = TestClient(create_app(tmp_path / "inbox", second_token))
    assert second_run.get(saved_link).status_code == 200

    # Rotating on purpose must still invalidate it.
    rotated_token, _ = resolve_token(path=token_file, rotate=True)
    rotated_run = TestClient(create_app(tmp_path / "inbox", rotated_token))
    assert rotated_run.get(saved_link).status_code == 401
