# Shield Tunneling ICP 配置参考

## 环境变量配置

### Cloud API 配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| DATABASE_URL | PostgreSQL 连接字符串 | - | 是 |
| LOG_LEVEL | 日志级别 | INFO | 否 |
| CORS_ORIGINS | 允许的跨域来源 | * | 否 |
| API_KEY | API 认证密钥 | - | 生产必填 |

```bash
# .env 示例
DATABASE_URL=postgresql://shield:password@localhost:5432/shield_tunneling
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,https://shield.example.com
API_KEY=your-secret-api-key
```

### Edge API 配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| EDGE_DB_PATH | SQLite 数据库路径 | ./data/edge.db | 否 |
| CLOUD_API_URL | Cloud API 地址 | http://localhost:8001 | 是 |
| MQTT_BROKER_HOST | MQTT Broker 地址 | localhost | 否 |
| MQTT_BROKER_PORT | MQTT Broker 端口 | 1883 | 否 |
| MODELS_DIR | 模型存储目录 | ./models | 否 |
| SYNC_INTERVAL | 同步间隔(秒) | 300 | 否 |
| LOG_LEVEL | 日志级别 | INFO | 否 |

```bash
# .env 示例
EDGE_DB_PATH=/opt/shield-tunneling/edge/data/edge.db
CLOUD_API_URL=https://cloud.shield.example.com
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MODELS_DIR=/opt/shield-tunneling/edge/models
SYNC_INTERVAL=300
LOG_LEVEL=INFO
```

### Terminal 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| VITE_EDGE_API_URL | Edge API 地址 | http://localhost:8000 |
| VITE_CLOUD_API_URL | Cloud API 地址 | http://localhost:8001 |
| VITE_MQTT_BROKER | MQTT WebSocket 地址 | ws://localhost:9001 |
| VITE_PROJECT_ID | 项目 ID | 1 |

```bash
# .env.local 示例
VITE_EDGE_API_URL=http://192.168.1.100:8000
VITE_CLOUD_API_URL=https://cloud.shield.example.com
VITE_MQTT_BROKER=ws://192.168.1.100:9001
VITE_PROJECT_ID=1
```

---

## 告警阈值配置

### warnings.yaml

```yaml
# edge/config/warnings.yaml

# 沉降阈值配置
settlement:
  attention_threshold: 27.0  # mm - 90% of warning
  warning_threshold: 30.0    # mm
  alarm_threshold: 40.0      # mm
  rate_threshold: 2.0        # mm/ring - 变化率

# 土仓压力阈值配置
chamber_pressure:
  attention_threshold: 270.0  # kPa
  warning_threshold: 280.0    # kPa
  alarm_threshold: 300.0      # kPa
  rate_threshold: 10.0        # kPa/ring

# 刀盘扭矩阈值配置
torque:
  attention_threshold: 900.0  # kN·m
  warning_threshold: 950.0    # kN·m
  alarm_threshold: 1000.0     # kN·m
  rate_threshold: 50.0        # kN·m/ring

# 轴线偏差阈值配置
horizontal_deviation:
  attention_threshold: 40.0   # mm
  warning_threshold: 50.0     # mm
  alarm_threshold: 70.0       # mm

vertical_deviation:
  attention_threshold: 30.0   # mm
  warning_threshold: 40.0     # mm
  alarm_threshold: 60.0       # mm

# 通用配置
general:
  hysteresis_percent: 5.0     # 滞后百分比
  min_data_points: 5          # 最少数据点
  evaluation_window: 10       # 评估窗口(环数)

# 地质分区特定配置
geological_zones:
  soft_clay:
    settlement_alarm_threshold: 35.0
    settlement_warning_threshold: 25.0
  sand:
    settlement_alarm_threshold: 45.0
    settlement_warning_threshold: 35.0
  rock:
    settlement_alarm_threshold: 20.0
    settlement_warning_threshold: 15.0
```

---

## 通知渠道配置

### Email 配置

```yaml
# 数据库或 API 配置
channel_type: email
channel_name: "主邮箱通知"
config:
  smtp_host: "smtp.example.com"
  smtp_port: 587
  smtp_user: "alerts@example.com"
  smtp_password: "encrypted_password"
  from_address: "alerts@example.com"
  use_tls: true
```

### SMS 配置

```yaml
channel_type: sms
channel_name: "紧急短信"
config:
  provider: "aliyun"  # aliyun, twilio, generic
  api_url: "https://dysmsapi.aliyuncs.com"
  api_key: "your_access_key"
  api_secret: "your_access_secret"
  from_number: "+8612345678"
  template_code: "SMS_123456789"
```

### Webhook 配置

```yaml
channel_type: webhook
channel_name: "企业微信"
config:
  url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
  method: "POST"
  headers:
    Content-Type: "application/json"
  # 可选: 自定义模板
  template: |
    {
      "msgtype": "markdown",
      "markdown": {
        "content": "**${subject}**\n${message}"
      }
    }
```

---

## 责任矩阵配置

### 默认角色

| 角色代码 | 角色名称 | 优先级 |
|----------|----------|--------|
| OPERATOR | 操作员 | 1 |
| SHIFT_LEAD | 班组长 | 2 |
| TECH_ENGINEER | 技术工程师 | 3 |
| SAFETY_OFFICER | 安全员 | 3 |
| PROJECT_ENGINEER | 项目工程师 | 4 |
| PROJECT_MANAGER | 项目经理 | 5 |

### 责任分配规则

```yaml
# 示例: 沉降问题责任分配
- category: settlement
  priority: critical
  warning_level: ALARM
  primary_role: PROJECT_ENGINEER
  secondary_role: PROJECT_MANAGER
  auto_assign: true
  escalation_hours: 2.0

- category: settlement
  priority: high
  warning_level: WARNING
  primary_role: TECH_ENGINEER
  secondary_role: PROJECT_ENGINEER
  auto_assign: true
  escalation_hours: 4.0

# 土仓压力问题
- category: chamber_pressure
  priority: critical
  primary_role: SHIFT_LEAD
  secondary_role: TECH_ENGINEER
  auto_assign: true
  escalation_hours: 1.0

# 设备维护
- category: maintenance
  priority: medium
  primary_role: OPERATOR
  secondary_role: SHIFT_LEAD
  auto_assign: false
  escalation_hours: 8.0
```

---

## 模型配置

### 模型部署配置

```yaml
# edge/config/models.yaml

model_deployment:
  auto_deploy: true
  check_interval_hours: 6.0
  validation_required: true
  rollback_on_failure: true

# 模型性能监控
performance_monitoring:
  evaluation_interval_rings: 50
  drift_threshold_rmse_percent: 20.0
  min_samples_for_evaluation: 30
  retrain_trigger_enabled: true

# 特征工程配置
feature_engineering:
  version: "1.0.0"
  window_size: 10
  include_geological: true
  include_historical_stats: true
```

---

## 同步配置

### 数据同步策略

```yaml
# edge/config/sync.yaml

sync:
  # 同步间隔
  interval_seconds: 300

  # 批次大小
  batch_size:
    ring_summaries: 50
    predictions: 100
    warnings: 50
    work_orders: 20

  # 重试策略
  retry:
    max_attempts: 3
    backoff_seconds: 60
    exponential: true

  # 离线模式
  offline:
    enabled: true
    max_queue_size: 10000
    persist_queue: true
```

---

## MQTT 配置

### Mosquitto 配置

```conf
# /etc/mosquitto/mosquitto.conf

# 基础配置
listener 1883
protocol mqtt

# WebSocket 支持 (用于 Terminal)
listener 9001
protocol websockets

# 认证 (生产环境)
# password_file /etc/mosquitto/passwd
# allow_anonymous false

# 日志
log_dest file /var/log/mosquitto/mosquitto.log
log_type all

# 持久化
persistence true
persistence_location /var/lib/mosquitto/

# QoS
max_inflight_messages 100
max_queued_messages 1000
```

---

## 数据库配置

### PostgreSQL 优化

```sql
-- 推荐的 PostgreSQL 配置
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET max_connections = '100';

-- TimescaleDB 配置
ALTER SYSTEM SET timescaledb.max_background_workers = 4;

SELECT pg_reload_conf();
```

### SQLite 优化

```python
# Edge SQLite 配置
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  # 64MB
PRAGMA temp_store = MEMORY;
```

---

## 日志配置

### Python 日志配置

```python
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: '%(asctime)s %(name)s %(levelname)s %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: /var/log/shield-tunneling/app.log
    maxBytes: 10485760  # 10MB
    backupCount: 10

loggers:
  edge:
    level: INFO
    handlers: [console, file]
    propagate: false

  cloud:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: WARNING
  handlers: [console]
```

---

## 性能调优

### 推荐配置

| 组件 | 配置项 | 开发环境 | 生产环境 |
|------|--------|----------|----------|
| Cloud API | Workers | 1 | 4 |
| Cloud API | Max Connections | 10 | 100 |
| Edge API | Workers | 1 | 2 |
| MQTT | Max Inflight | 20 | 100 |
| PostgreSQL | shared_buffers | 128MB | 512MB |
| SQLite | cache_size | 16MB | 64MB |
