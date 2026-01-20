# Multi-Project Task Management System

## Overview

設計一個像 Terminal-Bench 的 task 管理系統，支援多種專案類型和大量 PR 的管理。

---

## 1. Task 組織結構

### Directory Structure

```
fixagent-verifier/
├── tasks/                          # 所有 task 的根目錄
│   ├── java-gradle/               # 按專案類型分類
│   │   ├── pr-123__spring-boot/
│   │   ├── pr-456__kafka/
│   │   └── pr-789__hibernate/
│   │
│   ├── java-maven/
│   │   ├── pr-111__maven-core/
│   │   └── pr-222__junit5/
│   │
│   ├── nodejs-npm/
│   │   ├── pr-333__react/
│   │   └── pr-444__express/
│   │
│   ├── python-pip/
│   │   ├── pr-555__django/
│   │   └── pr-666__flask/
│   │
│   ├── rust-cargo/
│   │   └── pr-777__tokio/
│   │
│   └── go-mod/
│       └── pr-888__kubernetes/
│
├── templates/                      # 專案類型模板
│   ├── java-gradle/
│   │   ├── Dockerfile.j2
│   │   ├── run-tests.sh.j2
│   │   └── config.yaml
│   ├── java-maven/
│   │   └── ...
│   ├── nodejs-npm/
│   │   └── ...
│   └── python-pip/
│       └── ...
│
├── registries/                     # PR 註冊表
│   ├── spring-ecosystem.yaml       # Spring 相關專案的 PRs
│   ├── apache-projects.yaml        # Apache 專案的 PRs
│   └── my-company.yaml             # 公司內部專案的 PRs
│
└── datasets/                       # 預定義的 task 集合
    ├── production-critical.yaml    # 生產環境關鍵 PRs
    ├── weekly-verification.yaml    # 每週驗證的 PRs
    └── experimental.yaml           # 實驗性 PRs
```

---

## 2. Task 命名規範

### Pattern

```
{project-type}/pr-{number}__{repo-owner}-{repo-name}
```

### Examples

```
java-gradle/pr-123__spring-projects-spring-boot
java-maven/pr-456__apache-maven
nodejs-npm/pr-789__facebook-react
python-pip/pr-101__django-django
rust-cargo/pr-202__tokio-rs-tokio
go-mod/pr-303__kubernetes-kubernetes
```

### Benefits

- ✅ 一眼看出專案類型
- ✅ 按類型分組管理
- ✅ 避免命名衝突
- ✅ 容易搜尋和過濾

---

## 3. Project Type Detection & Templates

### 3.1 Auto-Detection System

```python
# project_detector/detector.py

from pathlib import Path
from enum import Enum

class ProjectType(str, Enum):
    JAVA_GRADLE = "java-gradle"
    JAVA_MAVEN = "java-maven"
    NODEJS_NPM = "nodejs-npm"
    NODEJS_YARN = "nodejs-yarn"
    PYTHON_PIP = "python-pip"
    PYTHON_POETRY = "python-poetry"
    RUST_CARGO = "rust-cargo"
    GO_MOD = "go-mod"
    DOTNET = "dotnet"
    RUBY_BUNDLER = "ruby-bundler"
    UNKNOWN = "unknown"


class ProjectDetector:
    """自動檢測專案類型"""

    # 檢測規則: 檔案存在 → 專案類型
    DETECTION_RULES = {
        ProjectType.JAVA_GRADLE: [
            "build.gradle",
            "build.gradle.kts",
            "gradlew",
            "settings.gradle",
        ],
        ProjectType.JAVA_MAVEN: [
            "pom.xml",
        ],
        ProjectType.NODEJS_NPM: [
            "package.json",
            "package-lock.json",
        ],
        ProjectType.NODEJS_YARN: [
            "package.json",
            "yarn.lock",
        ],
        ProjectType.PYTHON_PIP: [
            "requirements.txt",
            "setup.py",
            "setup.cfg",
        ],
        ProjectType.PYTHON_POETRY: [
            "pyproject.toml",
            "poetry.lock",
        ],
        ProjectType.RUST_CARGO: [
            "Cargo.toml",
            "Cargo.lock",
        ],
        ProjectType.GO_MOD: [
            "go.mod",
            "go.sum",
        ],
        ProjectType.DOTNET: [
            "*.csproj",
            "*.sln",
        ],
        ProjectType.RUBY_BUNDLER: [
            "Gemfile",
            "Gemfile.lock",
        ],
    }

    async def detect_from_github(
        self, repo_owner: str, repo_name: str, branch: str = "main"
    ) -> ProjectType:
        """
        從 GitHub 檢測專案類型

        使用 GitHub API 檢查根目錄檔案
        """
        github_client = GitHubClient()

        for project_type, indicators in self.DETECTION_RULES.items():
            for indicator in indicators:
                exists = await github_client.file_exists(
                    repo_owner, repo_name, branch, indicator
                )
                if exists:
                    return project_type

        return ProjectType.UNKNOWN

    def detect_from_local(self, repo_path: Path) -> ProjectType:
        """從本地目錄檢測專案類型"""
        for project_type, indicators in self.DETECTION_RULES.items():
            for indicator in indicators:
                if "*" in indicator:
                    # Glob pattern
                    if list(repo_path.glob(indicator)):
                        return project_type
                else:
                    if (repo_path / indicator).exists():
                        return project_type

        return ProjectType.UNKNOWN

    async def detect_with_language_hints(
        self, repo_owner: str, repo_name: str
    ) -> ProjectType:
        """
        結合 GitHub 語言統計來檢測

        當檔案檢測失敗時，使用語言統計作為後備
        """
        # 先嘗試檔案檢測
        project_type = await self.detect_from_github(repo_owner, repo_name)
        if project_type != ProjectType.UNKNOWN:
            return project_type

        # 使用語言統計
        github_client = GitHubClient()
        languages = await github_client.get_repo_languages(repo_owner, repo_name)

        # 按比例決定
        primary_language = max(languages.items(), key=lambda x: x[1])[0]

        language_mapping = {
            "Java": ProjectType.JAVA_GRADLE,  # 預設 Gradle
            "JavaScript": ProjectType.NODEJS_NPM,
            "TypeScript": ProjectType.NODEJS_NPM,
            "Python": ProjectType.PYTHON_PIP,
            "Rust": ProjectType.RUST_CARGO,
            "Go": ProjectType.GO_MOD,
            "C#": ProjectType.DOTNET,
            "Ruby": ProjectType.RUBY_BUNDLER,
        }

        return language_mapping.get(primary_language, ProjectType.UNKNOWN)
```

### 3.2 Template System

```python
# templates/template_manager.py

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import yaml

class TemplateManager:
    """管理不同專案類型的模板"""

    def __init__(self, templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        self.env = Environment(loader=FileSystemLoader(templates_dir))

    def get_template_config(self, project_type: ProjectType) -> dict:
        """讀取專案類型的配置"""
        config_path = self.templates_dir / project_type.value / "config.yaml"
        if not config_path.exists():
            raise ValueError(f"No template config for {project_type}")

        return yaml.safe_load(config_path.read_text())

    def render_dockerfile(
        self, project_type: ProjectType, context: dict
    ) -> str:
        """渲染 Dockerfile"""
        template = self.env.get_template(
            f"{project_type.value}/Dockerfile.j2"
        )
        return template.render(**context)

    def render_run_tests(
        self, project_type: ProjectType, context: dict
    ) -> str:
        """渲染 run-tests.sh"""
        template = self.env.get_template(
            f"{project_type.value}/run-tests.sh.j2"
        )
        return template.render(**context)

    def render_test_py(
        self, project_type: ProjectType, context: dict
    ) -> str:
        """渲染 test_compilation.py"""
        template = self.env.get_template(
            f"{project_type.value}/test_compilation.py.j2"
        )
        return template.render(**context)
```

---

## 4. Template Examples

### 4.1 Java Gradle Template

**`templates/java-gradle/config.yaml`**:
```yaml
name: "Java Gradle"
description: "Java projects using Gradle build system"
default_version:
  jdk: 17
  gradle: "8.5"

detection_files:
  - "build.gradle"
  - "build.gradle.kts"
  - "gradlew"

build_command: "./gradlew clean build -x test --no-daemon --stacktrace"
test_command: "./gradlew test --no-daemon"
```

**`templates/java-gradle/Dockerfile.j2`**:
```dockerfile
FROM eclipse-temurin:{{ jdk_version | default(17) }}-jdk-jammy

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl unzip yq \
    && rm -rf /var/lib/apt/lists/*

{% if gradle_version %}
# Install Gradle
RUN curl -fsSL https://services.gradle.org/distributions/gradle-{{ gradle_version }}-bin.zip -o /tmp/gradle.zip \
    && unzip /tmp/gradle.zip -d /opt \
    && ln -s /opt/gradle-{{ gradle_version }}/bin/gradle /usr/local/bin/gradle \
    && rm /tmp/gradle.zip
{% endif %}

# Git config
RUN git config --global user.email "fixagent@verifier.local" \
    && git config --global user.name "FixAgent Verifier"

WORKDIR /workspace
CMD ["sleep", "infinity"]
```

**`templates/java-gradle/run-tests.sh.j2`**:
```bash
#!/bin/bash
set -e

echo "=== Java Gradle PR Verification ==="

# Parse task.yaml
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PR_NUMBER=$(yq eval '.pr.number' "$TASK_DIR/task.yaml")
REPO_URL=$(yq eval '.pr.repo.clone_url' "$TASK_DIR/task.yaml")
TARGET_BRANCH=$(yq eval '.pr.target.branch' "$TASK_DIR/task.yaml")
TARGET_COMMIT=$(yq eval '.pr.target.commit' "$TASK_DIR/task.yaml")

# Clone and merge
git clone --depth=1 --branch "$TARGET_BRANCH" "$REPO_URL" /workspace
cd /workspace
git fetch --depth=50 origin "$TARGET_COMMIT"
git fetch origin "pull/$PR_NUMBER/head:pr-source"
git checkout "$TARGET_COMMIT"
git checkout -b mock-merge
git merge pr-source --no-commit --no-edit || echo "Merge conflicts, continuing..."

# Build
if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
    GRADLE_CMD="./gradlew"
else
    GRADLE_CMD="gradle"
fi

$GRADLE_CMD clean build -x test --no-daemon --stacktrace

# Write result
mkdir -p /logs/verifier
if [ $? -eq 0 ]; then
    echo "1" > /logs/verifier/result.txt
    echo "=== BUILD SUCCESSFUL ==="
else
    echo "0" > /logs/verifier/result.txt
    echo "=== BUILD FAILED ==="
    exit 1
fi
```

### 4.2 Node.js NPM Template

**`templates/nodejs-npm/config.yaml`**:
```yaml
name: "Node.js NPM"
description: "Node.js projects using NPM"
default_version:
  node: 20

detection_files:
  - "package.json"
  - "package-lock.json"

build_command: "npm ci && npm run build"
test_command: "npm test"
```

**`templates/nodejs-npm/Dockerfile.j2`**:
```dockerfile
FROM node:{{ node_version | default(20) }}-alpine

RUN apk add --no-cache git curl yq

RUN git config --global user.email "fixagent@verifier.local" \
    && git config --global user.name "FixAgent Verifier"

WORKDIR /workspace
CMD ["sleep", "infinity"]
```

**`templates/nodejs-npm/run-tests.sh.j2`**:
```bash
#!/bin/bash
set -e

echo "=== Node.js NPM PR Verification ==="

# Parse and clone (same as Java)
# ...

# Build
npm ci
npm run build

# Write result
mkdir -p /logs/verifier
if [ $? -eq 0 ]; then
    echo "1" > /logs/verifier/result.txt
else
    echo "0" > /logs/verifier/result.txt
    exit 1
fi
```

### 4.3 Python Pip Template

**`templates/python-pip/config.yaml`**:
```yaml
name: "Python Pip"
description: "Python projects using pip"
default_version:
  python: "3.11"

detection_files:
  - "requirements.txt"
  - "setup.py"

build_command: "pip install -r requirements.txt && python -m compileall ."
test_command: "pytest"
```

**`templates/python-pip/Dockerfile.j2`**:
```dockerfile
FROM python:{{ python_version | default("3.11") }}-slim

RUN apt-get update && apt-get install -y \
    git curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir yq

RUN git config --global user.email "fixagent@verifier.local" \
    && git config --global user.name "FixAgent Verifier"

WORKDIR /workspace
CMD ["sleep", "infinity"]
```

### 4.4 Rust Cargo Template

**`templates/rust-cargo/run-tests.sh.j2`**:
```bash
#!/bin/bash
set -e

echo "=== Rust Cargo PR Verification ==="

# Parse and clone...
# ...

# Build
cargo build --release

mkdir -p /logs/verifier
if [ $? -eq 0 ]; then
    echo "1" > /logs/verifier/result.txt
else
    echo "0" > /logs/verifier/result.txt
    exit 1
fi
```

### 4.5 Go Mod Template

**`templates/go-mod/run-tests.sh.j2`**:
```bash
#!/bin/bash
set -e

echo "=== Go Mod PR Verification ==="

# Parse and clone...
# ...

# Build
go mod download
go build ./...

mkdir -p /logs/verifier
if [ $? -eq 0 ]; then
    echo "1" > /logs/verifier/result.txt
else
    echo "0" > /logs/verifier/result.txt
    exit 1
fi
```

---

## 5. Registry System

### 5.1 Registry Format

**`registries/spring-ecosystem.yaml`**:
```yaml
name: "Spring Ecosystem PRs"
description: "Spring Framework and related projects"
version: "1.0"

settings:
  auto_detect_project_type: true
  n_concurrent: 4
  output_dir: "results/spring"

prs:
  # Spring Boot
  - pr_url: "https://github.com/spring-projects/spring-boot/pull/12345"
    priority: "high"
    project_type: "java-gradle"  # 可選，會自動檢測
    labels: ["spring-boot", "critical"]

  - pr_url: "https://github.com/spring-projects/spring-boot/pull/12346"
    priority: "medium"
    labels: ["spring-boot", "enhancement"]

  # Spring Framework
  - pr_url: "https://github.com/spring-projects/spring-framework/pull/67890"
    priority: "high"
    project_type: "java-gradle"
    labels: ["spring-framework", "core"]

  # Spring Cloud
  - pr_url: "https://github.com/spring-cloud/spring-cloud-gateway/pull/11111"
    priority: "medium"
    project_type: "java-maven"
    labels: ["spring-cloud", "gateway"]
```

**`registries/multi-language.yaml`**:
```yaml
name: "Multi-Language Projects"
description: "PRs from various programming languages"

prs:
  # Java
  - pr_url: "https://github.com/apache/kafka/pull/123"
    project_type: "java-gradle"
    labels: ["java", "kafka"]

  # Python
  - pr_url: "https://github.com/django/django/pull/456"
    project_type: "python-pip"
    labels: ["python", "django"]

  # Node.js
  - pr_url: "https://github.com/facebook/react/pull/789"
    project_type: "nodejs-yarn"
    labels: ["javascript", "react"]

  # Rust
  - pr_url: "https://github.com/tokio-rs/tokio/pull/101"
    project_type: "rust-cargo"
    labels: ["rust", "tokio"]

  # Go
  - pr_url: "https://github.com/kubernetes/kubernetes/pull/202"
    project_type: "go-mod"
    labels: ["go", "kubernetes"]
```

### 5.2 Dataset Organization

**`datasets/production-critical.yaml`**:
```yaml
name: "Production Critical"
description: "PRs targeting production systems"

# 引用多個 registries
include_registries:
  - "registries/spring-ecosystem.yaml"
  - "registries/apache-projects.yaml"

# 過濾條件
filters:
  priority: ["high", "critical"]
  labels:
    any: ["production", "hotfix", "security"]

# 執行設定
settings:
  n_concurrent: 8
  timeout_multiplier: 1.5
  retry_attempts: 3
```

**`datasets/weekly-verification.yaml`**:
```yaml
name: "Weekly Verification"
description: "All PRs to verify weekly"

include_registries:
  - "registries/**/*.yaml"  # 所有 registries

settings:
  n_concurrent: 16
  skip_verified: true  # 跳過已驗證的
```

---

## 6. Task Discovery & Filtering

### 6.1 Discovery System

```python
# task_discovery/discovery.py

from pathlib import Path
from typing import List
import fnmatch

class TaskDiscovery:
    """發現和過濾 tasks"""

    def __init__(self, tasks_dir: Path = Path("tasks")):
        self.tasks_dir = tasks_dir

    def discover_all(self) -> List[Path]:
        """發現所有 tasks"""
        tasks = []
        for project_type_dir in self.tasks_dir.iterdir():
            if not project_type_dir.is_dir():
                continue
            for task_dir in project_type_dir.iterdir():
                if task_dir.is_dir() and (task_dir / "task.yaml").exists():
                    tasks.append(task_dir)
        return tasks

    def discover_by_project_type(
        self, project_type: ProjectType
    ) -> List[Path]:
        """按專案類型發現"""
        project_type_dir = self.tasks_dir / project_type.value
        if not project_type_dir.exists():
            return []

        return [
            task_dir
            for task_dir in project_type_dir.iterdir()
            if task_dir.is_dir() and (task_dir / "task.yaml").exists()
        ]

    def discover_by_pattern(self, pattern: str) -> List[Path]:
        """
        按 glob pattern 發現

        Examples:
            "java-*/**"              # 所有 Java 專案
            "*/pr-*__spring-*"       # 所有 Spring 相關 PR
            "java-gradle/pr-123*"    # 特定 PR
        """
        all_tasks = self.discover_all()
        relative_paths = [
            task.relative_to(self.tasks_dir) for task in all_tasks
        ]

        matched = [
            path for path in relative_paths
            if fnmatch.fnmatch(str(path), pattern)
        ]

        return [self.tasks_dir / path for path in matched]

    def discover_by_labels(self, labels: List[str]) -> List[Path]:
        """按標籤發現"""
        all_tasks = self.discover_all()
        matched = []

        for task_dir in all_tasks:
            task_config = yaml.safe_load((task_dir / "task.yaml").read_text())
            task_labels = task_config.get("metadata", {}).get("tags", [])

            if any(label in task_labels for label in labels):
                matched.append(task_dir)

        return matched

    def discover_by_priority(self, priorities: List[str]) -> List[Path]:
        """按優先級發現"""
        all_tasks = self.discover_all()
        matched = []

        for task_dir in all_tasks:
            task_config = yaml.safe_load((task_dir / "task.yaml").read_text())
            task_priority = task_config.get("metadata", {}).get("priority", "medium")

            if task_priority in priorities:
                matched.append(task_dir)

        return matched

    def discover_from_registry(
        self, registry_path: Path
    ) -> List[Path]:
        """從 registry 發現 tasks"""
        registry = yaml.safe_load(registry_path.read_text())

        matched = []
        for pr_entry in registry.get("prs", []):
            pr_url = pr_entry["pr_url"]
            # 從 URL 推斷 task ID
            # 例如: https://github.com/owner/repo/pull/123
            #   → java-gradle/pr-123__owner-repo
            task_id = self._url_to_task_id(pr_url, pr_entry.get("project_type"))
            task_path = self._find_task_by_id(task_id)
            if task_path:
                matched.append(task_path)

        return matched

    def filter_unverified(
        self, tasks: List[Path], results_dir: Path
    ) -> List[Path]:
        """過濾未驗證的 tasks"""
        unverified = []

        for task_dir in tasks:
            task_id = task_dir.name
            # 檢查是否有成功的驗證結果
            result_files = list(results_dir.glob(f"{task_id}__**/result.json"))

            if not result_files:
                unverified.append(task_dir)
                continue

            # 檢查最新結果是否成功
            latest_result = max(result_files, key=lambda p: p.stat().st_mtime)
            result_data = json.loads(latest_result.read_text())

            if not result_data.get("verification_result", {}).get("success", False):
                unverified.append(task_dir)

        return unverified
```

### 6.2 CLI Integration

```python
# cli/main.py (extended)

@app.command()
def run(
    # 發現方式
    task_ids: List[str] = typer.Option(None, "--task-id", help="Specific task IDs"),
    project_type: str = typer.Option(None, "--project-type", help="Project type filter"),
    pattern: str = typer.Option(None, "--pattern", help="Glob pattern"),
    labels: List[str] = typer.Option(None, "--label", help="Filter by labels"),
    priority: List[str] = typer.Option(None, "--priority", help="Filter by priority"),
    registry: Path = typer.Option(None, "--registry", help="Registry file"),
    dataset: Path = typer.Option(None, "--dataset", help="Dataset file"),

    # 過濾
    skip_verified: bool = typer.Option(False, "--skip-verified", help="Skip verified tasks"),

    # 執行設定
    n_concurrent: int = typer.Option(4, "--concurrent", "-c"),
    output_dir: Path = typer.Option(Path("results"), "--output-dir", "-o"),
):
    """
    Run tasks with flexible discovery and filtering.

    Examples:
        # Run all Java tasks
        fixagent-verifier run --project-type java-gradle

        # Run specific tasks
        fixagent-verifier run --task-id pr-123__spring-boot --task-id pr-456__kafka

        # Run by pattern
        fixagent-verifier run --pattern "java-*/**"
        fixagent-verifier run --pattern "*/pr-*__spring-*"

        # Run by labels
        fixagent-verifier run --label spring-boot --label critical

        # Run from registry
        fixagent-verifier run --registry registries/spring-ecosystem.yaml

        # Run from dataset
        fixagent-verifier run --dataset datasets/production-critical.yaml

        # Skip already verified
        fixagent-verifier run --pattern "**/*" --skip-verified
    """
    discovery = TaskDiscovery()

    # Discover tasks
    if task_ids:
        tasks = [Path("tasks") / tid for tid in task_ids]
    elif project_type:
        tasks = discovery.discover_by_project_type(ProjectType(project_type))
    elif pattern:
        tasks = discovery.discover_by_pattern(pattern)
    elif labels:
        tasks = discovery.discover_by_labels(labels)
    elif priority:
        tasks = discovery.discover_by_priority(priority)
    elif registry:
        tasks = discovery.discover_from_registry(registry)
    elif dataset:
        tasks = discovery.discover_from_dataset(dataset)
    else:
        # Default: all tasks
        tasks = discovery.discover_all()

    # Filter
    if skip_verified:
        tasks = discovery.filter_unverified(tasks, output_dir)

    if not tasks:
        console.print("[yellow]No tasks found matching criteria[/yellow]")
        return

    console.print(f"[bold]Found {len(tasks)} tasks to verify[/bold]\n")

    # Run
    harness = PRVerificationHarness(
        tasks=tasks,
        output_dir=output_dir,
        n_concurrent=n_concurrent,
    )

    results = asyncio.run(harness.run())

    # Summary
    success_count = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total: {len(results)}")
    console.print(f"  Success: {success_count}")
    console.print(f"  Failed: {len(results) - success_count}")
```

---

## 7. Batch Generation

### 7.1 Registry Batch Generator

```python
# task_generator/batch_generator.py

class BatchGenerator:
    """批次生成 tasks from registry"""

    def __init__(self, templates_dir: Path = Path("templates")):
        self.generator = PRTaskGenerator()
        self.detector = ProjectDetector()

    async def generate_from_registry(
        self, registry_path: Path
    ) -> List[Path]:
        """從 registry 生成所有 tasks"""
        registry = yaml.safe_load(registry_path.read_text())

        tasks = []
        prs = registry.get("prs", [])
        auto_detect = registry.get("settings", {}).get(
            "auto_detect_project_type", True
        )

        with Progress() as progress:
            task_progress = progress.add_task(
                f"[cyan]Generating tasks from {registry_path.name}...",
                total=len(prs)
            )

            for pr_entry in prs:
                pr_url = pr_entry["pr_url"]

                # Detect project type if not specified
                if "project_type" not in pr_entry and auto_detect:
                    # Parse repo info from URL
                    owner, repo = self._parse_repo_from_url(pr_url)
                    project_type = await self.detector.detect_from_github(
                        owner, repo
                    )
                else:
                    project_type = ProjectType(
                        pr_entry.get("project_type", "java-gradle")
                    )

                # Generate task
                task_dir = await self.generator.generate_from_pr_url(
                    pr_url, project_type=project_type
                )

                # Add metadata from registry
                self._add_metadata_to_task(
                    task_dir,
                    priority=pr_entry.get("priority", "medium"),
                    labels=pr_entry.get("labels", []),
                )

                tasks.append(task_dir)
                progress.update(task_progress, advance=1)

        return tasks

    async def generate_from_dataset(
        self, dataset_path: Path
    ) -> List[Path]:
        """從 dataset 生成 tasks"""
        dataset = yaml.safe_load(dataset_path.read_text())

        # Load included registries
        all_prs = []
        for registry_pattern in dataset.get("include_registries", []):
            registry_files = Path(".").glob(registry_pattern)
            for registry_file in registry_files:
                registry = yaml.safe_load(registry_file.read_text())
                all_prs.extend(registry.get("prs", []))

        # Apply filters
        filters = dataset.get("filters", {})
        if filters:
            all_prs = self._apply_filters(all_prs, filters)

        # Generate tasks
        # (Similar to generate_from_registry)
        ...
```

---

## 8. CLI Commands Summary

```bash
# === Task Generation ===

# Generate single task (auto-detect project type)
fixagent-verifier generate --pr-url <url>

# Generate with specific project type
fixagent-verifier generate --pr-url <url> --project-type java-maven

# Batch generate from registry
fixagent-verifier generate-batch --registry registries/spring-ecosystem.yaml

# Batch generate from dataset
fixagent-verifier generate-batch --dataset datasets/production-critical.yaml


# === Task Discovery ===

# List all tasks
fixagent-verifier tasks list

# List by project type
fixagent-verifier tasks list --project-type java-gradle

# List by pattern
fixagent-verifier tasks list --pattern "*/pr-*__spring-*"


# === Task Execution ===

# Run all Java Gradle tasks
fixagent-verifier run --project-type java-gradle

# Run all Spring-related tasks
fixagent-verifier run --pattern "*/pr-*__spring-*"

# Run high priority tasks
fixagent-verifier run --priority high --priority critical

# Run tasks with specific labels
fixagent-verifier run --label production --label security

# Run from registry
fixagent-verifier run --registry registries/spring-ecosystem.yaml

# Run unverified tasks only
fixagent-verifier run --pattern "**/*" --skip-verified

# Run with high concurrency
fixagent-verifier run --dataset datasets/weekly.yaml --concurrent 16


# === Management ===

# Clean old results
fixagent-verifier clean --older-than 7d

# Show statistics
fixagent-verifier stats

# Validate task structure
fixagent-verifier validate-tasks

# Export results
fixagent-verifier export --format csv --output report.csv
```

---

## 9. Example Workflow

### Scenario: Managing 100+ PRs across multiple projects

#### Step 1: Create Registries

```yaml
# registries/company-backend.yaml
prs:
  - pr_url: "https://github.com/company/user-service/pull/101"
  - pr_url: "https://github.com/company/order-service/pull/102"
  - pr_url: "https://github.com/company/payment-service/pull/103"

# registries/company-frontend.yaml
prs:
  - pr_url: "https://github.com/company/web-app/pull/201"
  - pr_url: "https://github.com/company/mobile-app/pull/202"

# registries/open-source.yaml
prs:
  - pr_url: "https://github.com/spring-projects/spring-boot/pull/301"
  - pr_url: "https://github.com/apache/kafka/pull/302"
```

#### Step 2: Batch Generate Tasks

```bash
# Generate all tasks
fixagent-verifier generate-batch --registry registries/company-backend.yaml
fixagent-verifier generate-batch --registry registries/company-frontend.yaml
fixagent-verifier generate-batch --registry registries/open-source.yaml

# Result:
# tasks/
# ├── java-gradle/
# │   ├── pr-101__company-user-service/
# │   ├── pr-102__company-order-service/
# │   ├── pr-103__company-payment-service/
# │   ├── pr-301__spring-projects-spring-boot/
# │   └── pr-302__apache-kafka/
# └── nodejs-npm/
#     ├── pr-201__company-web-app/
#     └── pr-202__company-mobile-app/
```

#### Step 3: Run Verification

```bash
# Run all company backend services (high priority)
fixagent-verifier run --pattern "*/pr-*__company-*" --concurrent 8

# Run open source projects (lower priority)
fixagent-verifier run --pattern "*/pr-*__spring-*" --pattern "*/pr-*__apache-*" --concurrent 4
```

#### Step 4: Check Results

```bash
# Show statistics
fixagent-verifier stats

# Output:
# Total tasks: 107
# By project type:
#   - java-gradle: 85
#   - nodejs-npm: 15
#   - python-pip: 7
#
# Verification status:
#   - Success: 95
#   - Failed: 12
#   - Not run: 0
```

#### Step 5: Retry Failed Tasks

```bash
# Find and rerun failed tasks
fixagent-verifier run --pattern "**/*" --failed-only --concurrent 4
```

---

## 10. Benefits Summary

### ✅ Scalability
- 支援數百個 PRs
- 按專案類型組織
- 高效的批次操作

### ✅ Flexibility
- 自動檢測專案類型
- 多種過濾和發現方式
- 自定義 templates

### ✅ Maintainability
- 清晰的目錄結構
- 模板化配置
- 容易添加新專案類型

### ✅ Usability
- 強大的 CLI
- Registry/Dataset 管理
- 詳細的統計報告

### ✅ Performance
- 平行執行
- 跳過已驗證
- Docker image 緩存

---

## Next Steps

1. **實作專案檢測系統** (1-2 days)
2. **建立多專案類型模板** (2-3 days)
3. **實作 Registry/Dataset 系統** (2-3 days)
4. **實作 Task Discovery** (1-2 days)
5. **CLI 整合** (1 day)
6. **測試多種專案類型** (2-3 days)

**Total: 9-14 days (2-3 weeks)**
