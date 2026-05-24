"""Contract tests: verify SSE event shapes match docs/API_CONTRACT.md."""

import json

import pytest
from fastapi.testclient import TestClient

from twin_mind.api.app import create_app
from twin_mind.api.state import state
from twin_mind.config import settings


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    body = body.replace("\r\n", "\n")
    events: list[tuple[str, dict]] = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        ev = None
        data = None
        for line in frame.splitlines():
            if line.startswith("event:"):
                ev = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        if ev and data:
            events.append((ev, json.loads(data)))
    return events


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch, fake_llm, tmp_path):
    (tmp_path / "x.md").write_text("# Title\n\n## Role\n\nChing-En built an ingestion pipeline.\n")
    monkeypatch.setattr(settings, "SAMPLES_DIR", str(tmp_path))
    # Keep contract tests fast and offline — never hit BGE or the persistent Chroma dir.
    monkeypatch.setattr(settings, "EMBEDDER", "stub")
    monkeypatch.setattr(settings, "VECTORSTORE", "in_memory")
    # Default reranker is "claude" which requires ANTHROPIC_API_KEY at construction
    # time. Contract tests must run offline, so swap to identity.
    monkeypatch.setattr(settings, "RERANKER", "identity")
    state.retriever = None
    state._llm = fake_llm
    yield


def test_chat_emits_meta_token_citation_done():
    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/chat",
        json={"message": "What did Ching-En do?"},
        headers={"Authorization": "Bearer dev-key"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [t for t, _ in events]

    assert types[0] == "meta"
    meta = events[0][1]
    assert "request_id" in meta and "retrieved" in meta
    for r in meta["retrieved"]:
        assert set(r.keys()) >= {"id", "source", "section", "score", "url"}

    assert "token" in types
    assert "citation" in types
    assert types[-1] == "done"

    done = events[-1][1]
    assert set(done.keys()) >= {
        "refused",
        "refusal_reason",
        "tokens_in",
        "tokens_out",
        "cost_usd",
    }


def test_chat_unauthorized_without_key():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/v1/chat", json={"message": "hi"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_chat_rejects_too_long_message():
    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/chat",
        json={"message": "x" * 501},
        headers={"Authorization": "Bearer dev-key"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_healthz_open():
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
