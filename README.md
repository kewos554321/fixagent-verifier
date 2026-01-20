# FixAgent Verifier

CLI tool for automated PR verification through isolated Docker environments.

## Features

- **Isolated Verification**: Each PR runs in its own Docker container
- **Git Merge Simulation**: Automatically clones, checks out, and merges PRs
- **Gradle Support**: Verifies Java/Gradle projects (Maven support planned)
- **Detailed Reporting**: Comprehensive logs and results for each verification

## Installation

### Requirements

- Python 3.12+
- Docker
- uv (recommended) or pip

### Setup

```bash
# Clone the repository
cd fixagent-verifier

# Install dependencies
uv sync

# Build Docker image
cd templates/java-gradle
bash build.sh
cd ../..
```

## Usage

### Verify a Single PR

```bash
# Set GitHub token (optional, for private repos or higher rate limits)
export GITHUB_TOKEN=your_github_token

# Run verification
uv run fixagent-verifier run-single \
  --pr-url https://github.com/owner/repo/pull/123 \
  --project-type gradle
```

### Command Options

- `--pr-url`: GitHub PR URL to verify (required)
- `--project-type`: Project type (default: gradle)
- `--output`, `-o`: Output directory (default: results)
- `--token`: GitHub API token (or set GITHUB_TOKEN env var)
- `--cpus`: CPU cores to allocate (default: 2)
- `--memory`: Memory in MB (default: 4096)
- `--timeout`: Verification timeout in seconds (default: 1800)

### Example

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1 \
  --project-type gradle \
  --output ./my-results \
  --cpus 4 \
  --memory 8192
```

## How It Works

1. **Fetch PR Info**: Retrieves PR metadata from GitHub API
2. **Start Docker**: Creates isolated container with Java/Gradle environment
3. **Clone & Merge**: Clones target repo and simulates PR merge
4. **Verify**: Runs `./gradlew clean build -x test` (compilation only for POC)
5. **Report**: Generates detailed results and logs

## Output Structure

```
results/
└── <trial-id>/
    ├── config.json           # Trial configuration
    ├── result.json           # Verification result
    ├── compilation.log       # Full compilation output
    └── exception.txt         # Exception traceback (if failed)
```

## Architecture

```
fixagent-verifier/
├── src/fixagent_verifier/
│   ├── cli/              # CLI interface (Typer)
│   ├── models/           # Pydantic data models
│   ├── github/           # GitHub API client
│   ├── environments/     # Docker environment
│   ├── verifier/         # Gradle/Maven verifiers
│   └── utils/            # Trial execution logic
├── templates/            # Dockerfile templates
│   └── java-gradle/      # Java/Gradle template
└── tests/                # Test suite
```

## Development

### Running Tests

```bash
uv run pytest tests/
```

### Code Formatting

```bash
uvx ruff format .
uvx ruff check --fix .
```

## Roadmap

### Phase 1 (POC) - Current
- [x] Single PR verification
- [x] Gradle compilation testing
- [x] Docker isolation
- [x] CLI interface

### Phase 2 - Planned
- [ ] PR registry support (JSON file with multiple PRs)
- [ ] Parallel execution
- [ ] Progress tracking with Rich
- [ ] Summary reports

### Phase 3 - Future
- [ ] Maven support
- [ ] Unit test execution
- [ ] Retry logic
- [ ] Custom verification scripts

### Phase 4 - Advanced
- [ ] Cloud execution (Daytona, Modal)
- [ ] Web UI
- [ ] GitHub webhook integration
- [ ] Metrics and analytics

## Contributing

Contributions welcome! Please check the [PLAN.md](PLAN.md) for detailed architecture and implementation plans.

## License

MIT
