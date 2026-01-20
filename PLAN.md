# FixAgent Verifier - Implementation Plan

## Overview

A CLI tool for automated PR verification through isolated Docker environments. The tool will fetch PRs from GitHub, simulate merges in isolated containers, and verify compilation status (initially Java/SpringBoot Gradle projects).

## Architecture Design (Based on Harbor)

```
fixagent-verifier/
├── src/
│   ├── cli/                    # CLI interface (Typer-based)
│   │   ├── main.py            # Main entry point
│   │   ├── run.py             # Run verification jobs
│   │   ├── jobs.py            # Job management
│   │   └── tasks.py           # Task management
│   ├── models/                 # Pydantic data models
│   │   ├── pr.py              # PR configuration
│   │   ├── job.py             # Job configuration
│   │   ├── task.py            # Task configuration
│   │   ├── trial.py           # Trial results
│   │   └── registry.py        # Registry models
│   ├── environments/           # Execution environments
│   │   ├── base.py            # BaseEnvironment abstract class
│   │   ├── docker.py          # Docker environment implementation
│   │   └── factory.py         # Environment factory
│   ├── github/                 # GitHub integration
│   │   ├── client.py          # GitHub API client
│   │   └── pr_fetcher.py      # PR data fetcher
│   ├── verifier/               # Verification system
│   │   ├── base.py            # BaseVerifier
│   │   ├── gradle.py          # Gradle verifier
│   │   └── maven.py           # Maven verifier (future)
│   ├── orchestrator/           # Task orchestration
│   │   ├── base.py            # BaseOrchestrator
│   │   └── local.py           # Local orchestrator
│   └── utils/                  # Utilities
│       ├── git.py             # Git operations
│       └── docker.py          # Docker utilities
├── templates/                  # Task templates
│   └── java-gradle/           # Java Gradle template
│       ├── Dockerfile
│       └── verify.sh
├── examples/
│   └── pr-registry.json       # Example PR registry
├── pyproject.toml
└── README.md
```

---

## Data Models

### 1. PR Registry Format (`pr-registry.json`)

Similar to Harbor's `registry.json`, but for PRs:

```json
{
  "jobs": [
    {
      "name": "spring-framework-prs",
      "description": "Spring Framework PR verification",
      "prs": [
        {
          "pr_url": "https://github.com/spring-projects/spring-framework/pull/12345",
          "project_type": "gradle",
          "priority": "high"
        },
        {
          "pr_url": "https://github.com/spring-projects/spring-boot/pull/67890",
          "project_type": "gradle",
          "priority": "medium"
        }
      ]
    }
  ]
}
```

### 2. Task Configuration

Each PR becomes a task with this structure:

```python
# models/task.py
class TaskConfig(BaseModel):
    task_id: str                      # Unique task ID
    pr_url: str                       # GitHub PR URL
    repo_owner: str                   # e.g., "spring-projects"
    repo_name: str                    # e.g., "spring-framework"
    pr_number: int                    # PR number
    source_branch: str                # PR source branch
    target_branch: str                # PR target branch (e.g., "main")
    source_commit: str                # Source branch commit SHA
    target_commit: str                # Target branch commit SHA
    project_type: str                 # "gradle", "maven", etc.

    timeout_sec: float = 1800.0       # 30 minutes default
    cpus: int = 2
    memory_mb: int = 4096
    allow_internet: bool = True       # Needed to fetch dependencies
```

### 3. Trial Configuration

```python
# models/trial.py
class TrialConfig(BaseModel):
    trial_id: UUID
    task: TaskConfig
    environment: EnvironmentConfig
    verifier: VerifierConfig
    retry_attempts: int = 2
```

### 4. Verification Result

```python
# models/trial.py
class VerificationResult(BaseModel):
    success: bool                     # Did compilation succeed?
    compilation_output: str           # stdout/stderr from compilation
    duration_sec: float               # How long it took
    error_message: str | None = None  # Error message if failed
    gradle_tasks_run: list[str] = []  # ["clean", "build", "test"]
```

---

## Core Components

### 1. GitHub Integration (`github/client.py`)

Fetches PR metadata using GitHub API:

```python
class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.client = httpx.AsyncClient()

    async def get_pr_info(self, pr_url: str) -> PRInfo:
        """
        Fetches PR information:
        - PR number
        - Source branch, commit SHA
        - Target branch, commit SHA
        - Repo owner/name
        """
        # Parse URL: https://github.com/owner/repo/pull/123
        # Call: GET /repos/{owner}/{repo}/pulls/{pr_number}
        ...

    async def get_repo_clone_url(self, owner: str, repo: str) -> str:
        """Returns HTTPS clone URL"""
        return f"https://github.com/{owner}/{repo}.git"
```

### 2. Docker Environment (`environments/docker.py`)

Similar to Harbor's DockerEnvironment, but specialized for PR verification:

```python
class DockerEnvironment(BaseEnvironment):
    async def start(self, force_build: bool = False) -> None:
        """
        1. Build Docker image (Java + Gradle/Maven)
        2. Start container with docker compose up -d
        3. Container runs 'sleep infinity' to stay alive
        """

    async def setup_pr_workspace(self, task: TaskConfig) -> None:
        """
        1. Clone target branch: git clone --branch {target_branch}
        2. Checkout target commit: git checkout {target_commit}
        3. Create mock merge branch: git checkout -b mock-merge
        4. Fetch PR source: git fetch origin pull/{pr_number}/head:pr-source
        5. Merge PR: git merge pr-source --no-edit
        """

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        timeout_sec: int | None = None
    ) -> ExecResult:
        """Execute command in container"""
```

**Dockerfile Template** (`templates/java-gradle/Dockerfile`):

```dockerfile
FROM eclipse-temurin:17-jdk-jammy

# Install Git
RUN apt-get update && apt-get install -y git curl unzip

# Install Gradle (if not using wrapper)
RUN curl -fsSL https://services.gradle.org/distributions/gradle-8.5-bin.zip -o gradle.zip \
    && unzip gradle.zip -d /opt \
    && ln -s /opt/gradle-8.5/bin/gradle /usr/local/bin/gradle \
    && rm gradle.zip

WORKDIR /workspace

CMD ["sleep", "infinity"]
```

### 3. Verifier System (`verifier/gradle.py`)

Executes compilation and captures results:

```python
class GradleVerifier(BaseVerifier):
    async def verify(
        self,
        environment: BaseEnvironment,
        task: TaskConfig,
        trial_dir: Path
    ) -> VerificationResult:
        """
        1. Detect gradle wrapper or use system gradle
        2. Run compilation: ./gradlew clean build -x test
        3. Capture output
        4. Determine success (exit code 0)
        5. Write result to /logs/verifier/result.json
        """

        # Check for gradle wrapper
        wrapper_check = await environment.exec(
            "test -f ./gradlew && echo 'yes' || echo 'no'",
            cwd="/workspace"
        )
        gradle_cmd = "./gradlew" if "yes" in wrapper_check.stdout else "gradle"

        # Run compilation (excluding tests for POC)
        result = await environment.exec(
            f"{gradle_cmd} clean build -x test --no-daemon",
            cwd="/workspace",
            timeout_sec=task.timeout_sec
        )

        success = result.return_code == 0

        return VerificationResult(
            success=success,
            compilation_output=result.stdout + result.stderr,
            duration_sec=result.duration_sec,
            error_message=None if success else result.stderr,
            gradle_tasks_run=["clean", "build"]
        )
```

### 4. Orchestrator (`orchestrator/local.py`)

Manages parallel execution of PR verification tasks:

```python
class LocalOrchestrator:
    def __init__(
        self,
        trial_configs: list[TrialConfig],
        n_concurrent: int = 4
    ):
        self.trial_configs = trial_configs
        self.n_concurrent = n_concurrent

    async def run(self) -> list[TrialResult]:
        """
        Execute all trials with concurrency limit.
        Uses asyncio.Semaphore to limit parallel executions.
        """
        semaphore = asyncio.Semaphore(self.n_concurrent)

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(self._run_trial(semaphore, config))
                for config in self.trial_configs
            ]

        return [task.result() for task in tasks]

    async def _run_trial(
        self,
        semaphore: asyncio.Semaphore,
        config: TrialConfig
    ) -> TrialResult:
        async with semaphore:
            # 1. Start Docker environment
            # 2. Setup PR workspace (clone, checkout, merge)
            # 3. Run verifier
            # 4. Cleanup
            # 5. Return result
            ...
```

### 5. CLI Interface (`cli/main.py`)

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def run(
    registry: Path = typer.Option(..., "--registry", "-r", help="PR registry JSON file"),
    n_concurrent: int = typer.Option(4, "--concurrent", "-c", help="Number of concurrent verifications"),
    output_dir: Path = typer.Option("./results", "--output", "-o", help="Output directory for results"),
    github_token: str = typer.Option(None, "--token", envvar="GITHUB_TOKEN", help="GitHub token for API access"),
):
    """
    Run PR verifications from registry file.

    Example:
        fixagent-verifier run --registry pr-registry.json --concurrent 4
    """
    # 1. Load PR registry
    # 2. Fetch PR info from GitHub
    # 3. Create TrialConfigs
    # 4. Run orchestrator
    # 5. Display results
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (POC)

**Goals:**
- CLI tool that can read PR registry
- Docker environment that can clone and merge PRs
- Gradle verifier that tests compilation
- Single PR verification (no parallelism yet)

**Tasks:**
1. Setup project structure with `pyproject.toml`, `uv` dependencies
2. Implement GitHub client for fetching PR metadata
3. Create Docker environment with Java/Gradle support
4. Implement PR workspace setup (clone, checkout, merge)
5. Create Gradle verifier for compilation testing
6. Build simple CLI that runs one PR verification
7. Test with a real Spring Boot PR

**Deliverables:**
- Can verify a single Java/Gradle PR from URL
- Produces compilation result (success/failure)
- Logs stored in `results/` directory

**Example Command:**
```bash
fixagent-verifier run-single \
  --pr-url https://github.com/spring-projects/spring-boot/pull/12345 \
  --project-type gradle
```

---

### Phase 2: Registry and Parallel Execution

**Goals:**
- Support PR registry JSON format
- Parallel verification of multiple PRs
- Result aggregation and reporting

**Tasks:**
1. Define PR registry JSON schema (Pydantic models)
2. Implement registry loader
3. Create orchestrator with semaphore-based concurrency
4. Add progress tracking (Rich library)
5. Generate summary report (pass/fail counts, duration)
6. Save individual trial results as JSON

**Deliverables:**
- Can process `pr-registry.json` with multiple PRs
- Parallel execution with configurable concurrency
- Results saved in structured format:
  ```
  results/
  ├── job-id/
  │   ├── pr-12345/
  │   │   ├── config.json
  │   │   ├── result.json
  │   │   └── compilation.log
  │   └── pr-67890/
  │       └── ...
  └── summary.json
  ```

**Example Command:**
```bash
fixagent-verifier run \
  --registry pr-registry.json \
  --concurrent 4 \
  --output results/
```

---

### Phase 3: Enhanced Verification

**Goals:**
- Support Maven projects
- Add unit test execution (not just compilation)
- Add checksum tracking for reproducibility
- Retry logic for transient failures

**Tasks:**
1. Implement Maven verifier (`verifier/maven.py`)
2. Extend Gradle verifier to run unit tests
3. Add test result parsing (JUnit XML)
4. Implement retry logic in orchestrator
5. Add task checksums (Git commit SHAs)
6. Support custom Dockerfile per project type

**Deliverables:**
- Can verify Maven projects
- Can run unit tests and parse results
- Retry failed verifications automatically
- Track exact Git commits for reproducibility

**New Result Format:**
```json
{
  "success": true,
  "compilation": {
    "success": true,
    "duration_sec": 45.2
  },
  "tests": {
    "total": 120,
    "passed": 118,
    "failed": 2,
    "skipped": 0,
    "duration_sec": 180.5
  }
}
```

---

### Phase 4: Production Features

**Goals:**
- Cloud execution support (Daytona, Modal)
- Web UI for result viewing
- Webhook integration for auto-verification
- Metrics and analytics

**Tasks:**
1. Implement Daytona environment adapter
2. Add web UI (FastAPI + React) for viewing results
3. Create GitHub webhook handler for auto-verification on PR open/update
4. Add metrics collection (success rate, avg duration, etc.)
5. Support custom verifier scripts (like Harbor's test.sh)
6. Add caching for Docker images and dependencies

**Deliverables:**
- Can run verifications in cloud environments
- Web dashboard showing verification history
- Auto-verify PRs via webhook
- Prometheus metrics endpoint

---

## Git Merge Simulation Strategy

### Approach 1: Direct Merge (Recommended for POC)

**Steps:**
1. Clone target repository
2. Checkout target branch at specific commit
3. Fetch PR branch: `git fetch origin pull/{pr_number}/head:pr-branch`
4. Create merge branch: `git checkout -b mock-merge`
5. Merge PR: `git merge pr-branch --no-commit --no-ff`
6. Verify compilation
7. (Don't commit - just test)

**Pros:**
- Simple and fast
- Directly tests merge conflicts
- No need to fork

**Cons:**
- Requires write access to clone private repos (use GitHub token)

### Approach 2: Fork-based (Future)

**Steps:**
1. Fork source repository to temporary GitHub account
2. Push PR branch to fork
3. Merge in isolated environment
4. Cleanup fork after verification

**Pros:**
- Works with private repos without token
- More similar to actual PR workflow

**Cons:**
- Requires GitHub app/OAuth setup
- Slower due to fork creation

**Recommendation:** Start with Approach 1 for POC.

---

## Example PR Registry

```json
{
  "name": "spring-framework-verification",
  "description": "Verify Spring Framework PRs",
  "settings": {
    "n_concurrent": 4,
    "timeout_sec": 1800,
    "retry_attempts": 2
  },
  "prs": [
    {
      "pr_url": "https://github.com/spring-projects/spring-framework/pull/12345",
      "project_type": "gradle",
      "priority": "high",
      "custom_verify_script": null
    },
    {
      "pr_url": "https://github.com/spring-projects/spring-boot/pull/67890",
      "project_type": "gradle",
      "priority": "medium",
      "custom_verify_script": "./custom-verify.sh"
    }
  ]
}
```

---

## Key Design Decisions

### 1. Docker Isolation

**Decision:** Each PR verification runs in its own Docker container.

**Reasoning:**
- Complete isolation prevents conflicts
- Reproducible environments
- Easy cleanup after verification
- Can run multiple PRs in parallel safely

### 2. Task-based Architecture

**Decision:** Each PR is a "task" in Harbor terminology.

**Reasoning:**
- Reuses proven patterns from Harbor
- Easy to extend to other verification types
- Clear separation of concerns

### 3. Asynchronous Execution

**Decision:** Use `asyncio` for all I/O operations.

**Reasoning:**
- Efficient parallel execution
- Better resource utilization
- Consistent with Harbor's architecture

### 4. Git Strategy

**Decision:** Clone and merge in container, don't push anywhere.

**Reasoning:**
- Faster than fork-based approach
- No GitHub API rate limits for push operations
- Simpler implementation for POC

### 5. Compilation-only POC

**Decision:** Phase 1 only tests compilation, not unit tests.

**Reasoning:**
- Faster implementation
- Validates core architecture
- Tests often require additional setup (databases, etc.)

---

## Technology Stack

- **Language:** Python 3.12+
- **Package Manager:** uv
- **CLI Framework:** Typer
- **Async Runtime:** asyncio
- **Models:** Pydantic v2
- **Docker:** docker-py + docker compose
- **GitHub API:** httpx + GitHub REST API
- **Progress UI:** Rich
- **Testing:** pytest

---

## Security Considerations

1. **GitHub Token Storage:**
   - Use environment variable `GITHUB_TOKEN`
   - Never log tokens
   - Support GitHub App authentication (Phase 4)

2. **Docker Isolation:**
   - Run containers with non-root user
   - Limit network access (disable for security testing)
   - Set resource limits (CPU, memory, storage)

3. **Malicious Code Protection:**
   - Run all code in sandboxed containers
   - No access to host filesystem except logs
   - Network restrictions for untrusted code

4. **Rate Limiting:**
   - Respect GitHub API rate limits
   - Add backoff for API failures
   - Cache PR metadata

---

## Testing Strategy

### Unit Tests
- Test PR URL parsing
- Test Git operations (mock)
- Test result parsing
- Test Docker command generation

### Integration Tests
- Test full PR verification flow with test repos
- Test Docker container lifecycle
- Test parallel execution with semaphore

### End-to-End Tests
- Verify real Spring Boot PR (with mocking in CI)
- Test error handling (merge conflicts, compilation failures)
- Test timeout handling

---

## CLI Commands (Final)

```bash
# Run verifications from registry
fixagent-verifier run --registry pr-registry.json --concurrent 4

# Run single PR verification
fixagent-verifier run-single --pr-url <url> --project-type gradle

# List all jobs
fixagent-verifier jobs list

# View job results
fixagent-verifier jobs view <job-id>

# View specific trial result
fixagent-verifier trial view <trial-id>

# Clean up old results
fixagent-verifier clean --older-than 7d

# Generate summary report
fixagent-verifier report --job-id <job-id> --format html
```

---

## Success Metrics

### Phase 1 (POC)
- [ ] Can verify 1 Spring Boot PR successfully
- [ ] Correctly detects compilation success/failure
- [ ] Completes within 5 minutes for typical PR
- [ ] Produces readable log output

### Phase 2 (Production-Ready)
- [ ] Can verify 10+ PRs in parallel
- [ ] 95%+ success rate (no false failures)
- [ ] Average verification time < 3 minutes
- [ ] Zero manual intervention required

### Phase 3 (Enhanced)
- [ ] Supports Maven + Gradle
- [ ] Can run unit tests
- [ ] Handles merge conflicts gracefully
- [ ] Retry logic reduces transient failures to <1%

### Phase 4 (Scale)
- [ ] Can run 100+ verifications concurrently (cloud)
- [ ] Web UI provides real-time status
- [ ] Auto-verifies PRs within 1 minute of creation
- [ ] Metrics tracked in Prometheus/Grafana

---

## Next Steps

1. **Review this plan** - Confirm architecture aligns with requirements
2. **Setup repository** - Initialize project structure
3. **Implement Phase 1** - Build POC with single PR verification
4. **Test with real PRs** - Validate against Spring Boot/Framework PRs
5. **Iterate** - Gather feedback and refine

---

## Questions to Address

1. Should we support private repositories in Phase 1?
2. Do we need to support merge conflict detection/reporting?
3. Should we cache Docker images between runs?
4. What level of logging detail is needed?
5. Should we support custom Dockerfiles per PR?
6. Do we need a web UI or CLI-only is sufficient for POC?

---

## Resources

- Harbor Framework: https://github.com/laude-institute/harbor
- GitHub API: https://docs.github.com/en/rest
- Docker Python SDK: https://docker-py.readthedocs.io/
- Typer Documentation: https://typer.tiangolo.com/
