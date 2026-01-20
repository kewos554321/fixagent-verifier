"""GitHub API client for fetching PR information."""

import os
import re
from typing import Any

import httpx

from fixagent_verifier.models.pr import PRInfo


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str | None = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub API token. If None, reads from GITHUB_TOKEN env var.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _parse_pr_url(self, pr_url: str) -> tuple[str, str, int]:
        """
        Parse PR URL to extract owner, repo, and PR number.

        Args:
            pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)

        Returns:
            Tuple of (owner, repo, pr_number)

        Raises:
            ValueError: If URL format is invalid
        """
        pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.search(pattern, pr_url)
        if not match:
            raise ValueError(f"Invalid GitHub PR URL: {pr_url}")

        owner, repo, pr_number = match.groups()
        return owner, repo, int(pr_number)

    async def get_pr_info(self, pr_url: str) -> PRInfo:
        """
        Fetch PR information from GitHub API.

        Args:
            pr_url: GitHub PR URL

        Returns:
            PRInfo object with PR details

        Raises:
            httpx.HTTPError: If API request fails
        """
        owner, repo, pr_number = self._parse_pr_url(pr_url)

        async with httpx.AsyncClient() as client:
            # Fetch PR details
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            pr_data: dict[str, Any] = response.json()

            # Extract PR information
            return PRInfo(
                pr_url=pr_url,
                repo_owner=owner,
                repo_name=repo,
                pr_number=pr_number,
                source_branch=pr_data["head"]["ref"],
                source_commit=pr_data["head"]["sha"],
                source_repo_url=pr_data["head"]["repo"]["clone_url"]
                if pr_data["head"]["repo"]
                else pr_data["base"]["repo"]["clone_url"],
                target_branch=pr_data["base"]["ref"],
                target_commit=pr_data["base"]["sha"],
                target_repo_url=pr_data["base"]["repo"]["clone_url"],
                title=pr_data["title"],
                state=pr_data["state"],
            )

    def get_clone_url(self, owner: str, repo: str) -> str:
        """
        Get HTTPS clone URL for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Clone URL
        """
        return f"https://github.com/{owner}/{repo}.git"
