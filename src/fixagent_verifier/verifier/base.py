"""Base verifier interface."""

from abc import ABC, abstractmethod

from fixagent_verifier.environments.base import BaseEnvironment
from fixagent_verifier.models.trial import VerificationResult


class BaseVerifier(ABC):
    """Base class for project verifiers."""

    @abstractmethod
    async def verify(
        self, environment: BaseEnvironment, timeout_sec: float = 1800.0
    ) -> VerificationResult:
        """
        Verify project compilation/tests.

        Args:
            environment: Execution environment
            timeout_sec: Verification timeout

        Returns:
            VerificationResult with success status and details
        """
        pass
