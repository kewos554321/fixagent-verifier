# FixAgent Verifier - Quick Start Guide

## Implementation Complete! ✓

Your PR verification tool is now fully functional. Here's what was built:

### What's Working

✓ **GitHub Integration** - Fetches PR metadata from GitHub API
✓ **Docker Isolation** - Each PR runs in its own container
✓ **Git Merge Simulation** - Automatically clones and merges PRs
✓ **Gradle Verification** - Compiles Java/Gradle projects
✓ **Result Reporting** - Detailed logs and JSON results
✓ **CLI Interface** - User-friendly command-line tool

### Test Results

Successfully verified: https://github.com/kewos554321/springboot-aws-k8s/pull/1

```
✓ Verification PASSED
✓ Duration: 69.6s
✓ Tasks Run: clean, build
✓ Total Duration: 85.1s
```

## Usage

### Basic Command

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/owner/repo/pull/123
```

### With Options

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1 \
  --project-type gradle \
  --cpus 4 \
  --memory 8192 \
  --timeout 3600 \
  --output ./my-results
```

### Using GitHub Token (for private repos)

```bash
export GITHUB_TOKEN=your_token_here

uv run fixagent-verifier run-single \
  --pr-url https://github.com/private-org/private-repo/pull/123
```

## Output Structure

After verification, you'll get:

```
results/<trial-id>/
├── config.json           # Trial configuration
├── result.json          # Full verification result
└── compilation.log      # Complete build output
```

### Result JSON Structure

```json
{
  "trial_id": "uuid",
  "pr_number": 1,
  "pr_url": "...",
  "verification_result": {
    "success": true,
    "duration_sec": 69.6,
    "tasks_run": ["clean", "build"],
    "compilation_output": "..."
  },
  "started_at": "2026-01-20T21:48:12",
  "finished_at": "2026-01-20T21:49:37"
}
```

## Architecture Overview

```
PR URL → GitHub API → Clone Repo → Merge PR → Docker Container → Gradle Build → Results
```

### Components Implemented

1. **GitHub Client** (`github/client.py`)
   - Fetches PR metadata (branches, commits, repo info)
   - Parses PR URLs
   - Handles authentication

2. **Docker Environment** (`environments/docker.py`)
   - Creates isolated containers
   - Manages container lifecycle
   - Executes commands in containers
   - Handles file uploads/downloads

3. **Gradle Verifier** (`verifier/gradle.py`)
   - Detects gradle wrapper
   - Runs compilation (`clean build -x test`)
   - Captures output and timing
   - Determines success/failure

4. **Trial Execution** (`utils/trial.py`)
   - Orchestrates the entire flow
   - Handles errors gracefully
   - Saves results and logs

5. **CLI Interface** (`cli/main.py`)
   - User-friendly command interface
   - Beautiful terminal output (Rich)
   - Progress indication
   - Result visualization

## Next Steps (Phase 2)

To extend the tool, you can add:

### 1. PR Registry Support

Create a `pr-registry.json`:

```json
{
  "name": "my-prs",
  "prs": [
    {
      "pr_url": "https://github.com/owner/repo/pull/1",
      "project_type": "gradle"
    },
    {
      "pr_url": "https://github.com/owner/repo/pull/2",
      "project_type": "gradle"
    }
  ]
}
```

### 2. Parallel Execution

Verify multiple PRs concurrently:

```bash
fixagent-verifier run \
  --registry pr-registry.json \
  --concurrent 4
```

### 3. Unit Test Support

Extend `GradleVerifier` to run tests:

```python
# Change from:
build_cmd = f"{gradle_cmd} clean build -x test"

# To:
build_cmd = f"{gradle_cmd} clean build test"
```

### 4. Maven Support

Create `MavenVerifier` in `verifier/maven.py`:

```python
class MavenVerifier(BaseVerifier):
    async def verify(self, environment, timeout_sec):
        # Run: mvn clean compile
        ...
```

## Troubleshooting

### Docker Image Not Found

```bash
cd templates/java-gradle
bash build.sh
```

### GitHub API Rate Limit

Use a GitHub token:

```bash
export GITHUB_TOKEN=your_token
```

### Container Issues

Check running containers:

```bash
docker ps -a | grep fixagent
```

Clean up containers:

```bash
docker ps -a | grep fixagent | awk '{print $1}' | xargs docker rm -f
```

### Build Failures

Check the compilation log:

```bash
cat results/<trial-id>/compilation.log
```

## Examples

### Verify Spring Boot PR

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/spring-projects/spring-boot/pull/12345
```

### Verify with Higher Resources

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/apache/kafka/pull/6789 \
  --cpus 8 \
  --memory 16384 \
  --timeout 3600
```

### Save to Custom Location

```bash
uv run fixagent-verifier run-single \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1 \
  --output ./verification-results
```

## Performance Notes

- **First Run**: ~70-90s (downloads Gradle)
- **Subsequent Runs**: Faster (Gradle cached in container)
- **Container Overhead**: ~5-10s
- **Git Clone**: ~5-15s (depends on repo size)
- **Compilation**: Varies by project

## Development

### Project Structure

```
fixagent-verifier/
├── src/fixagent_verifier/
│   ├── cli/              # CLI interface
│   ├── models/           # Data models
│   ├── github/           # GitHub API client
│   ├── environments/     # Docker environment
│   ├── verifier/         # Gradle verifier
│   └── utils/            # Trial execution
├── templates/
│   └── java-gradle/      # Docker template
│       ├── Dockerfile
│       └── build.sh
├── pyproject.toml        # Dependencies
└── README.md
```

### Run Tests

```bash
uv run pytest tests/
```

### Format Code

```bash
uvx ruff format .
uvx ruff check --fix .
```

## Success! 🎉

You now have a working PR verification tool that:

- Fetches PR info from GitHub ✓
- Clones and merges PRs in Docker ✓
- Verifies Gradle compilation ✓
- Generates detailed reports ✓
- Has a beautiful CLI ✓

**Verified PR:** https://github.com/kewos554321/springboot-aws-k8s/pull/1
**Status:** PASSED ✓
**Duration:** 85.1s
