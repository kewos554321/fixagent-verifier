"""Trial execution utilities."""

import json
import traceback
from datetime import datetime
from pathlib import Path

from fixagent_verifier.environments.docker import DockerEnvironment
from fixagent_verifier.models.trial import ExceptionInfo, TrialConfig, TrialResult
from fixagent_verifier.verifier.gradle import GradleVerifier


async def run_trial(config: TrialConfig) -> TrialResult:
    """
    Execute a single PR verification trial.

    Args:
        config: Trial configuration

    Returns:
        TrialResult with verification outcome
    """
    trial_dir = config.output_dir / str(config.trial_id)
    trial_dir.mkdir(parents=True, exist_ok=True)

    result = TrialResult(
        trial_id=config.trial_id,
        trial_name=config.trial_name,
        task_id=config.task.task_id,
        pr_url=config.pr_info.pr_url,
        pr_number=config.pr_info.pr_number,
        trial_dir=trial_dir,
        started_at=datetime.now(),
    )

    # Save trial config
    config_path = trial_dir / "config.json"
    config_path.write_text(
        config.model_dump_json(indent=2, exclude={"output_dir"}), encoding="utf-8"
    )

    environment = None

    try:
        # 1. Create Docker environment
        environment = DockerEnvironment(
            container_name=f"fixagent-{config.trial_id}",
            image_name="fixagent-verifier:java-gradle",
            cpus=config.environment.cpus,
            memory_mb=config.environment.memory_mb,
            allow_internet=config.environment.allow_internet,
        )

        # 2. Start environment
        await environment.start()

        # 3. Setup PR workspace (clone and merge)
        await environment.setup_pr_workspace(config.pr_info)

        # 4. Run verifier
        verifier = GradleVerifier()
        result.verification_result = await verifier.verify(
            environment, timeout_sec=config.verifier.timeout_sec
        )

    except Exception as e:
        # Capture exception details
        result.exception_info = ExceptionInfo(
            exception_type=type(e).__name__,
            exception_message=str(e),
            traceback=traceback.format_exc(),
        )

        # Save exception to file
        exception_path = trial_dir / "exception.txt"
        exception_path.write_text(traceback.format_exc(), encoding="utf-8")

    finally:
        # 5. Cleanup environment
        if environment:
            try:
                await environment.stop(delete=True)
            except Exception:
                pass

        # 6. Finalize result
        result.finished_at = datetime.now()

        # Save result
        result_path = trial_dir / "result.json"
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        # Save verification output if available
        if result.verification_result:
            output_path = trial_dir / "compilation.log"
            output_path.write_text(
                result.verification_result.compilation_output, encoding="utf-8"
            )

    return result
