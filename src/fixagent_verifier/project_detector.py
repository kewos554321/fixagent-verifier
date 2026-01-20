"""Project type detection for automatic configuration."""

from enum import Enum
from pathlib import Path

import httpx


class ProjectType(str, Enum):
    """Supported project types."""

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
    """Detect project type from repository."""

    # Detection rules: file indicators -> project type
    DETECTION_RULES = {
        ProjectType.JAVA_GRADLE: [
            "build.gradle",
            "build.gradle.kts",
            "gradlew",
            "settings.gradle",
            "settings.gradle.kts",
        ],
        ProjectType.JAVA_MAVEN: [
            "pom.xml",
        ],
        ProjectType.NODEJS_NPM: [
            "package-lock.json",
        ],
        ProjectType.NODEJS_YARN: [
            "yarn.lock",
        ],
        ProjectType.PYTHON_PIP: [
            "requirements.txt",
            "setup.py",
        ],
        ProjectType.PYTHON_POETRY: [
            "poetry.lock",
        ],
        ProjectType.RUST_CARGO: [
            "Cargo.toml",
        ],
        ProjectType.GO_MOD: [
            "go.mod",
        ],
        ProjectType.DOTNET: [
            "*.csproj",
            "*.sln",
        ],
        ProjectType.RUBY_BUNDLER: [
            "Gemfile.lock",
        ],
    }

    async def detect_from_github(
        self,
        repo_owner: str,
        repo_name: str,
        branch: str = "main",
        github_token: str | None = None,
    ) -> ProjectType:
        """
        Detect project type from GitHub repository.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            branch: Branch to check (default: main)
            github_token: Optional GitHub token for API access

        Returns:
            Detected project type
        """
        base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents"
        headers = {"Accept": "application/vnd.github+json"}

        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    base_url, headers=headers, params={"ref": branch}, timeout=10.0
                )
                response.raise_for_status()
                files = response.json()

                # Get list of files in root directory
                file_names = [f["name"] for f in files if f["type"] == "file"]

                # Check detection rules
                for project_type, indicators in self.DETECTION_RULES.items():
                    for indicator in indicators:
                        if indicator in file_names:
                            return project_type

            except Exception:
                # Fallback to language detection
                pass

        # Fallback: use repository language
        return await self._detect_from_language(
            repo_owner, repo_name, github_token
        )

    async def _detect_from_language(
        self, repo_owner: str, repo_name: str, github_token: str | None
    ) -> ProjectType:
        """Detect from repository primary language."""
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/languages"
        headers = {"Accept": "application/vnd.github+json"}

        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                languages = response.json()

                if not languages:
                    return ProjectType.UNKNOWN

                # Get primary language
                primary_lang = max(languages.items(), key=lambda x: x[1])[0]

                # Map language to project type
                language_map = {
                    "Java": ProjectType.JAVA_GRADLE,
                    "JavaScript": ProjectType.NODEJS_NPM,
                    "TypeScript": ProjectType.NODEJS_NPM,
                    "Python": ProjectType.PYTHON_PIP,
                    "Rust": ProjectType.RUST_CARGO,
                    "Go": ProjectType.GO_MOD,
                    "C#": ProjectType.DOTNET,
                    "Ruby": ProjectType.RUBY_BUNDLER,
                }

                return language_map.get(primary_lang, ProjectType.UNKNOWN)

            except Exception:
                return ProjectType.UNKNOWN

    def detect_from_local(self, repo_path: Path) -> ProjectType:
        """
        Detect project type from local directory.

        Args:
            repo_path: Path to repository

        Returns:
            Detected project type
        """
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
