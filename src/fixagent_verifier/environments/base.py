"""Base environment interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from fixagent_verifier.models.pr import PRInfo


@dataclass
class ExecResult:
    """Result of command execution in environment."""

    stdout: str
    stderr: str
    return_code: int
    duration_sec: float = 0.0


class BaseEnvironment(ABC):
    """Base class for execution environments."""

    @abstractmethod
    async def start(self, force_build: bool = False) -> None:
        """
        Start the environment (build and start container).

        Args:
            force_build: Force rebuild of Docker image
        """
        pass

    @abstractmethod
    async def stop(self, delete: bool = True) -> None:
        """
        Stop the environment.

        Args:
            delete: Whether to delete containers/volumes
        """
        pass

    @abstractmethod
    async def setup_pr_workspace(self, pr_info: PRInfo) -> None:
        """
        Setup PR workspace by cloning and merging.

        Args:
            pr_info: PR information
        """
        pass

    @abstractmethod
    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ExecResult:
        """
        Execute command in environment.

        Args:
            command: Command to execute
            cwd: Working directory
            env: Environment variables
            timeout_sec: Timeout in seconds

        Returns:
            ExecResult with stdout, stderr, and return code
        """
        pass

    @abstractmethod
    async def upload_file(self, source_path: Path, target_path: str) -> None:
        """
        Upload file to environment.

        Args:
            source_path: Local source file path
            target_path: Target path in environment
        """
        pass

    @abstractmethod
    async def download_file(self, source_path: str, target_path: Path) -> None:
        """
        Download file from environment.

        Args:
            source_path: Source path in environment
            target_path: Local target file path
        """
        pass
