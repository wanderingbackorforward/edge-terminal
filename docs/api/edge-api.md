# Shield Tunneling Edge API 文档

## 概述

Edge API 运行在边缘设备上，提供实时数据处理、预测推理、告警生成和工单管理功能。

**Base URL**: `http://localhost:8000`
**API Version**: v1

---

## 健康检查

### GET /health

检查边缘服务健康状态。

**响应**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "database_connected": true,
  "model_loaded": true,
  "mqtt_connected": true
}
```

---

## 环号数据 API

### GET /api/v1/rings

获取环号摘要列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| start_ring | int | 起始环号 |
| end_ring | int | 结束环号 |
| limit | int | 每页数量，默认50 |
| offset | int | 偏移量 |

**响应**
```json
{
  "rings": [
    {
      "ring_number": 100,
      "start_time": 1700000000,
      "end_time": 1700002700,
      "mean_thrust": 12000,
      "max_thrust": 15000,
      "std_thrust": 800,
      "mean_torque": 900,
      "max_torque": 1100,
      "mean_chamber_pressure": 250,
      "mean_advance_rate": 30,
      "geological_zone": "soft_clay",
      "data_completeness_flag": "complete"
    }
  ],
  "total": 1
}
```

### GET /api/v1/rings/{ring_number}

获取指定环号详情。

### GET /api/v1/rings/latest

获取最新环号数据。

### GET /api/v1/rings/{ring_number}/timeline

获取环号时间线数据。

**响应**
```json
{
  "ring_number": 100,
  "events": [
    {
      "timestamp": 1700000000,
      "event_type": "ring_start",
      "description": "开始掘进"
    },
    {
      "timestamp": 1700001000,
      "event_type": "warning",
      "warning_id": "WRN-001",
      "warning_level": "WARNING"
    },
    {
      "timestamp": 1700002700,
      "event_type": "ring_complete",
      "description": "环号完成"
    }
  ]
}
```

---

## 预测 API

### GET /api/v1/predictions

获取预测结果列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| start_ring | int | 起始环号 |
| end_ring | int | 结束环号 |
| model_name | string | 模型名称筛选 |
| limit | int | 每页数量 |

**响应**
```json
{
  "predictions": [
    {
      "id": 1,
      "ring_number": 100,
      "predicted_settlement": 8.5,
      "confidence_lower": 6.8,
      "confidence_upper": 10.2,
      "prediction_confidence": 0.92,
      "model_name": "settlement_lgb_v1",
      "model_version": "1.0.0",
      "inference_time_ms": 5.2,
      "quality_flag": "normal",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### GET /api/v1/predictions/{ring_number}

获取指定环号的预测结果。

### POST /api/v1/predictions/run

运行预测推理。

**请求体**
```json
{
  "ring_number": 100,
  "force": false
}
```

**响应**
```json
{
  "success": true,
  "prediction": {
    "ring_number": 100,
    "predicted_settlement": 8.5,
    "confidence_lower": 6.8,
    "confidence_upper": 10.2,
    "prediction_confidence": 0.92,
    "predictive_warnings": []
  }
}
```

### GET /api/v1/predictions/latest

获取最新预测结果。

---

## 告警 API

### GET /api/v1/warnings

获取告警列表。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| warning_level | string | 级别筛选: ALARM, WARNING, ATTENTION |
| warning_type | string | 类型筛选: threshold, rate, predictive, combined |
| is_acknowledged | bool | 是否已确认 |
| is_resolved | bool | 是否已解决 |
| start_ring | int | 起始环号 |
| end_ring | int | 结束环号 |
| limit | int | 每页数量 |

**响应**
```json
{
  "warnings": [
    {
      "id": 1,
      "warning_id": "WRN-2024-001",
      "warning_type": "threshold",
      "warning_level": "ALARM",
      "ring_number": 100,
      "indicator_type": "settlement",
      "threshold": 40.0,
      "actual_value": 45.5,
      "threshold_type": "upper",
      "geological_zone": "soft_clay",
      "timestamp": 1705312200,
      "is_acknowledged": false,
      "is_resolved": false
    }
  ],
  "total": 1,
  "active_count": 1
}
```

### GET /api/v1/warnings/{warning_id}

获取告警详情。

### GET /api/v1/warnings/active

获取活跃告警列表。

### PUT /api/v1/warnings/{warning_id}/acknowledge

确认告警。

**请求体**
```json
{
  "acknowledged_by": "张三",
  "notes": "已查看，正在处理"
}
```

### PUT /api/v1/warnings/{warning_id}/resolve

解决告警。

**请求体**
```json
{
  "resolved_by": "张三",
  "action_taken": "已调整推进参数，沉降恢复正常"
}
```

### GET /api/v1/warnings/stats

获取告警统计。

**响应**
```json
{
  "total": 100,
  "by_level": {
    "ALARM": 5,
    "WARNING": 30,
    "ATTENTION": 65
  },
  "by_type": {
    "threshold": 60,
    "rate": 25,
    "predictive": 10,
    "combined": 5
  },
  "active": 10,
  "acknowledged": 40,
  "resolved": 50
}
```

---

## 工单 API (Edge)

### GET /api/v1/work-orders

获取本地工单列表。

### POST /api/v1/work-orders

创建工单。

### GET /api/v1/work-orders/{work_order_id}

获取工单详情。

### PUT /api/v1/work-orders/{work_order_id}/assign

分配工单。

### PUT /api/v1/work-orders/{work_order_id}/start

开始工单。

### PUT /api/v1/work-orders/{work_order_id}/complete

完成工单。

### PUT /api/v1/work-orders/{work_order_id}/verify

验证工单。

### GET /api/v1/work-orders/pending

获取待处理工单。

---

## 模型管理 API

### GET /api/v1/models

获取已部署模型列表。

**响应**
```json
{
  "models": [
    {
      "model_name": "settlement_lgb_soft_clay",
      "model_version": "1.0.0",
      "model_type": "lightgbm",
      "geological_zone": "soft_clay",
      "deployment_status": "active",
      "deployed_at": "2024-01-15T10:00:00Z",
      "validation_r2": 0.96,
      "validation_rmse": 2.1
    }
  ]
}
```

### GET /api/v1/models/{model_name}

获取模型详情。

### GET /api/v1/models/{model_name}/performance

获取模型性能指标。

**响应**
```json
{
  "model_name": "settlement_lgb_soft_clay",
  "metrics": [
    {
      "evaluation_date": "2024-01-15",
      "num_predictions": 50,
      "r2_score": 0.94,
      "rmse": 2.5,
      "mae": 1.8,
      "confidence_coverage": 0.93,
      "drift_detected": false
    }
  ]
}
```

### POST /api/v1/models/check-update

检查模型更新。

**响应**
```json
{
  "update_available": true,
  "current_version": "1.0.0",
  "latest_version": "2.0.0",
  "auto_deploy": true
}
```

---

## 同步状态 API

### GET /api/v1/sync/status

获取云同步状态。

**响应**
```json
{
  "cloud_connected": true,
  "last_sync_at": "2024-01-15T10:25:00Z",
  "pending_items": {
    "rings": 5,
    "predictions": 3,
    "warnings": 2,
    "work_orders": 1
  },
  "sync_mode": "auto"
}
```

### POST /api/v1/sync/trigger

手动触发同步。

---

## WebSocket 端点

### WS /ws/realtime

实时数据 WebSocket 连接。

**消息类型**
```json
{
  "type": "ring_update",
  "data": { "ring_number": 100, ... }
}

{
  "type": "warning",
  "data": { "warning_id": "WRN-001", ... }
}

{
  "type": "prediction",
  "data": { "ring_number": 100, ... }
}
```

---

## MQTT 主题

Edge 服务发布到以下 MQTT 主题：

| 主题 | 说明 | 保留 |
|------|------|------|
| shield/rings/new | 新环号数据 | 否 |
| shield/rings/latest | 最新环号 | 是 |
| shield/warnings/new | 新告警 | 否 |
| shield/warnings/active | 活跃告警列表 | 是 |
| shield/predictions/new | 新预测结果 | 否 |
| shield/predictions/latest | 最新预测 | 是 |

---

## 错误响应

```json
{
  "detail": "错误描述",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**HTTP 状态码**
| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |
