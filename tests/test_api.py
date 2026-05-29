from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "AI Act Deliberation Explainer" in res.text


def test_analyze():
    res = client.post("/api/analyze", json={"text": "Municipality X wants to use an AI system to rank social housing applications. The model uses historical welfare data. A human officer can approve the final decision, but applicants will not see the score."})
    assert res.status_code == 200
    data = res.json()
    assert "preliminary legal-design analysis" in data["disclaimer"]
    assert any(r["label"] == "opacity" for r in data["possible_risks"])
