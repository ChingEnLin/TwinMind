"""GitHub repo loader.

Pulls READMEs (and optionally top-level ``docs/*.md``) plus repo metadata
for every public repo of a configured user, minus a denylist.

Design notes:
- We do not stream large code files; only markdown. Code embeds poorly with
  general-purpose embedders and would balloon the corpus.
- Each Document's text is prefixed with a metadata block (description,
  topics, language, stars, last push) so keyword queries like "what
  language is X written in?" can hit the metadata via BM25 even if the
  README doesn't mention it.
- Document IDs are namespaced ``github/{owner}/{repo}/<path>`` so they
  cannot collide with the local-docs loader.
- Source.url points at the canonical view link
  ``https://github.com/{owner}/{repo}/blob/HEAD/<path>`` so citations can
  link out.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

from twin_mind.config import settings
from twin_mind.logging import get_logger
from twin_mind.models.document import Document, Source

logger = get_logger(__name__)

_API = "https://api.github.com"
_PER_PAGE = 100


@dataclass
class _RepoInfo:
    name: str
    full_name: str  # "owner/repo"
    owner: str
    description: str
    topics: list[str]
    language: str
    stars: int
    pushed_at: str
    default_branch: str


class GitHubRepoLoader:
    """Fetches READMEs and metadata for a GitHub user's public repos."""

    name = "github"

    def __init__(
        self,
        user: str | None = None,
        token: str | None = None,
        denylist: list[str] | None = None,
        include_docs: bool | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.user = user or settings.GITHUB_USER
        self.token = token if token is not None else settings.GITHUB_TOKEN
        self.denylist = set(denylist if denylist is not None else settings.GITHUB_DENYLIST)
        self.include_docs = (
            include_docs if include_docs is not None else settings.GITHUB_INCLUDE_DOCS
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "twin-mind/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Allow injection for tests; otherwise build a real client.
        self._client = client or httpx.Client(headers=headers, timeout=20.0)
        self._owns_client = client is None

    # --- public API ---

    def load(self) -> Iterable[Document]:
        if not self.token:
            raise RuntimeError(
                "GITHUB_TOKEN is not set — refusing to ingest GitHub unauthenticated. "
                "Add a Personal Access Token with `public_repo` scope to .env."
            )
        try:
            for repo in self._list_repos():
                if repo.name in self.denylist:
                    logger.info("github: skipping denylisted repo %s", repo.full_name)
                    continue
                yield from self._load_repo(repo)
        finally:
            if self._owns_client:
                self._client.close()

    # --- internals ---

    def _request(self, path: str) -> httpx.Response:
        """GET with rate-limit awareness. Sleeps if the remaining budget is tiny."""
        url = path if path.startswith("http") else f"{_API}{path}"
        resp = self._client.get(url)
        # Defensive: if we're about to hit zero, pause until the window resets.
        remaining = int(resp.headers.get("X-RateLimit-Remaining") or 1000)
        if remaining <= 1:
            reset = int(resp.headers.get("X-RateLimit-Reset") or 0)
            sleep_for = max(0, reset - int(time.time())) + 1
            if sleep_for > 0:
                logger.warning("github: rate limit near zero, sleeping %ds", sleep_for)
                time.sleep(sleep_for)
        return resp

    def _list_repos(self) -> Iterable[_RepoInfo]:
        page = 1
        while True:
            resp = self._request(
                f"/users/{self.user}/repos?per_page={_PER_PAGE}&page={page}&type=public&sort=updated"
            )
            resp.raise_for_status()
            items = resp.json()
            if not items:
                return
            for it in items:
                # Skip forks unless they were updated recently with our content. Cheap heuristic.
                if it.get("fork"):
                    continue
                yield _RepoInfo(
                    name=it["name"],
                    full_name=it["full_name"],
                    owner=it["owner"]["login"],
                    description=(it.get("description") or "").strip(),
                    topics=list(it.get("topics") or []),
                    language=(it.get("language") or "").strip(),
                    stars=int(it.get("stargazers_count") or 0),
                    pushed_at=(it.get("pushed_at") or "")[:10],
                    default_branch=it.get("default_branch") or "main",
                )
            if len(items) < _PER_PAGE:
                return
            page += 1

    def _metadata_block(self, repo: _RepoInfo) -> str:
        topics = ", ".join(repo.topics) if repo.topics else "(none)"
        return (
            f"Repo: {repo.name}\n"
            f"Owner: {repo.owner}\n"
            f"Description: {repo.description or '(none)'}\n"
            f"Topics: {topics}\n"
            f"Primary language: {repo.language or '(unknown)'}\n"
            f"Stars: {repo.stars}\n"
            f"Last pushed: {repo.pushed_at or '(unknown)'}\n"
        )

    def _view_url(self, repo: _RepoInfo, path: str) -> str:
        return f"https://github.com/{repo.full_name}/blob/{repo.default_branch}/{path}"

    def _doc_id(self, repo: _RepoInfo, path: str) -> str:
        return f"github/{repo.full_name}/{path}"

    def _fetch_readme(self, repo: _RepoInfo) -> tuple[str, str] | None:
        """Return (path, decoded_text) or None if no README."""
        resp = self._request(f"/repos/{repo.full_name}/readme")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        path = data.get("path") or "README.md"
        content = data.get("content") or ""
        # GitHub returns base64 with newlines.
        text = base64.b64decode(content).decode("utf-8", errors="replace")
        return path, text

    def _fetch_docs_dir(self, repo: _RepoInfo) -> Iterable[tuple[str, str]]:
        """Yield (path, text) for top-level docs/*.md if a docs/ directory exists."""
        resp = self._request(f"/repos/{repo.full_name}/contents/docs")
        if resp.status_code == 404:
            return
        resp.raise_for_status()
        entries = resp.json()
        if not isinstance(entries, list):
            return
        for entry in entries:
            if entry.get("type") != "file":
                continue
            name = entry.get("name") or ""
            if not name.lower().endswith((".md", ".markdown")):
                continue
            dl = entry.get("download_url")
            if not dl:
                continue
            r = self._request(dl)
            if r.status_code != 200:
                continue
            yield entry.get("path") or f"docs/{name}", r.text

    def _load_repo(self, repo: _RepoInfo) -> Iterable[Document]:
        readme = self._fetch_readme(repo)
        if readme is None and not repo.description and not repo.topics:
            logger.info("github: %s has no README or metadata, skipping", repo.full_name)
            return

        meta = self._metadata_block(repo)
        readme_path = readme[0] if readme else "README.md"
        readme_text = readme[1] if readme else "(no README provided)"
        composite = f"{meta}\n---\n\n{readme_text}"
        yield Document(
            id=self._doc_id(repo, readme_path),
            source=Source(
                name=f"{repo.full_name}/{readme_path}",
                url=self._view_url(repo, readme_path),
            ),
            text=composite,
            metadata={
                "github": True,
                "repo": repo.full_name,
                "stars": repo.stars,
                "language": repo.language,
            },
        )

        if self.include_docs:
            for path, text in self._fetch_docs_dir(repo):
                yield Document(
                    id=self._doc_id(repo, path),
                    source=Source(
                        name=f"{repo.full_name}/{path}",
                        url=self._view_url(repo, path),
                    ),
                    text=text,
                    metadata={
                        "github": True,
                        "repo": repo.full_name,
                        "path": path,
                    },
                )
