# Architecture Comparison: Current vs Task Mode

## Visual Comparison

### Current Architecture (Procedural)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User CLI                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   GitHub API (fetch PR info)  │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   Create Docker Environment   │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   Clone Repo & Merge PR       │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   Run Gradle Build            │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   Save Results & Cleanup      │
         └───────────────────────────────┘

Everything is ephemeral - nothing persists between runs
```

### Task Mode Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User CLI                                │
└────┬──────────────────────────────────────────────┬─────────────┘
     │                                               │
     │ (generate)                                    │ (run)
     ▼                                               ▼
┌─────────────────┐                    ┌──────────────────────────┐
│ Task Generator  │                    │   Verification Harness   │
└────────┬────────┘                    └────────────┬─────────────┘
         │                                          │
         ▼                                          │
┌─────────────────────────────────────┐            │
│      Task Directory Created         │◄───────────┘
│  (Persistent, Reusable, Shareable)  │
│                                     │
│  ├── task.yaml                      │
│  ├── Dockerfile                     │
│  ├── run-tests.sh                   │
│  └── tests/                         │
│      └── test_compilation.py        │
└─────────────────────────────────────┘
         │
         │ (cached, reusable)
         ▼
┌─────────────────────────────────────┐
│     Docker Environment              │
│     (from task's Dockerfile)        │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  run-tests.sh execution             │
│  (self-contained verification)      │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Results saved with task reference  │
└─────────────────────────────────────┘

Tasks persist and can be reused, shared, and distributed
```

## Key Differences

### 1. Data Flow

**Current (Procedural):**
```
PR URL → fetch → build → test → dispose
(Linear, ephemeral, not reusable)
```

**Task Mode:**
```
PR URL → generate task → [persistent task] → run → results
                              ↓
                         (reusable, shareable, cacheable)
```

### 2. File Organization

**Current:**
```
results/
└── <trial-id>/
    ├── config.json
    ├── result.json
    └── compilation.log

(Only results persist, no task definition)
```

**Task Mode:**
```
tasks/
└── pr-123__owner-repo/
    ├── task.yaml          # Complete definition
    ├── Dockerfile         # Environment spec
    ├── run-tests.sh       # Verification logic
    └── tests/
        └── test_compilation.py

results/
└── pr-123__owner-repo__<trial-id>/
    ├── result.json
    └── compilation.log
```

### 3. Workflow Comparison

**Current (One-step):**
```bash
# Everything happens at once
fixagent-verifier run-single --pr-url https://github.com/owner/repo/pull/123

# Want to rerun? Must re-fetch from GitHub
fixagent-verifier run-single --pr-url https://github.com/owner/repo/pull/123
```

**Task Mode (Two-step, but cacheable):**
```bash
# Step 1: Generate task (once)
fixagent-verifier generate --pr-url https://github.com/owner/repo/pull/123

# Step 2: Run task (many times)
fixagent-verifier run --task-id pr-123__owner-repo

# Rerun without GitHub API call
fixagent-verifier run --task-id pr-123__owner-repo

# Or use quick mode for one-step
fixagent-verifier quick --pr-url https://github.com/owner/repo/pull/123
```

## Feature Comparison Matrix

| Feature | Current | Task Mode | Winner |
|---------|---------|-----------|--------|
| **Single PR verification** | ✅ Simple | ✅ Simple (quick mode) | 🤝 Tie |
| **Batch verification** | ❌ Not supported | ✅ Registry-based | 🏆 Task |
| **Rerunning verifications** | ❌ Re-fetches PR | ✅ Uses cached task | 🏆 Task |
| **Sharing verifications** | ❌ Can't share | ✅ Share task dirs | 🏆 Task |
| **Resume interrupted runs** | ❌ Not supported | ✅ Lock files | 🏆 Task |
| **Custom verification** | ❌ Hard to customize | ✅ Edit run-tests.sh | 🏆 Task |
| **Parallel execution** | ✅ Supported | ✅ Better organized | 🏆 Task |
| **Debugging** | ⚠️ Logs only | ✅ Full task context | 🏆 Task |
| **Initial complexity** | ✅ Very simple | ⚠️ More files | 🏆 Current |
| **Disk usage** | ✅ Minimal | ⚠️ More files | 🏆 Current |

**Score: Task Mode wins 8-2**

## Use Case Analysis

### Use Case 1: Quick PR Check
**Scenario:** Developer wants to quickly verify a single PR

**Current:**
```bash
fixagent-verifier run-single --pr-url <url>
# ✅ Simple, one command
# ❌ Must wait for GitHub API fetch
# ❌ Can't rerun without re-fetching
```

**Task Mode:**
```bash
fixagent-verifier quick --pr-url <url>
# ✅ Same simplicity (quick mode)
# ✅ Task cached for future reruns
# ✅ Can debug by inspecting task dir
```

**Winner: Task Mode** (same UX, more benefits)

---

### Use Case 2: CI/CD Integration
**Scenario:** Verify all open PRs in a repository nightly

**Current:**
```bash
# Must script PR fetching and loop
for pr in $(get_prs); do
  fixagent-verifier run-single --pr-url $pr
done
# ❌ Sequential execution
# ❌ No resume if interrupted
# ❌ Re-fetches same PRs each night
```

**Task Mode:**
```bash
# Generate tasks once
fixagent-verifier generate-from-registry --registry prs.yaml

# Run in parallel
fixagent-verifier run --concurrent 10

# Resume if interrupted
fixagent-verifier resume --run-id <id>
# ✅ Parallel execution built-in
# ✅ Resume support
# ✅ Tasks cached, no re-fetching
```

**Winner: Task Mode** (built for this use case)

---

### Use Case 3: Debugging Failed Verification
**Scenario:** A PR verification failed, need to investigate

**Current:**
```bash
# Check logs
cat results/<trial-id>/compilation.log

# Want to rerun with changes?
# ❌ Must modify source code
# ❌ No way to customize verification for one PR
```

**Task Mode:**
```bash
# Check logs
cat results/pr-123__owner-repo__<trial-id>/compilation.log

# Inspect task
cd tasks/pr-123__owner-repo/
cat task.yaml
cat run-tests.sh

# Customize verification
vim run-tests.sh  # Add debug flags, etc.

# Rerun with custom changes
fixagent-verifier run --task-id pr-123__owner-repo

# ✅ Can customize per-task
# ✅ Full context available
# ✅ Easy to iterate
```

**Winner: Task Mode** (much better debugging)

---

### Use Case 4: Sharing Verification Setup
**Scenario:** Team wants to share PR verification configurations

**Current:**
```bash
# No way to share except:
# 1. Share PR URL (recipient must re-fetch)
# 2. Share result files (no way to rerun)
# ❌ Not shareable
```

**Task Mode:**
```bash
# Share entire task directory
tar -czf pr-123-task.tar.gz tasks/pr-123__owner-repo/
# Recipient can:
tar -xzf pr-123-task.tar.gz -C tasks/
fixagent-verifier run --task-id pr-123__owner-repo

# ✅ Fully shareable
# ✅ Recipient gets exact same environment
# ✅ Can be version controlled
```

**Winner: Task Mode** (enables collaboration)

---

## Performance Comparison

### Scenario: Verify 100 PRs from a registry

**Current Architecture:**
```
For each PR:
  1. Fetch PR info from GitHub API    (~1s)
  2. Build Docker image               (~30s, first time)
  3. Clone repo                       (~10s)
  4. Merge PR                         (~2s)
  5. Run compilation                  (~60s)
  6. Cleanup                          (~5s)

Total per PR: ~108s (first run)
Total per PR: ~78s (cached image)

100 PRs @ 4 concurrent = ~27 minutes (cached)
```

**Task Mode Architecture:**
```
Phase 1: Generate Tasks (one-time)
  For each PR:
    1. Fetch PR info from GitHub API  (~1s)
    2. Generate task directory        (~0.1s)
  Total: ~110s for 100 PRs

Phase 2: Run Tasks (can run multiple times)
  For each task:
    1. Load task config               (~0.01s)
    2. Build Docker image (cached)    (~5s)
    3. Run run-tests.sh               (~75s)
    4. Cleanup                        (~5s)
  Total per task: ~85s

100 tasks @ 4 concurrent = ~22 minutes

Reruns (tasks already generated):
  100 tasks @ 4 concurrent = ~22 minutes (no GitHub API calls)
```

**Performance Winner: Task Mode**
- First run: Similar performance
- Subsequent runs: 20% faster (no GitHub API calls)
- Better caching of Docker images
- Can skip already-verified tasks

---

## Migration Complexity

### Effort Required

**Current → Task Mode Migration:**

| Component | Effort | Complexity | Notes |
|-----------|--------|------------|-------|
| Task Generator | 2-3 days | Medium | New component, but straightforward |
| YAML Templates | 1 day | Low | Simple templating with Jinja2 |
| Harness Refactor | 3-4 days | Medium | Reuse existing Docker code |
| CLI Updates | 2 days | Low | Add new commands, keep old ones |
| Documentation | 1 day | Low | Update README, add examples |
| Testing | 2-3 days | Medium | Test task generation + execution |

**Total: 11-15 days** (2-3 weeks)

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking changes | Low | Medium | Keep backward compatibility |
| Performance regression | Low | Medium | Benchmark both approaches |
| User confusion | Medium | Low | Good documentation, quick mode |
| Disk space issues | Low | Low | Task cleanup command |

---

## Recommendation Matrix

### When to Use Current Architecture
- ✅ Absolute simplicity is required
- ✅ Only verifying 1-2 PRs occasionally
- ✅ No need for reruns
- ✅ No need for sharing
- ✅ Disk space is severely constrained

### When to Use Task Mode
- ✅ **Verifying many PRs regularly** ⭐
- ✅ **Need to rerun verifications** ⭐
- ✅ **Want to share verification setups** ⭐
- ✅ **Need resume support**
- ✅ **Want custom verification per PR**
- ✅ **Debugging failed verifications**
- ✅ **CI/CD integration**
- ✅ **Building a verification library**

## Final Recommendation

**Adopt Task Mode Architecture** ✅

**Reasoning:**
1. **Aligns with Industry Standards**: Terminal-Bench and Harbor both use this pattern
2. **Better UX**: Can rerun, share, customize without complexity
3. **Future-Proof**: Easy to add features (caching, resume, registry)
4. **Minimal Downside**: Keep backward compatibility with `run-single` command
5. **User Choice**: Offer both `quick` (one-step) and `generate`+`run` (two-step)

**Implementation Strategy:**
1. Keep current `run-single` command as-is
2. Add new task-mode commands (`generate`, `run`, `quick`)
3. Make `quick` the recommended default for new users
4. Deprecate `run-single` after 6 months
5. Full migration to task mode in version 2.0

This provides a smooth transition with no breaking changes.
