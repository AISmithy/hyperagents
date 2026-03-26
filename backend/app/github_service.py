from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


class GitHubService:
    _API_BASE = "https://api.github.com"

    def __init__(self, token: str = "") -> None:
        self._token = token

    def fetch_repo_summary(self, repo_url: str) -> dict[str, Any]:
        owner, repo = self._parse_url(repo_url)

        meta = self._get(f"/repos/{owner}/{repo}")
        languages = self._get(f"/repos/{owner}/{repo}/languages")
        contents = self._get(f"/repos/{owner}/{repo}/contents/")
        readme = self._fetch_readme(owner, repo)

        root_files = [
            item["name"]
            for item in (contents if isinstance(contents, list) else [])
        ][:30]

        return {
            "owner": owner,
            "repo": repo,
            "url": repo_url,
            "description": meta.get("description") or "",
            "language": meta.get("language") or "",
            "languages": list(languages.keys()) if isinstance(languages, dict) else [],
            "stars": meta.get("stargazers_count", 0),
            "open_issues": meta.get("open_issues_count", 0),
            "default_branch": meta.get("default_branch", "main"),
            "topics": meta.get("topics", []),
            "root_files": root_files,
            "readme_excerpt": readme[:3000] if readme else "",
        }

    def list_user_repos(self, username: str, max_repos: int = 20) -> list[dict]:
        """Return public repos for a GitHub user or org (metadata only, no content fetch)."""
        data = self._get(f"/users/{username}/repos?per_page={max_repos}&sort=updated&type=public")
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response for user {username!r}: {type(data)}")
        return [
            {
                "name": r.get("name", ""),
                "html_url": r.get("html_url", ""),
                "description": r.get("description") or "",
                "stargazers_count": r.get("stargazers_count", 0),
                "open_issues_count": r.get("open_issues_count", 0),
                "archived": r.get("archived", False),
                "has_wiki": r.get("has_wiki", False),
                "has_pages": r.get("has_pages", False),
                "topics": r.get("topics") or [],
                "language": r.get("language") or "",
            }
            for r in data
        ]

    def _parse_url(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url.strip().rstrip("/"))
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"Cannot parse GitHub URL: {url!r}. Expected https://github.com/owner/repo")
        return parts[0], parts[1]

    def _get(self, path: str) -> Any:
        url = f"{self._API_BASE}{path}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "hyperagents/1.0")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(f"GitHub API {exc.code} for {path}: {body[:200]}") from exc
        except OSError as exc:
            raise RuntimeError(f"Network error fetching {path}: {exc}") from exc

    def _fetch_readme(self, owner: str, repo: str) -> str:
        try:
            data = self._get(f"/repos/{owner}/{repo}/readme")
            content = data.get("content", "")
            encoding = data.get("encoding", "base64")
            if encoding == "base64":
                return base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
            return content
        except Exception:
            return ""
