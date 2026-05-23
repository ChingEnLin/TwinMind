"""GitHub loader tests with a hand-rolled httpx mock transport.

No live network. We mock the three endpoints the loader touches:
- ``/users/{user}/repos`` for listing
- ``/repos/{full}/readme`` for the README
- ``/repos/{full}/contents/docs`` for the optional docs/ traversal
"""

import base64

import httpx
import pytest

from twin_mind.ingestion.github_repos import GitHubRepoLoader


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode()


def _make_transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.query:
            # exact match including query for paginated listing
            full = f"{path}?{request.url.query.decode()}"
            if full in responses:
                return responses[full]
        if path in responses:
            return responses[path]
        return httpx.Response(404, json={"message": "not found"})

    return httpx.MockTransport(handler)


def _build_client(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=transport, base_url="https://api.github.com")


def test_loader_yields_readme_and_metadata_block():
    responses = {
        "/users/ChingEnLin/repos?per_page=100&page=1&type=public&sort=updated": httpx.Response(
            200,
            json=[
                {
                    "name": "QueryPal",
                    "full_name": "ChingEnLin/QueryPal",
                    "owner": {"login": "ChingEnLin"},
                    "description": "NL-to-SQL assistant",
                    "topics": ["rag", "fastapi"],
                    "language": "Python",
                    "stargazers_count": 7,
                    "pushed_at": "2026-04-12T10:00:00Z",
                    "default_branch": "main",
                    "fork": False,
                }
            ],
            headers={"X-RateLimit-Remaining": "5000"},
        ),
        "/repos/ChingEnLin/QueryPal/readme": httpx.Response(
            200,
            json={"path": "README.md", "content": _b64("QueryPal is an NL→SQL tool.")},
        ),
        "/repos/ChingEnLin/QueryPal/contents/docs": httpx.Response(404),
    }
    client = _build_client(_make_transport(responses))
    loader = GitHubRepoLoader(token="test-token", denylist=[], client=client)

    docs = list(loader.load())
    assert len(docs) == 1
    d = docs[0]
    assert d.id == "github/ChingEnLin/QueryPal/README.md"
    assert "QueryPal is an NL→SQL tool." in d.text
    # Metadata block is prefixed and BM25-friendly:
    assert "Primary language: Python" in d.text
    assert "Topics: rag, fastapi" in d.text
    assert "Stars: 7" in d.text
    # Citation URL points at GitHub:
    assert d.source.url == "https://github.com/ChingEnLin/QueryPal/blob/main/README.md"
    assert d.source.name == "ChingEnLin/QueryPal/README.md"


def test_loader_respects_denylist():
    responses = {
        "/users/ChingEnLin/repos?per_page=100&page=1&type=public&sort=updated": httpx.Response(
            200,
            json=[
                {
                    "name": "KuaMongous",
                    "full_name": "ChingEnLin/KuaMongous",
                    "owner": {"login": "ChingEnLin"},
                    "description": "",
                    "topics": [],
                    "language": "",
                    "stargazers_count": 0,
                    "pushed_at": "",
                    "default_branch": "main",
                    "fork": False,
                }
            ],
        ),
    }
    client = _build_client(_make_transport(responses))
    loader = GitHubRepoLoader(token="test-token", denylist=["KuaMongous"], client=client)
    assert list(loader.load()) == []


def test_loader_walks_docs_dir_when_present():
    responses = {
        "/users/ChingEnLin/repos?per_page=100&page=1&type=public&sort=updated": httpx.Response(
            200,
            json=[
                {
                    "name": "Foo",
                    "full_name": "ChingEnLin/Foo",
                    "owner": {"login": "ChingEnLin"},
                    "description": "x",
                    "topics": [],
                    "language": "Go",
                    "stargazers_count": 0,
                    "pushed_at": "2026-01-01T00:00:00Z",
                    "default_branch": "main",
                    "fork": False,
                }
            ],
        ),
        "/repos/ChingEnLin/Foo/readme": httpx.Response(
            200, json={"path": "README.md", "content": _b64("body")}
        ),
        "/repos/ChingEnLin/Foo/contents/docs": httpx.Response(
            200,
            json=[
                {
                    "name": "guide.md",
                    "path": "docs/guide.md",
                    "type": "file",
                    "download_url": "https://raw.githubusercontent.com/ChingEnLin/Foo/main/docs/guide.md",
                },
                {
                    "name": "image.png",
                    "path": "docs/image.png",
                    "type": "file",
                    "download_url": "x",
                },
            ],
        ),
        # The download_url is fetched directly:
        "/ChingEnLin/Foo/main/docs/guide.md": httpx.Response(200, text="# Guide\n\nbody"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        # Allow the raw.githubusercontent.com URL through too.
        if request.url.host == "raw.githubusercontent.com":
            if request.url.path == "/ChingEnLin/Foo/main/docs/guide.md":
                return httpx.Response(200, text="# Guide\n\nbody")
            return httpx.Response(404)
        path = request.url.path
        if request.url.query:
            full = f"{path}?{request.url.query.decode()}"
            if full in responses:
                return responses[full]
        return responses.get(path, httpx.Response(404))

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    loader = GitHubRepoLoader(token="test-token", denylist=[], include_docs=True, client=client)
    docs = list(loader.load())
    ids = sorted(d.id for d in docs)
    assert ids == [
        "github/ChingEnLin/Foo/README.md",
        "github/ChingEnLin/Foo/docs/guide.md",
    ]


def test_loader_refuses_without_token():
    loader = GitHubRepoLoader(token="", denylist=[])
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        list(loader.load())
