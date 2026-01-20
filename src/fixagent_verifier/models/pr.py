"""PR information models."""

from pydantic import BaseModel, Field


class PRInfo(BaseModel):
    """Information about a GitHub Pull Request."""

    pr_url: str = Field(..., description="Full PR URL")
    repo_owner: str = Field(..., description="Repository owner/organization")
    repo_name: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="PR number")

    source_branch: str = Field(..., description="PR source branch name")
    source_commit: str = Field(..., description="Source branch commit SHA")
    source_repo_url: str = Field(..., description="Source repository clone URL")

    target_branch: str = Field(..., description="PR target branch (e.g., main)")
    target_commit: str = Field(..., description="Target branch commit SHA")
    target_repo_url: str = Field(..., description="Target repository clone URL")

    title: str = Field(..., description="PR title")
    state: str = Field(..., description="PR state (open, closed, merged)")

    @property
    def clone_url(self) -> str:
        """Get HTTPS clone URL for target repository."""
        return self.target_repo_url
