# Shield Tunneling ICP 部署指南

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                       Cloud 云端                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Cloud API   │  │  PostgreSQL  │  │   TimescaleDB │      │
│  │  (FastAPI)   │  │   Database   │  │   Extension   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Edge 边缘                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Edge API    │  │   SQLite     │  │  ONNX Model  │      │
│  │  (FastAPI)   │  │   Database   │  │   Runtime    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  MQTT Broker │  │  Data Sync   │                        │
│  │  (Mosquitto) │  │   Service    │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ WebSocket/MQTT
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Terminal 终端                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │  React + TypeScript + Ant Design + ECharts        │      │
│  │  Visualization Dashboard                          │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 环境要求

### Cloud 云端
- Python 3.10+
- PostgreSQL 14+ (with TimescaleDB extension)
- 4GB+ RAM
- 50GB+ 存储空间

### Edge 边缘
- Python 3.10+
- SQLite 3.35+
- 2GB+ RAM
- 10GB+ 存储空间
- MQTT Broker (Mosquitto recommended)

### Terminal 终端
- Node.js 18+
- 现代浏览器 (Chrome 90+, Firefox 90+, Safari 14+)

---

## 快速部署 (Docker)

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/shield-tunneling-icp.git
cd shield-tunneling-icp
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件配置数据库连接等
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 或分别启动
docker-compose up -d cloud-api
docker-compose up -d edge-api
docker-compose up -d terminal
```

### 4. 初始化数据库

```bash
# Cloud 数据库迁移
docker-compose exec cloud-api python -m cloud.db.migrate

# Edge 数据库初始化
docker-compose exec edge-api python -m edge.db.init
```

### 5. 验证部署

```bash
# 检查 Cloud API
curl http://localhost:8001/health

# 检查 Edge API
curl http://localhost:8000/health

# 访问 Terminal
open http://localhost:3000
```

---

## 手动部署

### Cloud API 部署

#### 1. 安装依赖

```bash
cd cloud
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. 配置 PostgreSQL

```bash
# 创建数据库
createdb shield_tunneling

# 安装 TimescaleDB 扩展
psql -d shield_tunneling -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

#### 3. 运行数据库迁移

```bash
# 依次执行迁移脚本
psql -d shield_tunneling -f database/migrations/cloud/001_projects.sql
psql -d shield_tunneling -f database/migrations/cloud/002_ring_summary_history.sql
# ... 继续执行其他迁移
```

#### 4. 启动服务

```bash
# 开发模式
python -m cloud.api.main

# 生产模式 (使用 gunicorn)
gunicorn cloud.api.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001
```

### Edge API 部署

#### 1. 安装依赖

```bash
cd edge
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. 安装 MQTT Broker

```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto

# Windows - 下载安装包
# https://mosquitto.org/download/
```

#### 3. 配置 Mosquitto

```bash
# /etc/mosquitto/mosquitto.conf
listener 1883
allow_anonymous true
```

#### 4. 启动服务

```bash
# 启动 Mosquitto
sudo systemctl start mosquitto

# 启动 Edge API
python -m edge.main
```

### Terminal 部署

#### 1. 安装依赖

```bash
cd terminal
npm install
```

#### 2. 配置环境

```bash
# .env.local
VITE_EDGE_API_URL=http://localhost:8000
VITE_CLOUD_API_URL=http://localhost:8001
VITE_MQTT_BROKER=ws://localhost:9001
```

#### 3. 构建和部署

```bash
# 开发模式
npm run dev

# 生产构建
npm run build

# 使用 nginx 部署
cp -r dist/* /var/www/shield-terminal/
```

---

## 生产环境配置

### Nginx 反向代理

```nginx
# /etc/nginx/sites-available/shield-tunneling

# Cloud API
server {
    listen 443 ssl;
    server_name cloud.shield.example.com;

    ssl_certificate /etc/ssl/certs/shield.crt;
    ssl_certificate_key /etc/ssl/private/shield.key;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Edge API (本地网络)
server {
    listen 80;
    server_name edge.local;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Terminal
server {
    listen 443 ssl;
    server_name shield.example.com;

    ssl_certificate /etc/ssl/certs/shield.crt;
    ssl_certificate_key /etc/ssl/private/shield.key;

    root /var/www/shield-terminal;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Systemd 服务

```ini
# /etc/systemd/system/shield-cloud-api.service
[Unit]
Description=Shield Tunneling Cloud API
After=network.target postgresql.service

[Service]
Type=simple
User=shield
WorkingDirectory=/opt/shield-tunneling/cloud
ExecStart=/opt/shield-tunneling/cloud/venv/bin/gunicorn cloud.api.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/shield-edge-api.service
[Unit]
Description=Shield Tunneling Edge API
After=network.target mosquitto.service

[Service]
Type=simple
User=shield
WorkingDirectory=/opt/shield-tunneling/edge
ExecStart=/opt/shield-tunneling/edge/venv/bin/python -m edge.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable shield-cloud-api shield-edge-api
sudo systemctl start shield-cloud-api shield-edge-api
```

---

## 监控和日志

### 日志位置

```
/var/log/shield-tunneling/
├── cloud-api.log
├── edge-api.log
├── sync.log
└── warnings.log
```

### 日志级别配置

```bash
# 环境变量
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Prometheus 指标 (可选)

Cloud API 和 Edge API 都暴露 `/metrics` 端点用于 Prometheus 监控。

---

## 故障排除

### 常见问题

#### 1. 数据库连接失败

```bash
# 检查 PostgreSQL 服务
sudo systemctl status postgresql

# 检查连接
psql -h localhost -U shield -d shield_tunneling
```

#### 2. MQTT 连接失败

```bash
# 检查 Mosquitto 服务
sudo systemctl status mosquitto

# 测试连接
mosquitto_sub -h localhost -t "shield/#" -v
```

#### 3. 模型加载失败

```bash
# 检查模型文件
ls -la /opt/shield-tunneling/edge/models/

# 检查 ONNX Runtime
python -c "import onnxruntime; print(onnxruntime.get_device())"
```

#### 4. 云同步失败

```bash
# 检查网络连接
curl -I http://cloud.shield.example.com/health

# 检查同步日志
tail -f /var/log/shield-tunneling/sync.log
```

---

## 备份和恢复

### 数据库备份

```bash
# Cloud PostgreSQL 备份
pg_dump -h localhost -U shield shield_tunneling > backup_$(date +%Y%m%d).sql

# Edge SQLite 备份
cp /opt/shield-tunneling/edge/data/edge.db backup_edge_$(date +%Y%m%d).db
```

### 模型备份

```bash
# 备份模型文件
tar -czf models_backup_$(date +%Y%m%d).tar.gz /opt/shield-tunneling/edge/models/
```

---

## 安全建议

1. **网络隔离**: Edge 设备应在独立网络中运行
2. **API 认证**: 生产环境启用 API Key 或 OAuth2 认证
3. **HTTPS**: 所有对外通信使用 HTTPS
4. **防火墙**: 仅开放必要端口 (8000, 8001, 1883, 443)
5. **日志审计**: 启用访问日志和操作审计
6. **定期更新**: 及时更新依赖包和系统补丁
