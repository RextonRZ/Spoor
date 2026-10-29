from fastapi.testclient import TestClient

from spoor.api.app import create_app
from spoor.config import Settings


def test_healthz(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, model_api_key=None, agent_backend="none"))
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok" and resp.json()["sam"] is False


def test_blank_env_values_mean_unset():
    s = Settings(_env_file=None, model_api_key="", url_signing_secret=" ", database_url="", users_file="")
    assert s.model_api_key is None and s.url_signing_secret is None
    assert s.database_url is None and s.users_file is None
