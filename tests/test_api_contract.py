import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from jobsearcher.web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(create_app())


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unimplemented_routes_return_contract_error():
    r = client.get("/api/profile/files")
    assert r.status_code == 501
    assert r.json() == {
        "detail": "Endepunktet er ikke implementert ennå.",
        "code": "not_implemented",
    }


def test_exported_openapi_is_up_to_date():
    spec = importlib.util.spec_from_file_location(
        "export_openapi", ROOT / "scripts" / "export_openapi.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (ROOT / "web" / "openapi.json").read_text(
        encoding="utf-8"
    ) == mod.render(), (
        "web/openapi.json er utdatert: kjør `uv run python scripts/export_openapi.py`"
    )
