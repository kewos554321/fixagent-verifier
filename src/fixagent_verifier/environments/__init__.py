"""Environment implementations for isolated execution."""

from fixagent_verifier.environments.base import BaseEnvironment, ExecResult
from fixagent_verifier.environments.docker import DockerEnvironment

__all__ = ["BaseEnvironment", "ExecResult", "DockerEnvironment"]
