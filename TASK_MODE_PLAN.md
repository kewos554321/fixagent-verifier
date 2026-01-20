# FixAgent Verifier - Task Mode Architecture Plan

## Executive Summary

Based on Terminal-Bench's simpler architecture, we can refactor FixAgent Verifier to use a **task-based model** where each PR becomes a self-contained task. This approach offers better organization, reproducibility, and alignment with established benchmarking patterns.

## Why Task Mode is Better

### Current Architecture Issues

Our current implementation:
```python
# Everything is procedural
pr_info = await github_client.get_pr_info(pr_url)
environment = DockerEnvironment(...)
await environment.start()
await environment.setup_pr_workspace(pr_info)
result = await verifier.verify(environment)
```

**Problems:**
1. No persistent task representation
2. Hard to cache/reuse verification setups
3. Difficult to resume failed verifications
4. No standard task format for sharing
5. Mixed concerns (PR fetching + verification)

### Task-Based Architecture Benefits

Terminal-Bench's approach:
```
tasks/pr-{number}/
├── task.yaml          # Self-contained metadata
├── Dockerfile         # Environment setup
├── run-tests.sh       # Verification logic
└── tests/
    └── test_compilation.py
```

**Benefits:**
1. ✓ **Self-contained**: Each PR is a complete, shareable task
2. ✓ **Reproducible**: Dockerfile pins environment
3. ✓ **Cacheable**: Can reuse task directories
4. ✓ **Resumable**: Lock files track progress
5. ✓ **Testable**: Standard test.sh interface
6. ✓ **Extensible**: Easy to add new project types
7. ✓ **Shareable**: Tasks can be distributed as datasets

---

## Architecture Comparison

### Current (Procedural)

```
User → CLI → GitHub API → Docker → Git Clone → Gradle → Results
                    ↓
                 (everything ephemeral)
```

### Proposed (Task-Based)

```
User → CLI → Task Generator → Task Directory
                                  ↓
                          [Persistent Task]
                                  ↓
              Harness → Docker → run-tests.sh → Results
                                  ↑
                          (reusable, shareable)
```

---

## Proposed Architecture

### 1. Task Structure

Each PR verification becomes a task:

```
tasks/
├── pr-123__owner-repo/
│   ├── task.yaml              # PR metadata + config
│   ├── Dockerfile             # Environment setup
│   ├── docker-compose.yaml    # Container orchestration
│   ├── run-tests.sh          # Verification script
│   ├── tests/
│   │   └── test_compilation.py  # pytest verification
│   └── .lock                  # Resume support
└── pr-456__other-repo/
    └── ...
```

#### task.yaml Format

```yaml
# Task metadata
task_id: "pr-123__owner-repo"
task_type: "pr-verification"
created_at: "2026-01-20T10:00:00Z"

# PR information
pr:
  number: 123
  url: "https://github.com/owner/repo/pull/123"
  title: "Fix authentication bug"

  repo:
    owner: "owner"
    name: "repo"
    clone_url: "https://github.com/owner/repo.git"

  target:
    branch: "main"
    commit: "abc123def"

  source:
    branch: "feature-branch"
    commit: "xyz789abc"

# Project configuration
project:
  type: "gradle"  # or "maven"
  language: "java"
  jdk_version: 17
  gradle_version: "8.5"  # optional

# Execution settings
execution:
  max_test_timeout_sec: 1800.0
  allow_internet: true
  cpus: 2
  memory_mb: 4096

# Instructions for verification
instruction: |
  This task verifies PR #123 for owner/repo.

  The PR changes authentication logic. Verify that:
  1. The code compiles successfully after merging
  2. No new compilation errors are introduced

  Expected result: Successful compilation with ./gradlew clean build

# Verification criteria
verification:
  compilation_required: true
  unit_tests_required: false  # Phase 2
  integration_tests_required: false  # Phase 3

# Metadata
metadata:
  author_name: "FixAgent Verifier"
  difficulty: "medium"
  category: "pr-verification"
  tags: ["java", "gradle", "spring-boot"]
  estimated_duration_sec: 300
```

#### Dockerfile Template

```dockerfile
FROM eclipse-temurin:{{jdk_version}}-jdk-jammy

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Gradle (if not using wrapper)
{% if gradle_version %}
RUN curl -fsSL https://services.gradle.org/distributions/gradle-{{gradle_version}}-bin.zip -o /tmp/gradle.zip \
    && unzip /tmp/gradle.zip -d /opt \
    && ln -s /opt/gradle-{{gradle_version}}/bin/gradle /usr/local/bin/gradle \
    && rm /tmp/gradle.zip
{% endif %}

# Set Git config
RUN git config --global user.email "fixagent@verifier.local" \
    && git config --global user.name "FixAgent Verifier"

WORKDIR /workspace

CMD ["sleep", "infinity"]
```

#### run-tests.sh

```bash
#!/bin/bash
set -e

TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="/workspace"

echo "=== FixAgent Verifier - PR Verification ==="
echo "Task: $(basename $TASK_DIR)"
echo "Workspace: $WORKSPACE"
echo ""

# Parse task.yaml to get PR info
PR_NUMBER=$(yq eval '.pr.number' "$TASK_DIR/task.yaml")
REPO_URL=$(yq eval '.pr.repo.clone_url' "$TASK_DIR/task.yaml")
TARGET_BRANCH=$(yq eval '.pr.target.branch' "$TASK_DIR/task.yaml")
TARGET_COMMIT=$(yq eval '.pr.target.commit' "$TASK_DIR/task.yaml")

echo "PR: #$PR_NUMBER"
echo "Repository: $REPO_URL"
echo "Target: $TARGET_BRANCH @ $TARGET_COMMIT"
echo ""

# Step 1: Clone repository
echo "==> Cloning repository..."
git clone --depth=1 --branch "$TARGET_BRANCH" "$REPO_URL" "$WORKSPACE"
cd "$WORKSPACE"

# Step 2: Fetch PR and target commit
echo "==> Fetching PR and commits..."
git fetch --depth=50 origin "$TARGET_COMMIT"
git fetch origin "pull/$PR_NUMBER/head:pr-source"

# Step 3: Checkout target commit
echo "==> Checking out target commit..."
git checkout "$TARGET_COMMIT"

# Step 4: Create merge branch
echo "==> Creating mock merge branch..."
git checkout -b mock-merge

# Step 5: Merge PR (allow conflicts)
echo "==> Merging PR..."
git merge pr-source --no-commit --no-edit || {
    echo "WARNING: Merge conflicts detected"
    # Continue anyway - verifier will catch compilation failures
}

# Step 6: Run compilation
echo ""
echo "==> Running verification..."

# Detect gradle wrapper
if [ -f "./gradlew" ]; then
    GRADLE_CMD="./gradlew"
    chmod +x ./gradlew
else
    GRADLE_CMD="gradle"
fi

# Run gradle build (excluding tests for POC)
$GRADLE_CMD clean build -x test --no-daemon --stacktrace

EXIT_CODE=$?

# Step 7: Write result
mkdir -p /logs/verifier

if [ $EXIT_CODE -eq 0 ]; then
    echo "1" > /logs/verifier/result.txt
    echo ""
    echo "=== VERIFICATION PASSED ==="
else
    echo "0" > /logs/verifier/result.txt
    echo ""
    echo "=== VERIFICATION FAILED ==="
fi

exit $EXIT_CODE
```

#### tests/test_compilation.py

```python
"""pytest verification tests for PR compilation."""

import subprocess
from pathlib import Path


def test_gradle_build_succeeded():
    """Test that Gradle build completed successfully."""
    # Check for build artifacts
    build_dir = Path("/workspace/build")
    assert build_dir.exists(), "Build directory does not exist"

    # Check for compiled classes
    classes_dir = build_dir / "classes" / "java" / "main"
    if classes_dir.exists():
        assert any(classes_dir.rglob("*.class")), "No compiled classes found"


def test_no_compilation_errors():
    """Test that there are no compilation errors in logs."""
    log_file = Path("/logs/verifier/result.txt")
    assert log_file.exists(), "Result file not found"

    result = log_file.read_text().strip()
    assert result == "1", f"Compilation failed (result: {result})"


def test_gradle_wrapper_executable():
    """Test that gradle wrapper is properly configured."""
    wrapper = Path("/workspace/gradlew")
    if wrapper.exists():
        assert wrapper.stat().st_mode & 0o111, "gradlew not executable"
```

---

### 2. Task Generator

Automatically generates task directories from PR URLs:

```python
# task_generator/pr_generator.py

from pathlib import Path
from datetime import datetime
import yaml
from jinja2 import Template

class PRTaskGenerator:
    """Generates task directories for PR verification."""

    def __init__(self, tasks_dir: Path = Path("tasks")):
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(exist_ok=True)

    async def generate_from_pr_url(self, pr_url: str) -> Path:
        """
        Generate a task directory from a PR URL.

        Args:
            pr_url: GitHub PR URL

        Returns:
            Path to generated task directory
        """
        # 1. Fetch PR info from GitHub
        github_client = GitHubClient()
        pr_info = await github_client.get_pr_info(pr_url)

        # 2. Create task directory
        task_id = f"pr-{pr_info.pr_number}__{pr_info.repo_owner}-{pr_info.repo_name}"
        task_dir = self.tasks_dir / task_id
        task_dir.mkdir(exist_ok=True)

        # 3. Generate task.yaml
        task_yaml = self._generate_task_yaml(pr_info)
        (task_dir / "task.yaml").write_text(yaml.dump(task_yaml, sort_keys=False))

        # 4. Generate Dockerfile
        dockerfile = self._generate_dockerfile(pr_info.project_type)
        (task_dir / "Dockerfile").write_text(dockerfile)

        # 5. Copy run-tests.sh template
        run_tests = self._get_run_tests_template(pr_info.project_type)
        run_tests_path = task_dir / "run-tests.sh"
        run_tests_path.write_text(run_tests)
        run_tests_path.chmod(0o755)

        # 6. Generate docker-compose.yaml
        compose = self._generate_docker_compose(task_id)
        (task_dir / "docker-compose.yaml").write_text(compose)

        # 7. Create tests directory with pytest tests
        tests_dir = task_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_compilation.py").write_text(
            self._get_test_template(pr_info.project_type)
        )

        return task_dir

    def _generate_task_yaml(self, pr_info: PRInfo) -> dict:
        """Generate task.yaml content."""
        return {
            "task_id": f"pr-{pr_info.pr_number}__{pr_info.repo_owner}-{pr_info.repo_name}",
            "task_type": "pr-verification",
            "created_at": datetime.now().isoformat(),
            "pr": {
                "number": pr_info.pr_number,
                "url": pr_info.pr_url,
                "title": pr_info.title,
                "repo": {
                    "owner": pr_info.repo_owner,
                    "name": pr_info.repo_name,
                    "clone_url": pr_info.clone_url,
                },
                "target": {
                    "branch": pr_info.target_branch,
                    "commit": pr_info.target_commit,
                },
                "source": {
                    "branch": pr_info.source_branch,
                    "commit": pr_info.source_commit,
                },
            },
            "project": {
                "type": "gradle",  # Auto-detect in Phase 2
                "language": "java",
                "jdk_version": 17,
            },
            "execution": {
                "max_test_timeout_sec": 1800.0,
                "allow_internet": True,
                "cpus": 2,
                "memory_mb": 4096,
            },
            "instruction": f"Verify PR #{pr_info.pr_number} for {pr_info.repo_owner}/{pr_info.repo_name}\n\n"
                          f"This task verifies that the PR merges cleanly and compiles successfully.",
            "verification": {
                "compilation_required": True,
                "unit_tests_required": False,
                "integration_tests_required": False,
            },
            "metadata": {
                "author_name": "FixAgent Verifier",
                "difficulty": "medium",
                "category": "pr-verification",
                "tags": ["java", "gradle"],
                "estimated_duration_sec": 300,
            },
        }
```

---

### 3. Harness (Simplified from Terminal-Bench)

Execute tasks with parallel support:

```python
# harness/harness.py

import asyncio
from pathlib import Path
from uuid import uuid4
from rich.console import Console
from rich.progress import Progress

class PRVerificationHarness:
    """Harness for running PR verification tasks."""

    def __init__(
        self,
        tasks_dir: Path,
        output_dir: Path,
        n_concurrent: int = 4,
        task_ids: list[str] | None = None,
    ):
        self.tasks_dir = tasks_dir
        self.output_dir = output_dir
        self.n_concurrent = n_concurrent
        self.task_ids = task_ids
        self.console = Console()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> list[VerificationResult]:
        """Run all tasks with parallel execution."""

        # 1. Discover tasks
        tasks = self._discover_tasks()

        if not tasks:
            self.console.print("[red]No tasks found![/red]")
            return []

        self.console.print(f"[bold]Found {len(tasks)} tasks to verify[/bold]\n")

        # 2. Run tasks in parallel with semaphore
        semaphore = asyncio.Semaphore(self.n_concurrent)
        results = []

        with Progress() as progress:
            task_progress = progress.add_task(
                "[cyan]Verifying PRs...", total=len(tasks)
            )

            async with asyncio.TaskGroup() as tg:
                for task_dir in tasks:
                    async def run_task(td):
                        result = await self._run_single_task(td, semaphore)
                        results.append(result)
                        progress.update(task_progress, advance=1)

                    tg.create_task(run_task(task_dir))

        # 3. Display summary
        self._display_summary(results)

        return results

    def _discover_tasks(self) -> list[Path]:
        """Discover task directories."""
        if self.task_ids:
            # Specific tasks
            return [
                self.tasks_dir / task_id
                for task_id in self.task_ids
                if (self.tasks_dir / task_id).exists()
            ]
        else:
            # All tasks
            return [
                d for d in self.tasks_dir.iterdir()
                if d.is_dir() and (d / "task.yaml").exists()
            ]

    async def _run_single_task(
        self, task_dir: Path, semaphore: asyncio.Semaphore
    ) -> VerificationResult:
        """Run a single task with concurrency control."""

        async with semaphore:
            trial_id = uuid4()
            trial_dir = self.output_dir / f"{task_dir.name}__{trial_id}"
            trial_dir.mkdir(parents=True, exist_ok=True)

            # 1. Load task config
            task_config = self._load_task_config(task_dir)

            # 2. Start Docker environment
            environment = await self._start_environment(task_dir, trial_dir)

            try:
                # 3. Run tests
                result = await self._run_tests(environment, task_dir, task_config)

                # 4. Save results
                self._save_results(trial_dir, result)

                return result

            finally:
                # 5. Cleanup
                await environment.stop(delete=True)

    async def _start_environment(
        self, task_dir: Path, trial_dir: Path
    ) -> DockerEnvironment:
        """Start Docker environment using task's Dockerfile."""

        # Build image if needed
        image_name = f"fixagent-pr:{task_dir.name}"

        # Check if image exists
        client = docker.from_env()
        try:
            client.images.get(image_name)
        except docker.errors.ImageNotFound:
            # Build from task Dockerfile
            client.images.build(
                path=str(task_dir),
                tag=image_name,
                rm=True,
            )

        # Start container
        environment = DockerEnvironment(
            container_name=f"fixagent-{trial_dir.name}",
            image_name=image_name,
            working_dir="/workspace",
        )
        await environment.start()

        # Mount logs directory
        # (For simplicity, we'll use docker cp instead)

        return environment

    async def _run_tests(
        self,
        environment: DockerEnvironment,
        task_dir: Path,
        task_config: dict,
    ) -> VerificationResult:
        """Run the task's test script."""

        # Upload run-tests.sh and task.yaml to container
        await environment.upload_file(
            task_dir / "run-tests.sh", "/tmp/run-tests.sh"
        )
        await environment.upload_file(
            task_dir / "task.yaml", "/tmp/task.yaml"
        )

        # Execute run-tests.sh
        timeout = task_config["execution"]["max_test_timeout_sec"]
        result = await environment.exec(
            "bash /tmp/run-tests.sh",
            timeout_sec=timeout,
        )

        # Download results
        # Check if /logs/verifier/result.txt exists
        try:
            result_content = await environment.exec(
                "cat /logs/verifier/result.txt"
            )
            success = "1" in result_content.stdout
        except:
            success = result.return_code == 0

        return VerificationResult(
            task_id=task_config["task_id"],
            pr_number=task_config["pr"]["number"],
            pr_url=task_config["pr"]["url"],
            success=success,
            output=result.stdout + result.stderr,
            duration_sec=result.duration_sec,
        )
```

---

### 4. CLI Updates

```python
# cli/main.py (updated)

@app.command()
def generate(
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL"),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
):
    """
    Generate a task directory for a PR.

    Example:
        fixagent-verifier generate --pr-url https://github.com/owner/repo/pull/123
    """
    console.print("[bold]Generating task from PR...[/bold]")

    generator = PRTaskGenerator(tasks_dir)
    task_dir = asyncio.run(generator.generate_from_pr_url(pr_url))

    console.print(f"[green]✓ Task generated: {task_dir}[/green]")


@app.command()
def run(
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    output_dir: Path = typer.Option(Path("results"), "--output-dir", help="Output directory"),
    task_ids: list[str] = typer.Option(None, "--task-id", help="Specific task IDs"),
    n_concurrent: int = typer.Option(4, "--concurrent", "-c", help="Concurrent tasks"),
):
    """
    Run PR verification tasks.

    Examples:
        # Run all tasks
        fixagent-verifier run

        # Run specific tasks
        fixagent-verifier run --task-id pr-123__owner-repo --task-id pr-456__other-repo

        # Run with more concurrency
        fixagent-verifier run --concurrent 8
    """
    console.print("[bold blue]FixAgent Verifier - Task Mode[/bold blue]\n")

    harness = PRVerificationHarness(
        tasks_dir=tasks_dir,
        output_dir=output_dir,
        n_concurrent=n_concurrent,
        task_ids=task_ids,
    )

    results = asyncio.run(harness.run())

    # Exit with error if any failed
    if any(not r.success for r in results):
        raise typer.Exit(1)


@app.command()
def tasks_list(
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
):
    """List available tasks."""

    tasks = [
        d for d in tasks_dir.iterdir()
        if d.is_dir() and (d / "task.yaml").exists()
    ]

    if not tasks:
        console.print("[yellow]No tasks found[/yellow]")
        return

    table = Table(title="Available Tasks")
    table.add_column("Task ID", style="cyan")
    table.add_column("PR", style="magenta")
    table.add_column("Repository", style="green")
    table.add_column("Type", style="yellow")

    for task_dir in tasks:
        config = yaml.safe_load((task_dir / "task.yaml").read_text())
        table.add_row(
            config["task_id"],
            f"#{config['pr']['number']}",
            f"{config['pr']['repo']['owner']}/{config['pr']['repo']['name']}",
            config["project"]["type"],
        )

    console.print(table)


@app.command()
def quick(
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL"),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
    output_dir: Path = typer.Option(Path("results"), "--output-dir", help="Output directory"),
):
    """
    Quick mode: Generate task and run immediately.

    Example:
        fixagent-verifier quick --pr-url https://github.com/owner/repo/pull/123
    """
    # Generate task
    console.print("[bold]1. Generating task...[/bold]")
    generator = PRTaskGenerator(tasks_dir)
    task_dir = asyncio.run(generator.generate_from_pr_url(pr_url))
    console.print(f"   ✓ {task_dir.name}\n")

    # Run task
    console.print("[bold]2. Running verification...[/bold]")
    harness = PRVerificationHarness(
        tasks_dir=tasks_dir,
        output_dir=output_dir,
        n_concurrent=1,
        task_ids=[task_dir.name],
    )
    results = asyncio.run(harness.run())

    if not results[0].success:
        raise typer.Exit(1)
```

---

### 5. PR Registry Format (Batch Generation)

```yaml
# pr-registry.yaml

name: "spring-boot-prs"
description: "Spring Boot PRs for verification"
version: "1.0"

settings:
  n_concurrent: 4
  output_dir: "results"
  tasks_dir: "tasks"

prs:
  - pr_url: "https://github.com/spring-projects/spring-boot/pull/12345"
    priority: "high"

  - pr_url: "https://github.com/spring-projects/spring-boot/pull/12346"
    priority: "medium"

  - pr_url: "https://github.com/kewos554321/springboot-aws-k8s/pull/1"
    priority: "low"
```

**Batch generation:**

```python
@app.command()
def generate_from_registry(
    registry: Path = typer.Option(..., "--registry", help="PR registry YAML file"),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir", help="Tasks directory"),
):
    """
    Generate multiple tasks from a PR registry.

    Example:
        fixagent-verifier generate-from-registry --registry pr-registry.yaml
    """
    registry_data = yaml.safe_load(registry.read_text())

    generator = PRTaskGenerator(tasks_dir)

    with Progress() as progress:
        task_progress = progress.add_task(
            "[cyan]Generating tasks...",
            total=len(registry_data["prs"])
        )

        for pr_entry in registry_data["prs"]:
            task_dir = asyncio.run(
                generator.generate_from_pr_url(pr_entry["pr_url"])
            )
            console.print(f"   ✓ {task_dir.name}")
            progress.update(task_progress, advance=1)

    console.print(f"\n[green]✓ Generated {len(registry_data['prs'])} tasks[/green]")
```

---

## Implementation Phases

### Phase 1: Task Generation (Week 1)

**Goals:**
- Generate task directories from PR URLs
- YAML config generation
- Dockerfile templating
- run-tests.sh creation

**Tasks:**
- [ ] Implement `PRTaskGenerator` class
- [ ] Create Jinja2 templates for Dockerfile, run-tests.sh
- [ ] Add `fixagent-verifier generate` command
- [ ] Test task generation with 5 real PRs

**Deliverables:**
- Can generate task directories from PR URLs
- Generated tasks have all required files
- Task YAML is valid and complete

---

### Phase 2: Harness Implementation (Week 2)

**Goals:**
- Execute tasks in Docker
- Parallel execution with semaphore
- Result collection and reporting

**Tasks:**
- [ ] Implement `PRVerificationHarness` class
- [ ] Docker environment integration
- [ ] run-tests.sh execution
- [ ] Result parsing from /logs/verifier/result.txt
- [ ] Add `fixagent-verifier run` command

**Deliverables:**
- Can execute generated tasks
- Parallel execution works (n_concurrent)
- Results are collected and saved

---

### Phase 3: Resume Support & Advanced Features (Week 3)

**Goals:**
- Lock files for resume support
- Task caching
- Registry batch operations

**Tasks:**
- [ ] Implement lock file mechanism
- [ ] Add `fixagent-verifier resume` command
- [ ] Task caching (skip already verified tasks)
- [ ] Batch generation from registry
- [ ] Rich progress bars and UI

**Deliverables:**
- Can resume interrupted runs
- Registry-based batch verification works
- Beautiful CLI with progress tracking

---

## Migration Path

### From Current Implementation

```python
# Old way (current)
uv run fixagent-verifier run-single --pr-url <url>

# New way (task mode)
uv run fixagent-verifier quick --pr-url <url>

# Or two-step
uv run fixagent-verifier generate --pr-url <url>
uv run fixagent-verifier run --task-id pr-123__owner-repo
```

### Backward Compatibility

Keep old `run-single` command as alias:

```python
@app.command()
def run_single(pr_url: str, ...):
    """Legacy command - use 'quick' instead."""
    console.print("[yellow]Note: run-single is deprecated. Use 'quick' instead.[/yellow]\n")
    # Delegate to quick()
    quick(pr_url=pr_url, ...)
```

---

## Benefits Summary

### 1. Reproducibility
- Task directories are self-contained
- Can share tasks with others
- Version control friendly

### 2. Caching & Performance
- Don't rebuild Docker images for same project type
- Can skip already-verified PRs
- Parallel execution is trivial

### 3. Extensibility
- Easy to add Maven support (just new template)
- Custom verification scripts per project
- Plugin system for parsers

### 4. Debugging
- Each task is isolated
- Can manually inspect/rerun tasks
- Logs are organized by task

### 5. Distribution
- Tasks can be distributed as datasets
- Community can contribute tasks
- Standard format for PR verification

---

## Comparison: Current vs Task Mode

| Aspect | Current (Procedural) | Task Mode |
|--------|---------------------|-----------|
| **Structure** | Ephemeral, procedural | Persistent task directories |
| **Reusability** | Must re-fetch PR each time | Task cached, reusable |
| **Sharing** | Can't share verifications | Can share task directories |
| **Resume** | Not supported | Lock files enable resume |
| **Debugging** | Hard to reproduce | Task dir contains everything |
| **Extensibility** | Hard to add project types | Template-based, easy to extend |
| **Batch Operations** | Sequential only | Registry-based batching |
| **Parallelism** | Complex to implement | Natural with task isolation |

---

## Recommended Decision

**YES**, adopt task-based architecture for these reasons:

1. **Alignment with Standards**: Terminal-Bench and Harbor both use task-based models
2. **Better Organization**: Each PR verification is self-contained
3. **Improved UX**: Users can inspect, rerun, share tasks
4. **Easier Testing**: Each task can be unit tested
5. **Future-Proof**: Easier to add features (caching, resume, etc.)
6. **Community**: Standard format enables task sharing

**Trade-offs:**
- More initial complexity (task generation step)
- Disk space for task directories
- Two-step process (generate + run) vs one-step

**Mitigation:**
- Provide `quick` command for one-step workflow
- Keep backward-compatible `run-single` command
- Task cleanup command for disk management

---

## Next Steps

1. **Review this plan** with team/users
2. **Implement Phase 1** (task generation)
3. **Test with 10 real PRs** from different repos
4. **Gather feedback** and iterate
5. **Implement Phase 2 & 3** based on learnings

---

## Conclusion

Task-based architecture is **strongly recommended** for FixAgent Verifier. It provides:
- Better alignment with established patterns (Terminal-Bench, Harbor)
- Improved reproducibility and sharing
- Natural support for advanced features (caching, resume, batching)
- Cleaner code organization

The migration path is clear, backward compatibility is maintained, and the benefits significantly outweigh the added complexity.
