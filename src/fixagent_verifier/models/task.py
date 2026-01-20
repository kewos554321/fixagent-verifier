"""Task configuration models."""

from pydantic import BaseModel, Field


class TaskConfig(BaseModel):
    """Configuration for a PR verification task."""

    task_id: str = Field(..., description="Unique task identifier")
    pr_url: str = Field(..., description="GitHub PR URL")
    project_type: str = Field(default="gradle", description="Project type (gradle, maven)")

    # Timeouts and resources
    timeout_sec: float = Field(default=1800.0, description="Verification timeout (30 min)")
    cpus: int = Field(default=2, description="CPU cores to allocate")
    memory_mb: int = Field(default=4096, description="Memory in MB")
    allow_internet: bool = Field(default=True, description="Allow internet access for deps")

    # Optional custom verification
    custom_verify_script: str | None = Field(
        default=None, description="Path to custom verification script"
    )

    # Priority
    priority: str = Field(default="medium", description="Task priority (low, medium, high)")
