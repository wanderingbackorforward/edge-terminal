/**
 * T175: Warning Detail Component
 * Displays detailed view of a single warning event
 */
import React, { useMemo } from 'react';
import {
  Drawer,
  Descriptions,
  Tag,
  Button,
  Space,
  Timeline,
  Divider,
  Typography,
  Statistic,
  Row,
  Col,
  Card,
  Empty,
} from 'antd';
import {
  ExclamationCircleOutlined,
  WarningOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import type { WarningEvent, WarningLevel, WarningStatus } from '../../types/api';

const { Text, Title, Paragraph } = Typography;

// ============================================================================
// Types
// ============================================================================

export interface WarningDetailProps {
  warning: WarningEvent | null;
  open: boolean;
  onClose: () => void;
  onAcknowledge?: (warningId: string, notes?: string) => void;
  onResolve?: (warningId: string, resolution?: string) => void;
  onCreateWorkOrder?: (warning: WarningEvent) => void;
}

// ============================================================================
// Constants
// ============================================================================

const LEVEL_CONFIG: Record<WarningLevel, { color: string; icon: React.ReactNode; label: string; bg: string }> = {
  ATTENTION: {
    color: 'gold',
    icon: <ExclamationCircleOutlined />,
    label: '注意',
    bg: 'rgba(250, 173, 20, 0.1)',
  },
  WARNING: {
    color: 'orange',
    icon: <WarningOutlined />,
    label: '警告',
    bg: 'rgba(250, 140, 22, 0.1)',
  },
  ALARM: {
    color: 'red',
    icon: <AlertOutlined />,
    label: '报警',
    bg: 'rgba(245, 34, 45, 0.1)',
  },
};

const STATUS_CONFIG: Record<WarningStatus, { color: string; label: string }> = {
  active: { color: 'error', label: '活跃' },
  acknowledged: { color: 'warning', label: '已确认' },
  resolved: { color: 'success', label: '已解决' },
};

const TYPE_LABELS: Record<string, string> = {
  threshold: '阈值告警',
  rate: '变化率告警',
  predictive: '预测性告警',
  combined: '组合告警',
};

const INDICATOR_LABELS: Record<string, string> = {
  thrust_mean: '推力均值',
  thrust_variance: '推力方差',
  earth_pressure: '土压力',
  grouting_pressure: '注浆压力',
  advance_rate: '推进速度',
  cutter_torque: '刀盘扭矩',
  settlement: '沉降',
  horizontal_deviation: '水平偏差',
  vertical_deviation: '垂直偏差',
  deviation_combined: '组合偏差',
};

// ============================================================================
// Helper Functions
// ============================================================================

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(startTs: number, endTs?: number): string {
  const end = endTs || Date.now();
  const diff = end - startTs;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 60) return `${minutes} 分钟`;
  if (hours < 24) return `${hours} 小时 ${minutes % 60} 分钟`;
  return `${days} 天 ${hours % 24} 小时`;
}

// ============================================================================
// Component
// ============================================================================

const WarningDetail: React.FC<WarningDetailProps> = ({
  warning,
  open,
  onClose,
  onAcknowledge,
  onResolve,
  onCreateWorkOrder,
}) => {
  // Build timeline items
  const timelineItems = useMemo(() => {
    if (!warning) return [];

    const items: { color: string; dot?: React.ReactNode; children: React.ReactNode }[] = [
      {
        color: 'red',
        dot: <AlertOutlined />,
        children: (
          <>
            <Text strong>告警触发</Text>
            <br />
            <Text type="secondary">{formatTimestamp(warning.timestamp)}</Text>
          </>
        ),
      },
    ];

    if (warning.acknowledged_at) {
      items.push({
        color: 'orange',
        dot: <CheckCircleOutlined />,
        children: (
          <>
            <Text strong>已确认</Text>
            {warning.acknowledged_by && (
              <>
                <br />
                <Text type="secondary">
                  <UserOutlined /> {warning.acknowledged_by}
                </Text>
              </>
            )}
            <br />
            <Text type="secondary">{formatTimestamp(warning.acknowledged_at)}</Text>
          </>
        ),
      });
    }

    if (warning.resolved_at) {
      items.push({
        color: 'green',
        dot: <CheckCircleOutlined />,
        children: (
          <>
            <Text strong>已解决</Text>
            {warning.resolved_by && (
              <>
                <br />
                <Text type="secondary">
                  <UserOutlined /> {warning.resolved_by}
                </Text>
              </>
            )}
            <br />
            <Text type="secondary">{formatTimestamp(warning.resolved_at)}</Text>
          </>
        ),
      });
    }

    return items;
  }, [warning]);

  if (!warning) {
    return (
      <Drawer
        title="告警详情"
        open={open}
        onClose={onClose}
        width={480}
      >
        <Empty description="未选择告警" />
      </Drawer>
    );
  }

  const levelConfig = LEVEL_CONFIG[warning.warning_level];
  const statusConfig = STATUS_CONFIG[warning.status];

  return (
    <Drawer
      title={
        <Space>
          {levelConfig.icon}
          <span>告警详情</span>
          <Tag color={levelConfig.color}>{levelConfig.label}</Tag>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={520}
      extra={
        <Space>
          {warning.status === 'active' && onAcknowledge && (
            <Button onClick={() => onAcknowledge(warning.warning_id)}>
              确认
            </Button>
          )}
          {warning.status !== 'resolved' && onResolve && (
            <Button type="primary" onClick={() => onResolve(warning.warning_id)}>
              解决
            </Button>
          )}
        </Space>
      }
    >
      {/* Header Card */}
      <Card
        style={{ marginBottom: 16, background: levelConfig.bg }}
        bodyStyle={{ padding: 16 }}
      >
        <Title level={5} style={{ margin: 0 }}>
          {INDICATOR_LABELS[warning.indicator] || warning.indicator}
        </Title>
        <Paragraph style={{ margin: '8px 0 0' }}>
          {warning.message}
        </Paragraph>
      </Card>

      {/* Stats Row */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title="环号"
            value={warning.ring_number || '-'}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="当前值"
            value={warning.current_value?.toFixed(2) || '-'}
            suffix={warning.unit}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="阈值"
            value={warning.threshold_value?.toFixed(2) || '-'}
            suffix={warning.unit}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>
      </Row>

      {/* Duration */}
      {warning.status !== 'resolved' && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <ClockCircleOutlined />
            <Text>持续时间: </Text>
            <Text strong>{formatDuration(warning.timestamp)}</Text>
          </Space>
        </Card>
      )}

      <Divider orientation="left">基本信息</Divider>

      <Descriptions column={2} size="small">
        <Descriptions.Item label="告警ID" span={2}>
          <Text copyable code style={{ fontSize: 12 }}>
            {warning.warning_id}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="类型">
          {TYPE_LABELS[warning.warning_type] || warning.warning_type}
        </Descriptions.Item>
        <Descriptions.Item label="级别">
          <Tag color={levelConfig.color}>{levelConfig.label}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={statusConfig.color}>{statusConfig.label}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="指标">
          {INDICATOR_LABELS[warning.indicator] || warning.indicator}
        </Descriptions.Item>
        <Descriptions.Item label="触发时间" span={2}>
          {formatTimestamp(warning.timestamp)}
        </Descriptions.Item>
      </Descriptions>

      {/* Threshold Details */}
      {(warning.current_value !== undefined || warning.threshold_value !== undefined) && (
        <>
          <Divider orientation="left">阈值详情</Divider>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="当前值">
              <Text strong style={{ color: levelConfig.color }}>
                {warning.current_value?.toFixed(3)} {warning.unit}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="阈值">
              {warning.threshold_value?.toFixed(3)} {warning.unit}
            </Descriptions.Item>
            {warning.deviation !== undefined && (
              <Descriptions.Item label="偏差">
                {warning.deviation > 0 ? '+' : ''}{warning.deviation.toFixed(3)} {warning.unit}
              </Descriptions.Item>
            )}
            {warning.deviation_percent !== undefined && (
              <Descriptions.Item label="偏差率">
                {warning.deviation_percent > 0 ? '+' : ''}{warning.deviation_percent.toFixed(1)}%
              </Descriptions.Item>
            )}
          </Descriptions>
        </>
      )}

      {/* Timeline */}
      <Divider orientation="left">处理记录</Divider>
      <Timeline items={timelineItems} />

      {/* Notes */}
      {warning.notes && (
        <>
          <Divider orientation="left">备注</Divider>
          <Card size="small">
            <Paragraph style={{ margin: 0 }}>
              {warning.notes}
            </Paragraph>
          </Card>
        </>
      )}

      {/* Resolution */}
      {warning.resolution && (
        <>
          <Divider orientation="left">解决方案</Divider>
          <Card size="small">
            <Paragraph style={{ margin: 0 }}>
              {warning.resolution}
            </Paragraph>
          </Card>
        </>
      )}

      {/* Actions */}
      {onCreateWorkOrder && warning.status !== 'resolved' && (
        <>
          <Divider />
          <Button
            type="dashed"
            block
            icon={<FileTextOutlined />}
            onClick={() => onCreateWorkOrder(warning)}
          >
            创建工单
          </Button>
        </>
      )}
    </Drawer>
  );
};

export default WarningDetail;
