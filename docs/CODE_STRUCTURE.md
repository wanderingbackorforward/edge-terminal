# Shield Tunneling ICP 代码结构与启动说明

本项目实现盾构智能控制平台的 **边缘采集/清洗、云端训练** 与 **可视化终端**。当前主要完成了边缘层的数据采集、清洗与环号对齐算法，云端与终端仍以目录骨架为主。本文档从目录结构、核心模块、运行方式与后续建设等角度对代码进行说明，并整理本地启动步骤。

## 1. 根目录速览

| 目录 | 内容 | 备注 |
| --- | --- | --- |
| `edge/` | Python 3.11+ 边缘服务（采集、清洗、环对齐、FastAPI 路由、SQLite ORM） | 当前最完整的模块 |
| `database/` | SQLite/WAL 表结构迁移脚本 | `migrations/edge/*.sql` |
| `cloud/` | 云端服务（API、ETL、训练）骨架 | 仅目录与 `requirements.txt` |
| `terminal/` | React + Vite 可视化终端 | 目录已划分，源码待补充 |
| `docs/` | 说明文档（当前文件等） | |
| `specs/` | 详细需求与分期计划 | `system-plan/plan.md` 1866 行 |
| `docker/` | 各子系统镜像目录（空） | |
| `scripts/` | 预留自动化脚本目录 | |
| `README.md`、`IMPLEMENTATION_STATUS.md` | 进度概览、已完成任务列表 | |

## 2. Edge 层结构（`edge/`）

### 2.1 服务流水线（`services/`）

| 子目录 | 关键文件 | 功能要点 |
| --- | --- | --- |
| `collector/` | `opcua_client.py`, `modbus_client.py`, `source_manager.py`, `buffer_writer.py` | OPC UA/Modbus 采集、统一缓冲写库、数据源管理（含质量管线） |
| `cleaner/` | `threshold_validator.py`, `interpolator.py`, `reasonableness_checker.py`, `calibration.py`, `quality_metrics.py` | 工程阈值校验、插值补点、物理合理性校验、偏移校正、质量指标 |
| `aligner/` | `aggregator.py` | `align_data()` 实现 9 步环号特征聚合（PLC + 姿态 + 衍生指标 + 沉降延迟匹配） |
| `sync/`, `inference/`, `warning/`, `notification/`, `workorder/` | （待实现） | 目录已建，用于后续云同步、推理、预警、告警路由、工单等 |

### 2.2 API 与数据库

- `api/routes/health.py`, `manual_logs.py`, `rings.py`：FastAPI 路由与 Pydantic 响应模型，尚未在 `edge/main.py` 中组合应用（T060 待完成）。
- `models/*.py`：SQLAlchemy ORM（PLCLog、AttitudeLog、MonitoringLog、RingSummary）。
- `database/manager.py`：封装 SQLite/WAL 连接、事务、查询工具，默认数据库路径 `data/edge.db`，会自动创建数据目录。

### 2.3 配置与测试

- `config/*.yaml`：采集源、阈值、对齐参数、物理规则、校准参数等。
- `requirements.txt`：已将 `onnxruntime` 提升到 `1.17.3`（兼容 Python 3.12）。
- `pytest.ini`：开启 `pytest-cov`，当前阈值设为 0 以避免在测试用例尚未补齐时阻塞流水线。
- `tests/`：`unit/` 目录新增 `test_placeholder.py`，用于占位；`integration/`、`performance/`、`contract/` 尚未开始。

## 3. 数据库迁移（`database/migrations/edge`）

1. `001_plc_logs.sql`：高频 PLC 表（`plc_logs`）及索引。
2. `002_attitude_logs.sql`：姿态数据表。
3. `003_monitoring_logs.sql`：监测/沉降数据。
4. `004_ring_summary.sql`：环汇总及工程指标。
5. `005_wal_indexes.sql`：WAL/索引优化脚本。

所有迁移均可直接用 `sqlite3 data/edge.db < xxx.sql` 执行，`DatabaseManager` 也会将连接设置为 WAL + `PRAGMA synchronous=NORMAL`。

## 4. Cloud 层（`cloud/`）

目录包含：

- `api/`、`database/`、`etl/`、`models/`、`training/` 等占位目录；
- `requirements.txt` 覆盖 Supabase/Postgres、Airflow/Prefect、ML/ONNX Export 等依赖；
- `tests/` 目录尚无内容。

目前尚未实现具体逻辑，可在补齐前先按 `requirements.txt` 准备虚拟环境。

## 5. Terminal 层（`terminal/`）

- `package.json`：React 18 + Vite + Ant Design + ECharts，脚本包括 `dev`、`build`、`test`、`lint`、`format`、`test:e2e`。
- `src/` 下划分 `components/`, `pages/`, `hooks/`, `services/`, `types/`, `utils/`，暂未填充代码。
- `tests/` 目录预留给端到端/组件测试。

## 6. 规格与文档

- `specs/system-plan/plan.md`：系统级蓝图、时序、数据流、任务列表（包含 T060 Main FastAPI Application 等未完成项）。
- `SESSION_SUMMARY.md`、`IMPLEMENTATION_STATUS.md`：阶段总结与任务完成度。
- `docs/`：当前文件与未来的架构/部署文档存放处。

## 7. 启动指南（着重步骤）

### 7.1 环境前提

- Python 3.11+（实验环境中使用 `python3 -m venv .venv` 创建虚拟环境）。
- Node.js 18+（用于终端开发环境）。
- SQLite 3.40+（支持 WAL）。
- 可选：OPC UA/Modbus 仿真服务器（若需调试数据采集）。

### 7.2 Edge 服务

1. **虚拟环境 & 依赖**
   ```bash
   cd shield-tunneling-icp
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r edge/requirements.txt  # onnxruntime==1.17.3 兼容 Python 3.12
   ```
2. **初始化数据库**
   ```bash
   mkdir -p data
   cd database/migrations/edge
   for file in 00*.sql; do
       sqlite3 ../../../data/edge.db < "$file"
   done
   sqlite3 ../../../data/edge.db ".tables"
   ```
3. **运行数据采集/清洗（示例）**
   ```bash
   cd edge
   python services/collector/source_manager.py
   ```
   - `edge/config/sources.yaml` 控制 OPC UA、Modbus、REST、人工录入等数据源。
   - SourceManager 会按配置加载 `ThresholdValidator → Interpolator → ReasonablenessChecker → Calibration → QualityMetrics` 管线，并通过 `BufferWriter` 批量入库。
4. **触发环号对齐**
   ```bash
   cd edge
   python - <<'PY'
   from edge.database.manager import DatabaseManager
   from edge.services.aligner.aggregator import align_data

   db = DatabaseManager("data/edge.db")
   result = align_data(ring_number=120, db=db)
   print(result["ring_number"], result["data_completeness_flag"])
   PY
   ```
5. **FastAPI 路由**
   - `api/routes/health.py`, `manual_logs.py`, `rings.py` 已提供 `APIRouter`。
   - 尚未实现 `edge/main.py`（T060），无法直接 `uvicorn edge.main:app`。如需临时体验，可手动创建一个 `FastAPI()` 实例并包含上述 router。

### 7.3 终端（Visualization Terminal）

```bash
cd terminal
npm install
npm run dev   # Vite 默认 http://localhost:5173
npm run test  # Jest + Testing Library
```

在补充 UI 代码后，可使用 `npm run build` 生成生产包。

### 7.4 云端服务（准备阶段）

```bash
cd cloud
python3 -m venv .venv-cloud
source .venv-cloud/bin/activate
pip install -r requirements.txt  # 依赖较多，建议按模块逐步引入
```

后续将实现 Supabase/Postgres 同步、Airflow/Pefect ETL、训练与 ONNX 导出。

### 7.5 测试与质量

- 边缘层单测：`cd edge && pytest`
  - 目前仅有 `tests/unit/test_placeholder.py`，作为骨架以防止 `pytest` 报告 “no tests found”。
  - `pytest.ini` 会自动启用覆盖率报告（`htmlcov/`、`coverage.xml`）。
- 代码质量工具（安装在同一虚拟环境）：`black`, `flake8`, `mypy` 等，可直接运行。

## 8. 当前技术债 & 建议

1. **主 FastAPI 应用缺失**：需要实现 `edge/main.py` 将 `api/routes/*` 装载并配置启动/关闭钩子。
2. **真实测试集缺失**：目前仅有占位测试；在实现核心逻辑后应补齐单元/集成/性能/契约测试，并逐步恢复 `--cov-fail-under=90`。
3. **云端、终端代码为空**：仅目录结构，需按照 `specs/` 规划逐步填充。
4. **配置与凭证管理**：后续需将 OPC UA/Modbus/Supabase 凭证迁移至 `.env` 或 Secret Store（`pydantic-settings` 已在依赖中）。
5. **Docker & 自动化**：`docker/`、`scripts/` 尚无内容，可在完成核心服务后再补充容器编排与 CI 脚本。

---

有了以上说明，即可快速了解仓库结构与各模块职责，并按步骤完成环境准备、数据库初始化与边缘服务启动。后续开发可依据 `specs/` 中的里程碑补足云端与终端，实现端到端智能控制闭环。
