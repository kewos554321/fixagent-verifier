"""Docker Compose task generator."""

from pathlib import Path
from typing import Dict

from fixagent_verifier.github.client import GitHubClient
from fixagent_verifier.models.pr import PRInfo
from fixagent_verifier.project_detector import ProjectDetector, ProjectType


class ComposeTaskGenerator:
    """Generate docker-compose based tasks for PR verification."""

    # Project type configurations
    PROJECT_CONFIGS: Dict[ProjectType, dict] = {
        ProjectType.JAVA_GRADLE: {
            "image": "eclipse-temurin:17-jdk-jammy",
            "build_cmd": "./gradlew clean build -x test --no-daemon --stacktrace",
            "test_cmd": "./gradlew test --no-daemon",
            "setup": "apt-get update && apt-get install -y git curl",
        },
        ProjectType.JAVA_MAVEN: {
            "image": "maven:3.9-eclipse-temurin-17",
            "build_cmd": "mvn clean compile -DskipTests -q",
            "test_cmd": "mvn test",
            "setup": "apt-get update && apt-get install -y git",
        },
        ProjectType.NODEJS_NPM: {
            "image": "node:20-alpine",
            "build_cmd": "npm ci && npm run build",
            "test_cmd": "npm test",
            "setup": "apk add --no-cache git bash",
        },
        ProjectType.NODEJS_YARN: {
            "image": "node:20-alpine",
            "build_cmd": "yarn install --frozen-lockfile && yarn build",
            "test_cmd": "yarn test",
            "setup": "apk add --no-cache git bash",
        },
        ProjectType.PYTHON_PIP: {
            "image": "python:3.11-slim",
            "build_cmd": "pip install -r requirements.txt && python -m compileall .",
            "test_cmd": "pytest",
            "setup": "apt-get update && apt-get install -y git",
        },
        ProjectType.PYTHON_POETRY: {
            "image": "python:3.11-slim",
            "build_cmd": "pip install poetry && poetry install && poetry build",
            "test_cmd": "poetry run pytest",
            "setup": "apt-get update && apt-get install -y git",
        },
        ProjectType.RUST_CARGO: {
            "image": "rust:latest",
            "build_cmd": "cargo build --release",
            "test_cmd": "cargo test",
            "setup": "apt-get update && apt-get install -y git",
        },
        ProjectType.GO_MOD: {
            "image": "golang:1.21-alpine",
            "build_cmd": "go mod download && go build ./...",
            "test_cmd": "go test ./...",
            "setup": "apk add --no-cache git bash",
        },
    }

    def __init__(self, tasks_dir: Path = Path("tasks")):
        """
        Initialize compose task generator.

        Args:
            tasks_dir: Directory to store tasks
        """
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(exist_ok=True)
        self.github_client = GitHubClient()
        self.detector = ProjectDetector()

    async def generate_from_pr_url(
        self,
        pr_url: str,
        project_type: ProjectType | None = None,
        github_token: str | None = None,
    ) -> Path:
        """
        Generate task from PR URL.

        Args:
            pr_url: GitHub PR URL
            project_type: Optional project type (auto-detect if None)
            github_token: Optional GitHub token

        Returns:
            Path to generated task directory
        """
        # 1. Fetch PR info
        pr_info = await self.github_client.get_pr_info(pr_url)

        # 2. Auto-detect project type if not specified
        if not project_type:
            project_type = await self.detector.detect_from_github(
                pr_info.repo_owner,
                pr_info.repo_name,
                pr_info.target_branch,
                github_token,
            )

        if project_type == ProjectType.UNKNOWN:
            raise ValueError(
                f"Unable to detect project type for {pr_info.repo_owner}/{pr_info.repo_name}"
            )

        # 3. Create task directory
        task_name = f"{pr_info.repo_name}_{pr_info.pr_number}"
        task_dir = self.tasks_dir / task_name
        task_dir.mkdir(exist_ok=True)

        # 4. Generate docker-compose.yaml
        compose_content = self._generate_compose(pr_info, project_type)
        (task_dir / "docker-compose.yaml").write_text(compose_content)

        # 5. Generate .env file
        env_content = self._generate_env(pr_info, project_type)
        (task_dir / ".env").write_text(env_content)

        # 6. Create logs directory
        logs_dir = task_dir / "logs" / "verifier"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # 7. Create README
        readme_content = self._generate_readme(pr_info, project_type)
        (task_dir / "README.md").write_text(readme_content)

        return task_dir

    def _generate_compose(self, pr_info: PRInfo, project_type: ProjectType) -> str:
        """Generate docker-compose.yaml content."""
        config = self.PROJECT_CONFIGS.get(
            project_type, self.PROJECT_CONFIGS[ProjectType.JAVA_GRADLE]
        )

        return f'''version: '3.8'

services:
  verifier:
    image: {config["image"]}
    container_name: pr_{pr_info.repo_name}_{pr_info.pr_number}

    environment:
      # PR Information
      - PR_NUMBER={pr_info.pr_number}
      - REPO_URL={pr_info.clone_url}
      - REPO_NAME={pr_info.repo_name}
      - REPO_OWNER={pr_info.repo_owner}
      - TARGET_BRANCH={pr_info.target_branch}
      - TARGET_COMMIT={pr_info.target_commit}
      - SOURCE_BRANCH={pr_info.source_branch}
      - SOURCE_COMMIT={pr_info.source_commit}

      # Project Configuration
      - PROJECT_TYPE={project_type.value}
      - BUILD_COMMAND={config["build_cmd"]}
      - TEST_COMMAND={config["test_cmd"]}

    volumes:
      - ./logs:/logs

    working_dir: /workspace

    command: |
      bash -c '
        set -e
        echo "=========================================="
        echo "PR Verification: $REPO_NAME #$PR_NUMBER"
        echo "Project Type: $PROJECT_TYPE"
        echo "=========================================="
        echo ""

        # Setup
        echo "==> Setting up environment..."
        {config["setup"]}
        git config --global user.email "fixagent@verifier.local"
        git config --global user.name "FixAgent Verifier"

        # Clone repository
        echo "==> Cloning repository..."
        git clone --depth=1 --branch "$TARGET_BRANCH" "$REPO_URL" /workspace
        cd /workspace

        # Fetch PR and commits
        echo "==> Fetching PR #$PR_NUMBER..."
        git fetch --depth=50 origin "$TARGET_COMMIT"
        git fetch origin "pull/$PR_NUMBER/head:pr-source"

        # Checkout target commit
        echo "==> Checking out target commit: $TARGET_COMMIT"
        git checkout "$TARGET_COMMIT"

        # Create merge branch
        echo "==> Creating mock merge branch..."
        git checkout -b mock-merge

        # Merge PR
        echo "==> Merging PR source branch..."
        git merge pr-source --no-commit --no-edit || {{
          echo "WARNING: Merge conflicts detected, continuing anyway..."
        }}

        # Run build
        echo ""
        echo "==> Running build command..."
        echo "Command: $BUILD_COMMAND"
        echo ""

        eval "$BUILD_COMMAND"
        BUILD_EXIT_CODE=$?

        # Write result
        mkdir -p /logs/verifier
        echo "$BUILD_EXIT_CODE" > /logs/verifier/exit_code.txt
        date -Iseconds > /logs/verifier/timestamp.txt

        if [ $BUILD_EXIT_CODE -eq 0 ]; then
          echo "1" > /logs/verifier/result.txt
          echo ""
          echo "=========================================="
          echo "✓ BUILD SUCCESSFUL"
          echo "=========================================="
          exit 0
        else
          echo "0" > /logs/verifier/result.txt
          echo ""
          echo "=========================================="
          echo "✗ BUILD FAILED (exit code: $BUILD_EXIT_CODE)"
          echo "=========================================="
          exit 1
        fi
      '

    # Resource limits
    cpus: 2
    mem_limit: 4g

    networks:
      - pr-verification

networks:
  pr-verification:
    driver: bridge
'''

    def _generate_env(self, pr_info: PRInfo, project_type: ProjectType) -> str:
        """Generate .env file content."""
        config = self.PROJECT_CONFIGS.get(
            project_type, self.PROJECT_CONFIGS[ProjectType.JAVA_GRADLE]
        )

        return f'''# PR Information
PR_ID={pr_info.pr_number}
REPO_NAME={pr_info.repo_name}
REPO_OWNER={pr_info.repo_owner}
REPO_URL={pr_info.clone_url}
TARGET_BRANCH={pr_info.target_branch}
TARGET_COMMIT={pr_info.target_commit}
SOURCE_BRANCH={pr_info.source_branch}
SOURCE_COMMIT={pr_info.source_commit}

# Project Configuration
PROJECT_TYPE={project_type.value}
BUILD_COMMAND={config["build_cmd"]}
TEST_COMMAND={config["test_cmd"]}

# Resource Limits
CPUS=2
MEMORY=4g
'''

    def _generate_readme(self, pr_info: PRInfo, project_type: ProjectType) -> str:
        """Generate README.md for task."""
        return f'''# Task: {pr_info.repo_name}_{pr_info.pr_number}

## PR Information

- **Repository**: {pr_info.repo_owner}/{pr_info.repo_name}
- **PR Number**: #{pr_info.pr_number}
- **PR Title**: {pr_info.title}
- **PR URL**: {pr_info.pr_url}
- **Target Branch**: {pr_info.target_branch} @ `{pr_info.target_commit[:7]}`
- **Source Branch**: {pr_info.source_branch} @ `{pr_info.source_commit[:7]}`

## Project Configuration

- **Type**: {project_type.value}
- **Build Command**: `{self.PROJECT_CONFIGS[project_type]["build_cmd"]}`

## Usage

### Run Verification

```bash
# Using docker compose
docker compose up --abort-on-container-exit

# Using CLI
fixagent-verifier run-compose --task {pr_info.repo_name}_{pr_info.pr_number}
```

### Check Results

```bash
# Check result
cat logs/verifier/result.txt
# 1 = success, 0 = failed

# Check exit code
cat logs/verifier/exit_code.txt

# View logs
docker compose logs
```

### Cleanup

```bash
docker compose down
```

## Generated

- **Created**: {pr_info.pr_url}
- **Generator**: FixAgent Verifier (docker-compose mode)
'''
