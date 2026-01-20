"""Trial configuration and result models."""

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from fixagent_verifier.models.pr import PRInfo
from fixagent_verifier.models.task import TaskConfig


class EnvironmentConfig(BaseModel):
    """Docker environment configuration."""

    type: str = Field(default="docker", description="Environment type")
    cpus: int = Field(default=2, description="CPU cores")
    memory_mb: int = Field(default=4096, description="Memory in MB")
    allow_internet: bool = Field(default=True, description="Allow internet access")


class VerifierConfig(BaseModel):
    """Verifier configuration."""

    timeout_sec: float = Field(default=1800.0, description="Verification timeout")
    project_type: str = Field(default="gradle", description="Project type")
    custom_script: str | None = Field(default=None, description="Custom verification script")


class TrialConfig(BaseModel):
    """Configuration for a single verification trial."""

    trial_id: UUID = Field(default_factory=uuid4, description="Unique trial ID")
    trial_name: str = Field(..., description="Human-readable trial name")
    task: TaskConfig = Field(..., description="Task configuration")
    pr_info: PRInfo = Field(..., description="PR information")
    environment: EnvironmentConfig = Field(..., description="Environment config")
    verifier: VerifierConfig = Field(..., description="Verifier config")
    output_dir: Path = Field(default=Path("results"), description="Output directory")
    retry_attempts: int = Field(default=2, description="Number of retry attempts")


class VerificationResult(BaseModel):
    """Result of compilation/test verification."""

    success: bool = Field(..., description="Did verification succeed?")
    compilation_output: str = Field(default="", description="stdout/stderr from compilation")
    duration_sec: float = Field(..., description="Verification duration in seconds")
    error_message: str | None = Field(default=None, description="Error message if failed")
    tasks_run: list[str] = Field(default_factory=list, description="Build tasks executed")


class ExceptionInfo(BaseModel):
    """Exception information if trial failed."""

    exception_type: str
    exception_message: str
    traceback: str


class TrialResult(BaseModel):
    """Result of a verification trial."""

    trial_id: UUID = Field(..., description="Trial ID")
    trial_name: str = Field(..., description="Trial name")
    task_id: str = Field(..., description="Task ID")
    pr_url: str = Field(..., description="PR URL")
    pr_number: int = Field(..., description="PR number")

    verification_result: VerificationResult | None = Field(
        default=None, description="Verification result"
    )
    exception_info: ExceptionInfo | None = Field(
        default=None, description="Exception info if failed"
    )

    started_at: datetime | None = Field(default=None, description="Trial start time")
    finished_at: datetime | None = Field(default=None, description="Trial finish time")

    trial_dir: Path = Field(..., description="Trial output directory")

    @property
    def duration_sec(self) -> float | None:
        """Calculate trial duration."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def success(self) -> bool:
        """Check if trial succeeded."""
        return (
            self.exception_info is None
            and self.verification_result is not None
            and self.verification_result.success
        )
