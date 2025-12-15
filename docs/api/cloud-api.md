# Shield Tunneling Cloud API 文档

## 概述

Cloud API 提供边缘设备数据同步、工单管理、责任矩阵配置和通知渠道管理功能。

**Base URL**: `http://localhost:8001`
**API Version**: v1

## 认证

当前版本不需要认证。生产环境应配置 API Key 或 OAuth2。

---

## 健康检查

### GET /health

检查服务健康状态。

**响应**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "database_connected": true
}
```

---

## 数据同步 API

### POST /api/v1/sync/ring-summaries

同步环号摘要数据到云端。

**请求体**
```json
{
  "project_id": 1,
  "edge_device_id": "edge-001",
  "ring_summaries": [
    {
      "ring_number": 100,
      "start_time": 1700000000,
      "end_time": 1700002700,
      "mean_thrust": 12000,
      "max_thrust": 15000,
      "std_thrust": 800,
      "mean_torque": 900,
      "mean_chamber_pressure": 250,
      "mean_advance_rate": 30,
      "geological_zone": "soft_clay"
    }
  ]
}
```

**响应**
```json
{
  "success": true,
  "synced_count": 1,
  "sync_id": "sync-20240115-001",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### POST /api/v1/sync/predictions

同步预测结果到云端。

**请求体**
```json
{
  "project_id": 1,
  "predictions": [
    {
      "ring_number": 100,
      "predicted_settlement": 8.5,
      "confidence_lower": 6.8,
      "confidence_upper": 10.2,
      "prediction_confidence": 0.92,
      "model_name": "settlement_lgb_v1",
      "model_version": "1.0.0"
    }
  ]
}
```

### POST /api/v1/sync/warnings

同步告警事件到云端。

**请求体**
```json
{
  "project_id": 1,
  "warnings": [
    {
      "warning_id": "WRN-2024-001",
      "warning_type": "threshold",
      "warning_level": "ALARM",
      "ring_number": 100,
      "indicator_type": "settlement",
      "threshold": 40.0,
      "actual_value": 45.5,
      "timestamp": 1705312200
    }
  ]
}
```

---

## 工单管理 API

### GET /api/v1/work-orders

获取工单列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | int | 必填，项目ID |
| status | string | 状态筛选: pending, assigned, in_progress, completed, cancelled |
| priority | string | 优先级筛选: critical, high, medium, low |
| assigned_to | string | 负责人筛选 |
| limit | int | 每页数量，默认50 |
| offset | int | 偏移量 |

**响应**
```json
{
  "work_orders": [
    {
      "id": 1,
      "work_order_id": "WO-20240115-001",
      "title": "沉降超限处理",
      "category": "settlement",
      "priority": "critical",
      "status": "pending",
      "ring_number": 100,
      "warning_id": "WRN-2024-001",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### GET /api/v1/work-orders/{work_order_id}

获取工单详情。

### POST /api/v1/work-orders

创建工单。

**请求体**
```json
{
  "project_id": 1,
  "title": "沉降超限处理",
  "description": "环号100沉降值45.5mm超过阈值40mm",
  "category": "settlement",
  "priority": "critical",
  "warning_id": "WRN-2024-001",
  "ring_number": 100,
  "verification_required": true,
  "verification_ring_count": 5
}
```

### PUT /api/v1/work-orders/{work_order_id}

更新工单。

### PUT /api/v1/work-orders/{work_order_id}/assign

分配工单。

**请求体**
```json
{
  "assigned_to": "张三",
  "assigned_by": "系统管理员"
}
```

### PUT /api/v1/work-orders/{work_order_id}/complete

完成工单。

**请求体**
```json
{
  "completed_by": "张三",
  "completion_notes": "已调整推进参数，沉降恢复正常"
}
```

### PUT /api/v1/work-orders/{work_order_id}/verify

验证工单。

**请求体**
```json
{
  "verified_by": "李四",
  "result": "success",
  "notes": "连续5环沉降均在阈值内"
}
```

### GET /api/v1/work-orders/stats

获取工单统计。

**响应**
```json
{
  "total": 100,
  "pending": 10,
  "assigned": 15,
  "in_progress": 20,
  "completed": 50,
  "cancelled": 5
}
```

---

## 责任矩阵 API

### GET /api/v1/responsibility/roles

获取所有角色。

**响应**
```json
[
  {
    "id": 1,
    "role_code": "OPERATOR",
    "role_name": "操作员",
    "description": "Shield machine operator",
    "priority_level": 1
  },
  {
    "id": 2,
    "role_code": "SHIFT_LEAD",
    "role_name": "班组长",
    "priority_level": 2
  }
]
```

### POST /api/v1/responsibility/roles

创建角色。

### GET /api/v1/responsibility/personnel

获取人员列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | int | 必填，项目ID |
| role_id | int | 角色筛选 |
| is_active | bool | 状态筛选 |

### POST /api/v1/responsibility/personnel

创建人员记录。

**请求体**
```json
{
  "project_id": 1,
  "employee_id": "EMP001",
  "name": "张三",
  "email": "zhang@example.com",
  "phone": "13800138001",
  "role_id": 3,
  "department": "工程部",
  "shift_schedule": "day"
}
```

### GET /api/v1/responsibility/matrix

获取责任矩阵。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | int | 必填，项目ID |
| category | string | 问题类别筛选 |

**响应**
```json
{
  "matrix": [
    {
      "id": 1,
      "category": "settlement",
      "priority": "critical",
      "warning_level": "ALARM",
      "primary_role_id": 4,
      "secondary_role_id": 5,
      "auto_assign": true,
      "escalation_hours": 4.0
    }
  ],
  "total": 1
}
```

### POST /api/v1/responsibility/matrix

创建责任矩阵条目。

### GET /api/v1/responsibility/lookup

查询负责人。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | int | 必填 |
| category | string | 必填，问题类别 |
| priority | string | 优先级 |
| warning_level | string | 告警级别 |

### POST /api/v1/responsibility/auto-assign/{work_order_id}

自动分配工单。

---

## 通知渠道 API

### GET /api/v1/notifications/channels

获取通知渠道列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | int | 必填 |
| channel_type | string | 类型筛选: email, sms, webhook |
| is_enabled | bool | 状态筛选 |

### POST /api/v1/notifications/channels

创建通知渠道。

**请求体**
```json
{
  "project_id": 1,
  "channel_type": "email",
  "channel_name": "主邮箱通知",
  "config": {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_user": "alerts@example.com",
    "smtp_password": "xxx",
    "from_address": "alerts@example.com",
    "use_tls": true
  },
  "is_enabled": true
}
```

### POST /api/v1/notifications/channels/{channel_id}/test

测试通知渠道连接。

### GET /api/v1/notifications/subscriptions

获取订阅列表。

### POST /api/v1/notifications/subscriptions

创建订阅。

**请求体**
```json
{
  "project_id": 1,
  "channel_id": 1,
  "personnel_id": 1,
  "recipient_address": "zhang@example.com",
  "warning_levels": ["ALARM", "WARNING"],
  "categories": ["settlement", "chamber_pressure"],
  "event_types": ["warning", "work_order"],
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "06:00",
  "min_interval_minutes": 5
}
```

### GET /api/v1/notifications/logs

获取通知日志。

### POST /api/v1/notifications/send

发送测试通知。

**请求体**
```json
{
  "channel_id": 1,
  "recipient": "test@example.com",
  "subject": "测试通知",
  "message": "这是一条测试消息",
  "event_type": "manual"
}
```

---

## 错误响应

所有 API 错误返回统一格式：

```json
{
  "detail": "错误描述",
  "error": "错误详情"
}
```

**HTTP 状态码**
| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |
