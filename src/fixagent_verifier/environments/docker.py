"""Docker environment implementation."""

import asyncio
import time
from pathlib import Path
from textwrap import dedent

import docker
from docker.errors import DockerException
from docker.models.containers import Container

from fixagent_verifier.environments.base import BaseEnvironment, ExecResult
from fixagent_verifier.models.pr import PRInfo


class DockerEnvironment(BaseEnvironment):
    """Docker-based isolated environment for PR verification."""

    def __init__(
        self,
        container_name: str,
        image_name: str,
        cpus: int = 2,
        memory_mb: int = 4096,
        allow_internet: bool = True,
        working_dir: str = "/workspace",
    ):
        """
        Initialize Docker environment.

        Args:
            container_name: Name for the container
            image_name: Docker image name
            cpus: Number of CPU cores
            memory_mb: Memory limit in MB
            allow_internet: Whether to allow internet access
            working_dir: Working directory in container
        """
        self.container_name = container_name
        self.image_name = image_name
        self.cpus = cpus
        self.memory_mb = memory_mb
        self.allow_internet = allow_internet
        self.working_dir = working_dir

        self.client = docker.from_env()
        self.container: Container | None = None

    async def start(self, force_build: bool = False) -> None:
        """Start the Docker container."""
        # Check if image exists, build if needed
        try:
            self.client.images.get(self.image_name)
            if force_build:
                raise docker.errors.ImageNotFound("Force rebuild")
        except docker.errors.ImageNotFound:
            # Image needs to be built - will be handled by user providing Dockerfile
            # For now, we'll assume image exists or use a base image
            pass

        # Network mode
        network_mode = "bridge" if self.allow_internet else "none"

        # Stop existing container with same name if exists
        try:
            existing = self.client.containers.get(self.container_name)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start container
        self.container = self.client.containers.run(
            image=self.image_name,
            name=self.container_name,
            command="sleep infinity",
            detach=True,
            network_mode=network_mode,
            cpu_count=self.cpus,
            mem_limit=f"{self.memory_mb}m",
            working_dir=self.working_dir,
            remove=False,
        )

        # Wait for container to be ready
        await asyncio.sleep(2)

    async def stop(self, delete: bool = True) -> None:
        """Stop and optionally delete the container."""
        if self.container:
            try:
                self.container.stop(timeout=10)
                if delete:
                    self.container.remove()
            except DockerException:
                pass
            self.container = None

    async def setup_pr_workspace(self, pr_info: PRInfo) -> None:
        """
        Setup PR workspace by cloning target repo and merging PR.

        Steps:
        1. Clone target repository at target branch
        2. Checkout target commit
        3. Fetch PR branch
        4. Create mock merge branch
        5. Merge PR branch (without committing)
        """
        if not self.container:
            raise RuntimeError("Container not started")

        # Clone target repository
        clone_cmd = f"""
        git clone --depth=1 --branch {pr_info.target_branch} \
            {pr_info.target_repo_url} {self.working_dir}
        """
        result = await self.exec(clone_cmd.strip(), cwd="/")
        if result.return_code != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

        # Fetch full history for target and source commits
        fetch_cmd = f"""
        git fetch --depth=50 origin {pr_info.target_commit} && \
        git fetch origin pull/{pr_info.pr_number}/head:pr-source
        """
        result = await self.exec(fetch_cmd.strip())
        if result.return_code != 0:
            raise RuntimeError(f"Failed to fetch PR: {result.stderr}")

        # Checkout target commit
        checkout_cmd = f"git checkout {pr_info.target_commit}"
        result = await self.exec(checkout_cmd)
        if result.return_code != 0:
            raise RuntimeError(f"Failed to checkout target commit: {result.stderr}")

        # Create mock merge branch
        branch_cmd = "git checkout -b mock-merge"
        result = await self.exec(branch_cmd)
        if result.return_code != 0:
            raise RuntimeError(f"Failed to create merge branch: {result.stderr}")

        # Merge PR branch (allow merge conflicts for now)
        merge_cmd = "git merge pr-source --no-commit --no-edit || true"
        result = await self.exec(merge_cmd)
        # Don't fail on merge conflicts - verifier will catch compilation failures

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ExecResult:
        """Execute command in Docker container."""
        if not self.container:
            raise RuntimeError("Container not started")

        work_dir = cwd or self.working_dir
        environment = env or {}

        start_time = time.time()

        try:
            # Execute command
            exec_result = self.container.exec_run(
                f'bash -c "{command}"',
                workdir=work_dir,
                environment=environment,
                demux=True,
            )

            duration = time.time() - start_time

            stdout = exec_result.output[0].decode() if exec_result.output[0] else ""
            stderr = exec_result.output[1].decode() if exec_result.output[1] else ""

            return ExecResult(
                stdout=stdout,
                stderr=stderr,
                return_code=exec_result.exit_code,
                duration_sec=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return ExecResult(
                stdout="",
                stderr=str(e),
                return_code=1,
                duration_sec=duration,
            )

    async def upload_file(self, source_path: Path, target_path: str) -> None:
        """Upload file to container using docker cp."""
        if not self.container:
            raise RuntimeError("Container not started")

        # Use docker cp command
        cmd = f"docker cp {source_path} {self.container_name}:{target_path}"
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

    async def download_file(self, source_path: str, target_path: Path) -> None:
        """Download file from container using docker cp."""
        if not self.container:
            raise RuntimeError("Container not started")

        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Use docker cp command
        cmd = f"docker cp {self.container_name}:{source_path} {target_path}"
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

    async def build_image(self, dockerfile_path: Path, context_dir: Path) -> None:
        """
        Build Docker image from Dockerfile.

        Args:
            dockerfile_path: Path to Dockerfile
            context_dir: Build context directory
        """
        self.client.images.build(
            path=str(context_dir),
            dockerfile=str(dockerfile_path.relative_to(context_dir)),
            tag=self.image_name,
            rm=True,
        )
