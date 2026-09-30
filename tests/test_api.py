"""Веб-сервис: сторонний пользователь проходит весь путь и получает файлы."""
import pytest

pytest.importorskip("cadquery")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_page_and_families():
    assert client.get("/").status_code == 200
    keys = [f["key"] for f in client.get("/api/families").json()["families"]]
    assert keys == ["plate", "angle", "channel", "zprofile"]


def test_full_calculation_gives_files():
    body = {"family": "channel", "values": {"A": 60, "B": 40, "C": 25, "S": 2, "R": None, "U": None},
            "material": "soft_steel", "series_per_year": 25000,
            "holes": [{"face": "base", "kind": "round", "d": 10.5, "x": 20, "y": 30},
                      {"face": "flange_2", "kind": "slot", "length": 14, "width": 7, "s": 30, "e": 8, "angle": 0}]}
    r = client.post("/api/calculate", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["blank"]["w"] == pytest.approx(82.29, abs=0.01) and d["formed"] == [40.0, 60.0, 25.0]
    assert d["recommended"] in {"A", "B", "C"}
    for url in list(d["files"].values()) + [d["iso"]]:
        assert client.get(url).status_code == 200


def test_input_error_is_readable():
    r = client.post("/api/calculate", json={"family": "angle", "values": {"A": 100, "B": 40, "C": 1, "S": 2},
                                            "material": "soft_steel"})
    assert r.status_code == 400 and "C = 1" in r.json()["detail"]


def test_files_cannot_escape_job_folder():
    assert client.get("/files/abc/..%2F..%2Fetc%2Fpasswd").status_code == 404


JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


def test_photos_are_accepted_and_bundled():
    sid = client.post("/api/session").json()["session"]
    assert client.post(f"/api/session/{sid}/photo/top", content=JPEG).status_code == 200
    assert client.post(f"/api/session/{sid}/photo/side", content=JPEG).status_code == 200
    assert client.delete(f"/api/session/{sid}/photo/side").status_code == 200
    body = {"family": "plate", "values": {"A": 80, "B": 50, "S": 3}, "material": "soft_steel", "session": sid}
    d = client.post("/api/calculate", json=body).json()
    assert d["job"] == sid and d["photos"] == ["Сверху"]
    assert client.get(d["files"]["photos"]).status_code == 200


def test_bad_photos_are_refused():
    sid = client.post("/api/session").json()["session"]
    assert client.post(f"/api/session/{sid}/photo/top", content=b"MZ not an image").status_code == 400
    assert client.post(f"/api/session/{sid}/photo/nope", content=JPEG).status_code == 400
    assert client.post(f"/api/session/{sid}/photo/top", content=JPEG + b"0" * (6 * 1024 * 1024)).status_code == 413
    assert client.post("/api/session/zzzz/photo/top", content=JPEG).status_code == 404
