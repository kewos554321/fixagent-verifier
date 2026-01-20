# Docker Compose Task Configuration Approach

## 簡化的 Task 結構

### Task 命名規範

```
tasks/
├── springboot-aws-k8s_1/          # <repo_name>_<pr_id>
│   ├── docker-compose.yaml        # 定義編譯方式
│   └── .env                       # PR 資訊
├── spring-boot_12345/
│   ├── docker-compose.yaml
│   └── .env
└── react_789/
    ├── docker-compose.yaml
    └── .env
```

---

## Docker Compose 配置方案

### 方案 1: 使用 Environment Variables (推薦)

**`tasks/springboot-aws-k8s_1/docker-compose.yaml`**:

```yaml
version: '3.8'

services:
  verifier:
    image: fixagent-verifier:${PROJECT_TYPE:-java-gradle}
    container_name: pr_${REPO_NAME}_${PR_ID}

    environment:
      # PR 資訊
      - PR_NUMBER=${PR_ID}
      - REPO_URL=${REPO_URL}
      - REPO_NAME=${REPO_NAME}
      - TARGET_BRANCH=${TARGET_BRANCH:-main}
      - TARGET_COMMIT=${TARGET_COMMIT}
      - SOURCE_BRANCH=${SOURCE_BRANCH}
      - SOURCE_COMMIT=${SOURCE_COMMIT}

      # 專案類型與編譯設定
      - PROJECT_TYPE=${PROJECT_TYPE:-java-gradle}
      - BUILD_COMMAND=${BUILD_COMMAND:-./gradlew clean build -x test --no-daemon}
      - TEST_COMMAND=${TEST_COMMAND:-./gradlew test --no-daemon}
      - JAVA_VERSION=${JAVA_VERSION:-17}

    volumes:
      - ./logs:/logs
      - /var/run/docker.sock:/var/run/docker.sock  # 如果需要 Docker-in-Docker

    working_dir: /workspace

    command: |
      bash -c '
        echo "=== PR Verification: $${REPO_NAME} #$${PR_ID} ==="
        echo "Project Type: $${PROJECT_TYPE}"
        echo "Build Command: $${BUILD_COMMAND}"
        echo ""

        # Clone repository
        git clone --depth=1 --branch "$${TARGET_BRANCH}" "$${REPO_URL}" /workspace
        cd /workspace

        # Fetch and merge PR
        git fetch --depth=50 origin "$${TARGET_COMMIT}"
        git fetch origin "pull/$${PR_ID}/head:pr-source"
        git checkout "$${TARGET_COMMIT}"
        git checkout -b mock-merge
        git merge pr-source --no-commit --no-edit || echo "Merge conflicts detected"

        # Run build
        eval "$${BUILD_COMMAND}"
        BUILD_EXIT_CODE=$$?

        # Write result
        mkdir -p /logs/verifier
        if [ $$BUILD_EXIT_CODE -eq 0 ]; then
          echo "1" > /logs/verifier/result.txt
          echo "SUCCESS"
        else
          echo "0" > /logs/verifier/result.txt
          echo "FAILED"
          exit 1
        fi
      '

    # Resource limits
    cpus: ${CPUS:-2}
    mem_limit: ${MEMORY:-4g}

    networks:
      - pr-verification

networks:
  pr-verification:
    driver: bridge
```

**`tasks/springboot-aws-k8s_1/.env`**:

```bash
# PR Information
PR_ID=1
REPO_NAME=springboot-aws-k8s
REPO_URL=https://github.com/kewos554321/springboot-aws-k8s.git
TARGET_BRANCH=main
TARGET_COMMIT=c6b497d
SOURCE_BRANCH=kewos554321-patch-1
SOURCE_COMMIT=465866d

# Project Configuration
PROJECT_TYPE=java-gradle
BUILD_COMMAND=./gradlew clean build -x test --no-daemon --stacktrace
TEST_COMMAND=./gradlew test --no-daemon
JAVA_VERSION=17

# Resource Limits
CPUS=2
MEMORY=4g
```

### 方案 2: 使用 Labels (元數據標記)

```yaml
version: '3.8'

services:
  verifier:
    image: fixagent-verifier:java-gradle

    labels:
      # PR Metadata
      pr.number: "1"
      pr.repo: "springboot-aws-k8s"
      pr.url: "https://github.com/kewos554321/springboot-aws-k8s/pull/1"

      # Project Configuration
      project.type: "java-gradle"
      project.language: "java"
      project.jdk: "17"

      # Build Configuration
      build.command: "./gradlew clean build -x test --no-daemon"
      build.test_command: "./gradlew test --no-daemon"

      # Verification Metadata
      verification.priority: "high"
      verification.tags: "spring-boot,aws,k8s"

    environment:
      - PR_NUMBER=1
      - REPO_URL=https://github.com/kewos554321/springboot-aws-k8s.git
      # ... (same as above)

    command: bash /scripts/verify.sh
```

### 方案 3: 使用 Extension Fields (簡化配置)

```yaml
version: '3.8'

# 定義可重用的配置
x-java-gradle-base: &java-gradle-base
  image: fixagent-verifier:java-gradle
  environment: &java-gradle-env
    PROJECT_TYPE: java-gradle
    BUILD_COMMAND: "./gradlew clean build -x test --no-daemon"
    TEST_COMMAND: "./gradlew test --no-daemon"
  cpus: 2
  mem_limit: 4g

x-java-maven-base: &java-maven-base
  image: fixagent-verifier:java-maven
  environment: &java-maven-env
    PROJECT_TYPE: java-maven
    BUILD_COMMAND: "mvn clean compile -DskipTests"
    TEST_COMMAND: "mvn test"
  cpus: 2
  mem_limit: 4g

x-nodejs-base: &nodejs-base
  image: fixagent-verifier:nodejs
  environment: &nodejs-env
    PROJECT_TYPE: nodejs-npm
    BUILD_COMMAND: "npm ci && npm run build"
    TEST_COMMAND: "npm test"
  cpus: 2
  mem_limit: 2g

services:
  verifier:
    # 根據專案類型選擇 base
    <<: *java-gradle-base  # 使用 Java Gradle 配置

    environment:
      # 繼承 base 的環境變量
      <<: *java-gradle-env

      # PR 特定資訊
      PR_NUMBER: 1
      REPO_URL: https://github.com/kewos554321/springboot-aws-k8s.git
      REPO_NAME: springboot-aws-k8s
      TARGET_BRANCH: main
      TARGET_COMMIT: c6b497d
      SOURCE_COMMIT: 465866d

    volumes:
      - ./logs:/logs

    working_dir: /workspace
    command: bash /scripts/verify.sh
```

---

## 實際使用範例

### Java Gradle Project

**`tasks/spring-boot_12345/docker-compose.yaml`**:
```yaml
version: '3.8'

services:
  verifier:
    image: eclipse-temurin:17-jdk-jammy
    container_name: pr_spring-boot_12345

    environment:
      # PR Info
      PR_ID: "12345"
      REPO_URL: "https://github.com/spring-projects/spring-boot.git"
      TARGET_BRANCH: "main"
      TARGET_COMMIT: "abc123"

      # Build Config
      PROJECT_TYPE: "java-gradle"
      BUILD_CMD: "./gradlew clean build -x test --no-daemon"

    volumes:
      - ./logs:/logs

    working_dir: /workspace

    command: |
      bash -c '
        # Install git
        apt-get update && apt-get install -y git

        # Clone and merge
        git clone --branch $$TARGET_BRANCH $$REPO_URL /workspace
        cd /workspace
        git fetch origin pull/$$PR_ID/head:pr-source
        git checkout $$TARGET_COMMIT
        git merge pr-source --no-edit

        # Build
        $$BUILD_CMD

        # Result
        mkdir -p /logs/verifier
        echo "$$?" > /logs/verifier/exit_code.txt
      '
```

### Node.js Project

**`tasks/react_789/docker-compose.yaml`**:
```yaml
version: '3.8'

services:
  verifier:
    image: node:20-alpine

    environment:
      PR_ID: "789"
      REPO_URL: "https://github.com/facebook/react.git"
      TARGET_BRANCH: "main"
      BUILD_CMD: "npm ci && npm run build"

    working_dir: /workspace

    command: |
      sh -c '
        apk add --no-cache git
        git clone --branch $$TARGET_BRANCH $$REPO_URL /workspace
        cd /workspace
        git fetch origin pull/$$PR_ID/head:pr-source
        git merge pr-source --no-edit
        $$BUILD_CMD
      '
```

### Python Project

**`tasks/django_456/docker-compose.yaml`**:
```yaml
version: '3.8'

services:
  verifier:
    image: python:3.11-slim

    environment:
      PR_ID: "456"
      REPO_URL: "https://github.com/django/django.git"
      BUILD_CMD: "pip install -r requirements.txt && python -m compileall ."

    command: |
      bash -c '
        apt-get update && apt-get install -y git
        git clone $$REPO_URL /workspace
        cd /workspace
        git fetch origin pull/$$PR_ID/head:pr-source
        git merge pr-source --no-edit
        $$BUILD_CMD
      '
```

---

## CLI 整合

### 執行方式

```bash
# 方式 1: 直接使用 docker compose
cd tasks/springboot-aws-k8s_1/
docker compose up --abort-on-container-exit

# 方式 2: 使用 CLI wrapper
fixagent-verifier run-compose --task springboot-aws-k8s_1

# 方式 3: 批次執行
fixagent-verifier run-all-compose --concurrent 4
```

### CLI 實作

```python
# cli/main.py

@app.command()
def run_compose(
    task: str = typer.Option(..., "--task", help="Task directory name"),
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir"),
):
    """
    Run PR verification using docker compose.

    Example:
        fixagent-verifier run-compose --task springboot-aws-k8s_1
    """
    task_dir = tasks_dir / task
    compose_file = task_dir / "docker-compose.yaml"

    if not compose_file.exists():
        console.print(f"[red]No docker-compose.yaml found in {task_dir}[/red]")
        raise typer.Exit(1)

    # Run docker compose
    console.print(f"[bold]Running verification for {task}...[/bold]")

    result = subprocess.run(
        ["docker", "compose", "up", "--abort-on-container-exit"],
        cwd=task_dir,
        capture_output=True,
        text=True
    )

    # Parse result
    result_file = task_dir / "logs" / "verifier" / "result.txt"
    if result_file.exists():
        success = "1" in result_file.read_text()
        if success:
            console.print("[green]✓ Verification PASSED[/green]")
        else:
            console.print("[red]✗ Verification FAILED[/red]")
            raise typer.Exit(1)
    else:
        console.print("[yellow]! No result file found[/yellow]")
        raise typer.Exit(1)


@app.command()
def run_all_compose(
    tasks_dir: Path = typer.Option(Path("tasks"), "--tasks-dir"),
    concurrent: int = typer.Option(4, "--concurrent", "-c"),
    pattern: str = typer.Option("*", "--pattern"),
):
    """
    Run all tasks using docker compose in parallel.

    Example:
        fixagent-verifier run-all-compose --concurrent 4
    """
    # Find all task directories with docker-compose.yaml
    task_dirs = []
    for task_dir in tasks_dir.glob(pattern):
        if (task_dir / "docker-compose.yaml").exists():
            task_dirs.append(task_dir)

    if not task_dirs:
        console.print("[yellow]No tasks found[/yellow]")
        return

    console.print(f"[bold]Found {len(task_dirs)} tasks[/bold]\n")

    # Run in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=concurrent) as executor:
        futures = {
            executor.submit(run_task_compose, task_dir): task_dir
            for task_dir in task_dirs
        }

        for future in as_completed(futures):
            task_dir = futures[future]
            try:
                result = future.result()
                if result:
                    console.print(f"[green]✓ {task_dir.name}[/green]")
                else:
                    console.print(f"[red]✗ {task_dir.name}[/red]")
            except Exception as e:
                console.print(f"[red]✗ {task_dir.name}: {e}[/red]")


def run_task_compose(task_dir: Path) -> bool:
    """Run a single task using docker compose."""
    subprocess.run(
        ["docker", "compose", "up", "--abort-on-container-exit"],
        cwd=task_dir,
        capture_output=True,
    )

    result_file = task_dir / "logs" / "verifier" / "result.txt"
    if result_file.exists():
        return "1" in result_file.read_text()
    return False
```

---

## Task 生成器

```python
# task_generator/compose_generator.py

class ComposeTaskGenerator:
    """生成基於 docker-compose 的 task"""

    def __init__(self, tasks_dir: Path = Path("tasks")):
        self.tasks_dir = tasks_dir

    async def generate(
        self, pr_url: str, project_type: str = None
    ) -> Path:
        """
        生成 task 目錄

        Args:
            pr_url: PR URL
            project_type: 專案類型 (可選，會自動檢測)

        Returns:
            Task 目錄路徑
        """
        # 1. Fetch PR info
        github_client = GitHubClient()
        pr_info = await github_client.get_pr_info(pr_url)

        # 2. Auto-detect project type if not specified
        if not project_type:
            detector = ProjectDetector()
            project_type = await detector.detect_from_github(
                pr_info.repo_owner, pr_info.repo_name
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
        (task_dir / "logs" / "verifier").mkdir(parents=True, exist_ok=True)

        return task_dir

    def _generate_compose(
        self, pr_info: PRInfo, project_type: str
    ) -> str:
        """生成 docker-compose.yaml 內容"""

        # Project type specific configs
        configs = {
            "java-gradle": {
                "image": "eclipse-temurin:17-jdk-jammy",
                "build_cmd": "./gradlew clean build -x test --no-daemon",
                "setup": "apt-get update && apt-get install -y git",
            },
            "java-maven": {
                "image": "maven:3.9-eclipse-temurin-17",
                "build_cmd": "mvn clean compile -DskipTests",
                "setup": "apt-get update && apt-get install -y git",
            },
            "nodejs-npm": {
                "image": "node:20-alpine",
                "build_cmd": "npm ci && npm run build",
                "setup": "apk add --no-cache git",
            },
            "python-pip": {
                "image": "python:3.11-slim",
                "build_cmd": "pip install -r requirements.txt && python -m compileall .",
                "setup": "apt-get update && apt-get install -y git",
            },
        }

        config = configs.get(project_type, configs["java-gradle"])

        return f'''version: '3.8'

services:
  verifier:
    image: {config["image"]}
    container_name: pr_{pr_info.repo_name}_{pr_info.pr_number}

    environment:
      - PR_NUMBER={pr_info.pr_number}
      - REPO_URL={pr_info.clone_url}
      - REPO_NAME={pr_info.repo_name}
      - TARGET_BRANCH={pr_info.target_branch}
      - TARGET_COMMIT={pr_info.target_commit}
      - SOURCE_COMMIT={pr_info.source_commit}
      - PROJECT_TYPE={project_type}
      - BUILD_COMMAND={config["build_cmd"]}

    volumes:
      - ./logs:/logs

    working_dir: /workspace

    command: |
      bash -c '
        echo "=== PR Verification: $REPO_NAME #$PR_NUMBER ==="

        # Setup
        {config["setup"]}
        git config --global user.email "fixagent@verifier.local"
        git config --global user.name "FixAgent Verifier"

        # Clone
        git clone --depth=1 --branch "$TARGET_BRANCH" "$REPO_URL" /workspace
        cd /workspace

        # Fetch and merge
        git fetch --depth=50 origin "$TARGET_COMMIT"
        git fetch origin "pull/$PR_NUMBER/head:pr-source"
        git checkout "$TARGET_COMMIT"
        git checkout -b mock-merge
        git merge pr-source --no-commit --no-edit || echo "Merge conflicts"

        # Build
        echo "Running: $BUILD_COMMAND"
        eval "$BUILD_COMMAND"
        EXIT_CODE=$?

        # Write result
        mkdir -p /logs/verifier
        if [ $EXIT_CODE -eq 0 ]; then
          echo "1" > /logs/verifier/result.txt
          echo "=== BUILD SUCCESS ==="
        else
          echo "0" > /logs/verifier/result.txt
          echo "=== BUILD FAILED ==="
          exit 1
        fi
      '

    cpus: 2
    mem_limit: 4g
'''

    def _generate_env(
        self, pr_info: PRInfo, project_type: str
    ) -> str:
        """生成 .env 檔案"""
        return f'''# PR Information
PR_ID={pr_info.pr_number}
REPO_NAME={pr_info.repo_name}
REPO_URL={pr_info.clone_url}
TARGET_BRANCH={pr_info.target_branch}
TARGET_COMMIT={pr_info.target_commit}
SOURCE_BRANCH={pr_info.source_branch}
SOURCE_COMMIT={pr_info.source_commit}

# Project Configuration
PROJECT_TYPE={project_type}

# Resource Limits
CPUS=2
MEMORY=4g
'''
```

---

## 使用流程

### 1. 生成 Task

```bash
fixagent-verifier generate-compose \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1

# 輸出:
# ✓ Generated task: tasks/springboot-aws-k8s_1/
```

### 2. 檢查生成的檔案

```bash
tree tasks/springboot-aws-k8s_1/

# tasks/springboot-aws-k8s_1/
# ├── docker-compose.yaml
# ├── .env
# └── logs/
#     └── verifier/
```

### 3. 執行驗證

```bash
# 方式 A: 直接用 docker compose
cd tasks/springboot-aws-k8s_1/
docker compose up

# 方式 B: 用 CLI
fixagent-verifier run-compose --task springboot-aws-k8s_1
```

### 4. 查看結果

```bash
cat tasks/springboot-aws-k8s_1/logs/verifier/result.txt
# 1  (表示成功)

docker compose logs
# 查看完整日誌
```

---

## 優勢

✅ **簡單**: 每個 task 只需要 `docker-compose.yaml` + `.env`
✅ **標準化**: 使用 Docker Compose 標準
✅ **靈活**: 編譯命令在配置檔中，容易修改
✅ **可攜**: 可以直接分享 task 目錄
✅ **易調試**: 可以手動修改 compose 配置重新執行

## 總結

使用 **`<repo_name>_<pr_id>`** 命名 + **docker-compose.yaml** 定義編譯方式是最簡潔實用的方案！

你可以立即開始使用這個方案，我可以幫你實作 `generate-compose` 和 `run-compose` 命令！
