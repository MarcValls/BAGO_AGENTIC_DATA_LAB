from fastapi.testclient import TestClient
from src.api import server


def test_manual_is_curated_html_with_accessible_language_and_no_script_permissions(monkeypatch, tmp_path):
    source = tmp_path / "docs/public-web/MANUAL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Manual BAGO\n\n## Consultar una web\n\nRevisa el origen y confirma el permiso.\n", encoding="utf-8")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    response = TestClient(server.app).get("/manual")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="es">' in response.text
    assert "Consultar una web" in response.text
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_manual_missing_is_an_honest_error_without_path_disclosure(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    response = TestClient(server.app).get("/manual")
    assert response.status_code == 503
    assert str(tmp_path) not in response.text


def test_manual_cannot_read_a_query_selected_file(monkeypatch, tmp_path):
    source = tmp_path / "docs/public-web/MANUAL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Manual autorizado", encoding="utf-8")
    secret = tmp_path / "private.txt"
    secret.write_text("synthetic-secret-must-not-appear", encoding="utf-8")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    response = TestClient(server.app).get("/manual", params={"path": str(secret)})
    assert response.status_code == 200
    assert "Manual autorizado" in response.text
    assert secret.read_text() not in response.text


def test_reviewed_write_guide_is_fixed_and_linked_from_both_manuals(monkeypatch,tmp_path):
    for relative,title in [('docs/public-web/MANUAL.md','General autorizado'),('docs/agent-write/MANUAL_ES.md','Escritura autorizada')]:
        source=tmp_path/relative
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_text('# '+title,encoding='utf-8')
    secret=tmp_path/'secret.txt';secret.write_text('private-synthetic',encoding='utf-8')
    monkeypatch.setattr(server,'REPO_ROOT',tmp_path)
    client=TestClient(server.app)
    for route,title in [('/manual','General autorizado'),('/manual/escritura-revisada','Escritura autorizada')]:
        response=client.get(route,params={'path':str(secret)})
        assert response.status_code==200 and title in response.text
        assert 'href="/manual/escritura-revisada"' in response.text and 'href="/manual"' in response.text
        assert secret.read_text() not in response.text
        assert "default-src 'none'" in response.headers['content-security-policy']


def test_reviewed_write_guide_missing_is_not_a_general_manual_fallback(monkeypatch,tmp_path):
    monkeypatch.setattr(server,'REPO_ROOT',tmp_path)
    response=TestClient(server.app).get('/manual/escritura-revisada')
    assert response.status_code==503 and str(tmp_path) not in response.text
