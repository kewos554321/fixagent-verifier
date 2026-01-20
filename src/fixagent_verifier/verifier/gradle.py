"""Gradle project verifier."""

import time

from fixagent_verifier.environments.base import BaseEnvironment
from fixagent_verifier.models.trial import VerificationResult
from fixagent_verifier.verifier.base import BaseVerifier


class GradleVerifier(BaseVerifier):
    """Verifier for Gradle-based projects."""

    async def verify(
        self, environment: BaseEnvironment, timeout_sec: float = 1800.0
    ) -> VerificationResult:
        """
        Verify Gradle project compilation.

        Steps:
        1. Check for gradle wrapper (./gradlew)
        2. Run compilation: ./gradlew clean build -x test --no-daemon
        3. Capture output and check success
        """
        start_time = time.time()
        tasks_run = []

        try:
            # Check for gradle wrapper
            wrapper_check = await environment.exec(
                "test -f ./gradlew && echo 'yes' || echo 'no'", timeout_sec=10
            )

            if "yes" in wrapper_check.stdout:
                gradle_cmd = "./gradlew"
                # Make wrapper executable
                chmod_result = await environment.exec("chmod +x ./gradlew", timeout_sec=10)
                if chmod_result.return_code != 0:
                    return VerificationResult(
                        success=False,
                        compilation_output=chmod_result.stderr,
                        duration_sec=time.time() - start_time,
                        error_message="Failed to make gradlew executable",
                        tasks_run=[],
                    )
            else:
                gradle_cmd = "gradle"

            # Run clean build (excluding tests for POC)
            tasks_run = ["clean", "build"]
            build_cmd = f"{gradle_cmd} clean build -x test --no-daemon --stacktrace"

            result = await environment.exec(build_cmd, timeout_sec=timeout_sec)

            duration = time.time() - start_time
            success = result.return_code == 0

            return VerificationResult(
                success=success,
                compilation_output=result.stdout + "\n" + result.stderr,
                duration_sec=duration,
                error_message=None if success else "Compilation failed - see output",
                tasks_run=tasks_run,
            )

        except Exception as e:
            duration = time.time() - start_time
            return VerificationResult(
                success=False,
                compilation_output=str(e),
                duration_sec=duration,
                error_message=f"Verification exception: {str(e)}",
                tasks_run=tasks_run,
            )
