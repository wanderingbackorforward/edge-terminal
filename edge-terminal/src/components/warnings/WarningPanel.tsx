/**
 * T174: Warning Panel Component
 * Displays list of warnings with filtering and actions
 */
import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Select,
  Input,
  Tooltip,
  Badge,
  Typography,
  Empty,
} from 'antd';
import {
  ExclamationCircleOutlined,
  WarningOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  ReloadOutlined,
  FilterOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { WarningEvent, WarningLevel, WarningStatus, WarningType } from '../../types/api';

const { Text } = Typography;

// ============================================================================
// Types
// ============================================================================

export interface WarningPanelProps {
  warnings: WarningEvent[];
  loading?: boolean;
  onWarningClick?: (warning: WarningEvent) => void;
  onAcknowledge?: (warningId: string) => void;
  onResolve?: (warningId: string) => void;
  onRefresh?: () => void;
  showFilters?: boolean;
  showActions?: boolean;
  maxHeight?: number | string;
  compact?: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const LEVEL_CONFIG: Record<WarningLevel, { color: string; icon: React.ReactNode; label: string }> = {
  ATTENTION: {
    color: 'gold',
    icon: <ExclamationCircleOutlined />,
    label: '注意',
  },
  WARNING: {
    color: 'orange',
    icon: <WarningOutlined />,
    label: '警告',
  },
  ALARM: {
    color: 'red',
    icon: <AlertOutlined />,
    label: '报警',
  },
};

const STATUS_CONFIG: Record<WarningStatus, { color: string; label: string }> = {
  active: { color: 'error', label: '活跃' },
  acknowledged: { color: 'warning', label: '已确认' },
  resolved: { color: 'success', label: '已解决' },
};

const TYPE_LABELS: Record<WarningType, string> = {
  threshold: '阈值告警',
  rate: '变化率告警',
  predictive: '预测性告警',
  combined: '组合告警',
};
const FALLBACK_LEVEL = { color: 'default', icon: <AlertOutlined />, label: '告警' };

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
const fallbackIndicator = 'indicator';

// ============================================================================
// Helper Functions
// ============================================================================

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  return `${days}天前`;
}

// ============================================================================
// Component
// ============================================================================

const WarningPanel: React.FC<WarningPanelProps> = ({
  warnings,
  loading = false,
  onWarningClick,
  onAcknowledge,
  onResolve,
  onRefresh,
  showFilters = true,
  showActions = true,
  maxHeight = 500,
  compact = false,
}) => {
  // Filter states
  const [levelFilter, setLevelFilter] = useState<WarningLevel | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<WarningStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<WarningType | 'all'>('all');
  const [searchText, setSearchText] = useState('');

  // Filter warnings
  const filteredWarnings = useMemo(() => {
    return warnings.filter((warning) => {
      if (levelFilter !== 'all' && warning.warning_level !== levelFilter) return false;
      if (statusFilter !== 'all' && warning.status !== statusFilter) return false;
      if (typeFilter !== 'all' && warning.warning_type !== typeFilter) return false;
      if (searchText) {
        const search = searchText.toLowerCase();
        const indicatorLabel = INDICATOR_LABELS[warning.indicator] || warning.indicator;
        return (
          warning.warning_id.toLowerCase().includes(search) ||
          indicatorLabel.toLowerCase().includes(search) ||
          warning.message.toLowerCase().includes(search)
        );
      }
      return true;
    });
  }, [warnings, levelFilter, statusFilter, typeFilter, searchText]);

  // Stats
  const stats = useMemo(() => {
    const active = warnings.filter((w) => w.status === 'active').length;
    const alarms = warnings.filter((w) => w.warning_level === 'ALARM' && w.status === 'active').length;
    const warningCount = warnings.filter((w) => w.warning_level === 'WARNING' && w.status === 'active').length;
    const attentionCount = warnings.filter((w) => w.warning_level === 'ATTENTION' && w.status === 'active').length;
    return { active, alarms, warningCount, attentionCount };
  }, [warnings]);

  // Handle row click
  const handleRowClick = useCallback(
    (record: WarningEvent) => {
      onWarningClick?.(record);
    },
    [onWarningClick]
  );

  // Table columns
  const columns: ColumnsType<WarningEvent> = useMemo(() => {
    const cols: ColumnsType<WarningEvent> = [
      {
        title: '级别',
        dataIndex: 'warning_level',
        key: 'level',
        width: compact ? 60 : 80,
        render: (level: WarningLevel) => {
          const normalized = (level || '').toUpperCase() as WarningLevel;
          const config = LEVEL_CONFIG[normalized] || FALLBACK_LEVEL;
          return (
            <Tooltip title={config.label}>
              <Tag color={config.color} icon={config.icon}>
                {!compact && config.label}
              </Tag>
            </Tooltip>
          );
        },
        sorter: (a, b) => {
          const order = { ALARM: 3, WARNING: 2, ATTENTION: 1 };
          return order[b.warning_level] - order[a.warning_level];
        },
      },
      {
        title: '指标',
        dataIndex: 'indicator',
        key: 'indicator',
        width: compact ? 100 : 120,
        ellipsis: true,
        render: (indicator: string) => (
          <Text ellipsis={{ tooltip: true }}>
            {INDICATOR_LABELS[indicator] || indicator || fallbackIndicator}
          </Text>
        ),
      },
      {
        title: '环号',
        dataIndex: 'ring_number',
        key: 'ring',
        width: 70,
        sorter: (a, b) => (a.ring_number || 0) - (b.ring_number || 0),
      },
      {
        title: '消息',
        dataIndex: 'message',
        key: 'message',
        ellipsis: true,
        render: (message: string) => (
          <Text ellipsis={{ tooltip: message }}>
            {message}
          </Text>
        ),
      },
      {
        title: '时间',
        dataIndex: 'timestamp',
        key: 'timestamp',
        width: compact ? 80 : 140,
        render: (timestamp: number) => (
          <Tooltip title={formatTimestamp(timestamp)}>
            <Text type="secondary">
              {compact ? formatRelativeTime(timestamp) : formatTimestamp(timestamp)}
            </Text>
          </Tooltip>
        ),
        sorter: (a, b) => b.timestamp - a.timestamp,
        defaultSortOrder: 'ascend',
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 80,
        render: (status: WarningStatus) => {
          const config = STATUS_CONFIG[status];
          return <Badge status={config.color as any} text={config.label} />;
        },
      },
    ];

    if (showActions) {
      cols.push({
        title: '操作',
        key: 'actions',
        width: 120,
        render: (_, record) => (
          <Space size="small">
            {record.status === 'active' && onAcknowledge && (
              <Button
                type="link"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onAcknowledge(record.warning_id);
                }}
              >
                确认
              </Button>
            )}
            {record.status !== 'resolved' && onResolve && (
              <Button
                type="link"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onResolve(record.warning_id);
                }}
              >
                解决
              </Button>
            )}
          </Space>
        ),
      });
    }

    return cols;
  }, [compact, showActions, onAcknowledge, onResolve]);

  // Reset filters
  const handleResetFilters = useCallback(() => {
    setLevelFilter('all');
    setStatusFilter('all');
    setTypeFilter('all');
    setSearchText('');
  }, []);

  return (
    <Card
      title={
        <Space>
          <AlertOutlined />
          <span>告警列表</span>
          <Badge count={stats.active} overflowCount={99} />
        </Space>
      }
      extra={
        <Space size="small">
          {stats.alarms > 0 && (
            <Tag color="red">
              {stats.alarms} 报警
            </Tag>
          )}
          {stats.warningCount > 0 && (
            <Tag color="orange">
              {stats.warningCount} 警告
            </Tag>
          )}
          {onRefresh && (
            <Button
              type="text"
              icon={<ReloadOutlined />}
              onClick={onRefresh}
              loading={loading}
            />
          )}
        </Space>
      }
      bodyStyle={{ padding: compact ? 8 : 16 }}
    >
      {showFilters && (
        <Space wrap style={{ marginBottom: 16, width: '100%' }}>
          <Input
            placeholder="搜索..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 160 }}
            allowClear
          />
          <Select
            value={levelFilter}
            onChange={setLevelFilter}
            style={{ width: 100 }}
            options={[
              { label: '全部级别', value: 'all' },
              { label: '报警', value: 'ALARM' },
              { label: '警告', value: 'WARNING' },
              { label: '注意', value: 'ATTENTION' },
            ]}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 100 }}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '活跃', value: 'active' },
              { label: '已确认', value: 'acknowledged' },
              { label: '已解决', value: 'resolved' },
            ]}
          />
          <Select
            value={typeFilter}
            onChange={setTypeFilter}
            style={{ width: 120 }}
            options={[
              { label: '全部类型', value: 'all' },
              { label: '阈值告警', value: 'threshold' },
              { label: '变化率', value: 'rate' },
              { label: '预测性', value: 'predictive' },
              { label: '组合', value: 'combined' },
            ]}
          />
          {(levelFilter !== 'all' || statusFilter !== 'all' || typeFilter !== 'all' || searchText) && (
            <Button
              type="text"
              icon={<FilterOutlined />}
              onClick={handleResetFilters}
            >
              重置
            </Button>
          )}
        </Space>
      )}

      <Table
        dataSource={filteredWarnings}
        columns={columns}
        rowKey="warning_id"
        size={compact ? 'small' : 'middle'}
        loading={loading}
        pagination={{
          pageSize: compact ? 5 : 10,
          showSizeChanger: !compact,
          showQuickJumper: !compact,
          showTotal: (total) => `共 ${total} 条`,
        }}
        scroll={{ y: maxHeight }}
        onRow={(record) => ({
          onClick: () => handleRowClick(record),
          style: { cursor: onWarningClick ? 'pointer' : 'default' },
        })}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无告警"
            />
          ),
        }}
      />
    </Card>
  );
};

export default WarningPanel;
