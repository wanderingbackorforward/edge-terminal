# Git 提交步骤 (供AI执行)

## 工作目录
```bash
cd /home/monss/tunnel-su-1/shield-tunneling-icp-backup
```

---

## 第一次提交：边缘端前端中文化

### 涉及文件
- edge-terminal/src/pages/Dashboard.tsx
- edge-terminal/src/pages/Rings.tsx
- edge-terminal/src/pages/Warnings.tsx
- edge-terminal/src/pages/Analytics.tsx
- edge-terminal/src/pages/Settings.tsx
- edge-terminal/src/components/layout/Header.tsx
- edge-terminal/src/components/layout/Sidebar.tsx
- edge-terminal/src/components/dashboard/WarningPanel.tsx
- edge-terminal/src/components/dashboard/RingOverview.tsx
- edge-terminal/src/components/charts/TrajectoryChart.tsx
- edge-terminal/src/components/ui/Table.tsx
- edge-terminal/src/components/ui/Button.tsx
- edge-terminal/src/components/ui/Badge.tsx

### 执行命令
```bash
git add edge-terminal/

git commit -m "feat(edge-terminal): 前端界面全部中文化

- Dashboard/Rings/Warnings/Analytics/Settings 页面中文化
- Header/Sidebar 布局组件中文化
- WarningPanel/RingOverview 业务组件中文化
- TrajectoryChart 图表中文化 (水平偏差/垂直偏差)
- Table 分页组件中文化 (第X页/共Y页)
- Button 组件添加 isLoading prop
- Badge 组件修复 className 处理"
```

---

## 第二次提交：云端预测引擎 + 部署配置

### 涉及文件
新增:
- cloud/api/models/ml_models.py
- cloud/api/routes/ml.py
- cloud/etl/dags/training_dag.py
- cloud/etl/dags/sync_dag.py
- cloud/etl/dags/drift_dag.py
- cloud/etl/tasks/__init__.py
- cloud/training/__init__.py
- cloud/training/trainer.py
- cloud/services/__init__.py
- scripts/cloud_start.sh
- scripts/init_airflow.sh
- docs/deployment/CLOUD_DEPLOYMENT.md

修改:
- cloud/api/main.py (添加 ML 路由注册)
- docker-compose.cloud.yml (添加 MLflow 服务)

### 执行命令
```bash
git add cloud/
git add docker-compose.cloud.yml
git add scripts/cloud_start.sh
git add scripts/init_airflow.sh
git add docs/deployment/CLOUD_DEPLOYMENT.md

git commit -m "feat(cloud): 云端预测引擎 + MLflow + 部署配置

云端 API:
- 新增 ML API 路由 (/api/ml/settlement/*)
- 集成 MLflow 进行模型注册和追踪

ETL 管道 (Airflow DAGs):
- training_dag: 模型训练管道
- sync_dag: 边缘数据同步 (每5分钟)
- drift_dag: 漂移检测与自动重训练

训练模块:
- SettlementTrainer 类，支持 MLflow + ONNX 导出

部署配置:
- docker-compose.cloud.yml 添加 MLflow 服务
- 云端部署文档 (CLOUD_DEPLOYMENT.md)
- 一键启动脚本 (cloud_start.sh)"
```

---

## 推送到远程 (可选)
```bash
git push origin main
```

---

## 验证
```bash
git log --oneline -3
```
