# Docker Compose Mode - Quick Start

## ✅ 實作完成！

Docker Compose 模式已經實作完成，使用 `<repo_name>_<pr_id>` 命名，編譯方式定義在 `docker-compose.yaml`。

---

## 快速開始

### 1. 生成 Task

```bash
# 自動檢測專案類型
uv run fixagent-verifier generate-compose \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1

# 輸出:
# ✓ Task generated successfully!
#    Location: tasks/springboot-aws-k8s_1
```

### 2. 查看生成的檔案

```bash
tree tasks/springboot-aws-k8s_1/

# tasks/springboot-aws-k8s_1/
# ├── docker-compose.yaml  # 完整的驗證流程
# ├── .env                 # PR 資訊和配置
# ├── README.md            # 使用說明
# └── logs/                # 結果目錄
#     └── verifier/
```

### 3. 執行驗證

**方式 A: 使用 CLI (推薦)**
```bash
uv run fixagent-verifier run-compose --task springboot-aws-k8s_1
```

**方式 B: 直接使用 docker compose**
```bash
cd tasks/springboot-aws-k8s_1/
docker compose up
```

### 4. 查看結果

```bash
# 檢查結果
cat tasks/springboot-aws-k8s_1/logs/verifier/result.txt
# 1 = 成功, 0 = 失敗

# 檢查 exit code
cat tasks/springboot-aws-k8s_1/logs/verifier/exit_code.txt

# 查看完整日誌
cd tasks/springboot-aws-k8s_1/
docker compose logs
```

---

## 批次操作

### 生成多個 Tasks

```bash
# 生成多個 PRs
uv run fixagent-verifier generate-compose --pr-url <url1>
uv run fixagent-verifier generate-compose --pr-url <url2>
uv run fixagent-verifier generate-compose --pr-url <url3>
```

### 批次執行

```bash
# 執行所有 tasks (4 個並行)
uv run fixagent-verifier run-all-compose --concurrent 4

# 執行特定 pattern 的 tasks
uv run fixagent-verifier run-all-compose --pattern "springboot-*" --concurrent 2

# 跳過已驗證的 tasks
uv run fixagent-verifier run-all-compose --skip-verified --concurrent 8
```

### 列出所有 Tasks

```bash
# 列出所有 tasks 和狀態
uv run fixagent-verifier list-compose

# 輸出:
# ┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━┓
# ┃ Task Name           ┃ PR  ┃ Status   ┃
# ┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━┩
# │ springboot-aws-k8s_1│ #1  │ ✓ Passed │
# │ react_789           │ #789│ ⋯ Not run│
# └─────────────────────┴─────┴──────────┘
```

---

## 支援的專案類型

已自動支援以下專案類型：

| 專案類型 | 檢測檔案 | Build Command |
|---------|---------|---------------|
| **Java Gradle** | build.gradle, gradlew | `./gradlew clean build -x test --no-daemon` |
| **Java Maven** | pom.xml | `mvn clean compile -DskipTests` |
| **Node.js NPM** | package-lock.json | `npm ci && npm run build` |
| **Node.js Yarn** | yarn.lock | `yarn install && yarn build` |
| **Python Pip** | requirements.txt | `pip install -r requirements.txt && python -m compileall .` |
| **Python Poetry** | poetry.lock | `poetry install && poetry build` |
| **Rust** | Cargo.toml | `cargo build --release` |
| **Go** | go.mod | `go build ./...` |

### 手動指定專案類型

```bash
uv run fixagent-verifier generate-compose \
  --pr-url <url> \
  --project-type java-maven
```

---

## Task 結構說明

### docker-compose.yaml

定義完整的驗證流程：
- **環境變數**: PR 資訊、專案配置
- **執行流程**: clone → merge → build
- **結果輸出**: 寫入 `/logs/verifier/result.txt`

### .env

包含所有配置變數：
```bash
PR_ID=1
REPO_URL=https://github.com/...
PROJECT_TYPE=java-gradle
BUILD_COMMAND=./gradlew clean build -x test
CPUS=2
MEMORY=4g
```

### README.md

每個 task 都有使用說明，包含：
- PR 資訊
- 專案配置
- 執行指令
- 查看結果方法

---

## 自定義配置

### 修改 Build Command

編輯 task 的 `.env` 或 `docker-compose.yaml`:

```bash
# 方式 1: 修改 .env
vim tasks/springboot-aws-k8s_1/.env
# 修改 BUILD_COMMAND 行

# 方式 2: 修改 docker-compose.yaml
vim tasks/springboot-aws-k8s_1/docker-compose.yaml
# 修改 BUILD_COMMAND 環境變數或 command 區塊
```

### 調整資源限制

```yaml
# docker-compose.yaml
services:
  verifier:
    cpus: 4        # 增加 CPU
    mem_limit: 8g  # 增加記憶體
```

### 啟用測試

```bash
# 修改 BUILD_COMMAND 移除 -x test
BUILD_COMMAND=./gradlew clean build --no-daemon
```

---

## 實際測試範例

```bash
# 1. 生成 task
uv run fixagent-verifier generate-compose \
  --pr-url https://github.com/kewos554321/springboot-aws-k8s/pull/1

# 2. 執行驗證
uv run fixagent-verifier run-compose --task springboot-aws-k8s_1

# 預期輸出:
# Running task: springboot-aws-k8s_1
#
# $ cd tasks/springboot-aws-k8s_1 && docker compose up
#
# [Container logs showing build process...]
#
# ✓ Verification PASSED
#    Exit code: 0
#    Results: tasks/springboot-aws-k8s_1/logs/verifier/
```

---

## 進階用法

### 多專案類型混合

```bash
# Java
uv run fixagent-verifier generate-compose \
  --pr-url https://github.com/spring-projects/spring-boot/pull/12345

# Node.js
uv run fixagent-verifier generate-compose \
  --pr-url https://github.com/facebook/react/pull/789

# Python
uv run fixagent-verifier generate-compose \
  --pr-url https://github.com/django/django/pull/456

# 批次執行所有
uv run fixagent-verifier run-all-compose --concurrent 3
```

### CI/CD 整合

```yaml
# .github/workflows/pr-verify.yml
name: PR Verification

on: pull_request

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install FixAgent Verifier
        run: pip install fixagent-verifier

      - name: Generate Task
        run: |
          fixagent-verifier generate-compose \
            --pr-url ${{ github.event.pull_request.html_url }}

      - name: Run Verification
        run: |
          TASK_NAME=$(ls tasks/ | head -1)
          fixagent-verifier run-compose --task $TASK_NAME
```

---

## Troubleshooting

### Docker 連接失敗

```bash
# 檢查 Docker daemon
docker ps

# 確認 Docker Compose 已安裝
docker compose version
```

### Task 執行卡住

```bash
# 查看容器狀態
docker ps -a | grep pr_

# 查看容器日誌
docker logs <container-id>

# 強制清理
cd tasks/springboot-aws-k8s_1/
docker compose down -v
```

### 結果檔案不存在

```bash
# 檢查日誌目錄
ls -la tasks/springboot-aws-k8s_1/logs/verifier/

# 手動進入容器檢查
docker exec -it pr_springboot-aws-k8s_1 bash
```

---

## 對比：舊方案 vs 新方案

| 特性 | 舊方案 (run-single) | 新方案 (compose) |
|------|-------------------|------------------|
| **Task 持久化** | ❌ 結果消失 | ✅ Task 目錄保留 |
| **可重新執行** | ❌ 需重新 fetch | ✅ 直接重跑 |
| **可分享** | ❌ 無法分享 | ✅ 分享 task 目錄 |
| **自定義** | ❌ 需改代碼 | ✅ 修改 compose/env |
| **多專案類型** | ⚠️ 手動指定 | ✅ 自動檢測 |
| **標準化** | ⚠️ 自定義格式 | ✅ Docker Compose |

---

## 總結

✅ **簡潔**: 每個 PR = 一個 task 目錄
✅ **標準**: 使用 Docker Compose
✅ **靈活**: 編譯方式在配置檔中
✅ **可攜**: 可分享 task 目錄
✅ **易用**: 自動檢測專案類型
✅ **高效**: 支援批次平行執行

你現在可以：
1. 生成 tasks
2. 批次執行
3. 分享 tasks
4. 自定義配置
5. CI/CD 整合

**開始使用:**
```bash
uv run fixagent-verifier generate-compose --pr-url <your-pr-url>
uv run fixagent-verifier run-compose --task <task-name>
```
