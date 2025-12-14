/**
 * Warnings Page (T179)
 * Full warning history with filters and management
 */
import React, { useState, useEffect, useMemo } from 'react';
import {
  Card,
  Table,
  Space,
  Tag,
  Button,
  Input,
  Select,
  DatePicker,
  Row,
  Col,
  Statistic,
  Typography,
  Tooltip,
  Modal,
  message,
  Drawer,
  Timeline,
  Descriptions,
  Badge,
} from 'antd';
import {
  SearchOutlined,
  FilterOutlined,
  ExportOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  BellOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import type { FilterValue, SorterResult } from 'antd/es/table/interface';
import { useRealTimeData } from '../hooks';
import { warningApi } from '../services/api';
import type { WarningEvent, WarningLevel, WarningStatus, AcknowledgeWarningRequest, ResolveWarningRequest } from '../types/api';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

interface TableParams {
  pagination?: TablePaginationConfig;
  sortField?: string;
  sortOrder?: string;
  filters?: Record<string, FilterValue | null>;
}

export const Warnings: React.FC = () => {
  const { activeWarnings: realtimeWarnings, refreshWarnings } = useRealTimeData();
  const [loading, setLoading] = useState(false);
  const [warnings, setWarnings] = useState<WarningEvent[]>([]);
  const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [tableParams, setTableParams] = useState<TableParams>({
    pagination: {
      current: 1,
      pageSize: 20,
    },
  });

  // Filters
  const [searchText, setSearchText] = useState('');
  const [levelFilter, setLevelFilter] = useState<WarningLevel | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<WarningStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [dateRange, setDateRange] = useState<[any, any] | null>(null);

  // Use real-time warnings (activeWarnings from hook)
  const normalizeWarning = (w: any): WarningEvent => {
    const levelMap: Record<string, WarningLevel> = {
      high: 'Alarm',
      alarm: 'Alarm',
      medium: 'Warning',
      warning: 'Warning',
      low: 'Attention',
      attention: 'Attention',
    };
    const levelKey = (w.warning_level || w.warningLevel || '').toString().toLowerCase();
    const warning_level: WarningLevel = levelMap[levelKey] || 'Warning';
    const indicator_type = w.indicator_type || w.indicator_name || w.indicator || 'unknown';
    const tsRaw = Number(w.timestamp || w.created_at || Date.now() / 1000);
    const timestamp = tsRaw > 1e12 ? tsRaw / 1000 : tsRaw;

    return {
      warning_id: Number(w.warning_id) || w.warning_id || 0,
      ring_number: Number(w.ring_number) || 0,
      timestamp,
      indicator_type,
      indicator_value: w.indicator_value ?? w.indicatorValue ?? null,
      threshold: w.threshold_value ?? w.threshold ?? null,
      warning_level,
      triggering_condition: (w.warning_type as WarningType) || 'threshold',
      prediction_id: w.prediction_id ?? null,
      status: (w.status as WarningStatus) || 'active',
      acknowledged_by: w.acknowledged_by || null,
      acknowledged_at: w.acknowledged_at || null,
      resolved_by: w.resolved_by || null,
      resolved_at: w.resolved_at || null,
      action_taken: w.resolution_notes || w.action_taken || null,
      created_at: w.created_at || timestamp,
      synced_to_cloud: Boolean(w.synced_to_cloud),
    };
  };

  useEffect(() => {
    if (realtimeWarnings.length > 0) {
      setWarnings(realtimeWarnings.map(normalizeWarning));
    }
  }, [realtimeWarnings]);

  // Fetch all warnings initially
  useEffect(() => {
    const fetchWarnings = async () => {
      setLoading(true);
      try {
        const response = await warningApi.getWarnings({ page_size: 100 });
        const normalized = (response.warnings || []).map(normalizeWarning);
        setWarnings(normalized);
      } catch (err) {
        console.error('获取告警失败:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchWarnings();
  }, []);

  // Statistics
  const stats = useMemo(() => {
    const active = warnings.filter(w => w.status === 'active').length;
    const acknowledged = warnings.filter(w => w.status === 'acknowledged').length;
    const resolved = warnings.filter(w => w.status === 'resolved').length;
    const alarms = warnings.filter(w => w.warning_level === 'Alarm' && w.status === 'active').length;
    return { active, acknowledged, resolved, alarms };
  }, [warnings]);

  // Filtered data
  const filteredData = useMemo(() => {
    return warnings.filter(w => {
      // Search filter
      if (searchText) {
        const search = searchText.toLowerCase();
      const matchesSearch =
          (w.indicator_type || '').toLowerCase().includes(search) ||
          w.ring_number.toString().includes(search) ||
          w.warning_level.toLowerCase().includes(search);
        if (!matchesSearch) return false;
      }

      // Level filter
      if (levelFilter !== 'all' && w.warning_level !== levelFilter) return false;

      // Status filter
      if (statusFilter !== 'all' && w.status !== statusFilter) return false;

      // Type filter
      if (typeFilter !== 'all' && w.indicator_type !== typeFilter) return false;

      // Date range filter
      if (dateRange && dateRange[0] && dateRange[1]) {
        const warningDate = new Date(w.timestamp * 1000);
        const start = dateRange[0].toDate();
        const end = dateRange[1].toDate();
        if (warningDate < start || warningDate > end) return false;
      }

      return true;
    });
  }, [warnings, searchText, levelFilter, statusFilter, typeFilter, dateRange]);

  // Get unique indicator types for filter
  const indicatorTypes = useMemo(() => {
    const types = new Set(warnings.map(w => w.indicator_type || 'unknown'));
    return Array.from(types);
  }, [warnings]);

  const handleAcknowledge = async (warning: WarningEvent) => {
    try {
      const request: AcknowledgeWarningRequest = { acknowledged_by: 'Admin' };
      await warningApi.acknowledgeWarning(String(warning.warning_id), request);
      message.success(`告警 #${warning.warning_id} 已确认`);
      refreshWarnings?.();
    } catch (error) {
      message.error('Failed to acknowledge warning');
    }
  };

  const handleResolve = async (warning: WarningEvent) => {
    Modal.confirm({
      title: '解决告警',
      content: '确认将该告警标记为已解决？',
      onOk: async () => {
        try {
          const request: ResolveWarningRequest = {
            resolved_by: 'Admin',
            action_taken: '在控制台标记解决',
          };
          await warningApi.resolveWarning(String(warning.warning_id), request);
          message.success(`告警 #${warning.warning_id} 已解决`);
          refreshWarnings?.();
        } catch (error) {
          message.error('解决失败');
        }
      },
    });
  };

  const handleViewDetail = (warning: WarningEvent) => {
    setSelectedWarning(warning);
    setDetailDrawerOpen(true);
  };

  const getLevelTag = (level: WarningLevel) => {
    const config: Record<WarningLevel, { color: string; icon: React.ReactNode }> = {
      Alarm: { color: 'red', icon: <CloseCircleOutlined /> },
      Warning: { color: 'orange', icon: <WarningOutlined /> },
      Attention: { color: 'blue', icon: <ExclamationCircleOutlined /> },
    };
    const safeLevel: WarningLevel = config[level] ? level : 'Warning';
    const { color, icon } = config[safeLevel];
    return (
      <Tag color={color} icon={icon}>
        {safeLevel}
      </Tag>
    );
  };

  const getStatusBadge = (status: WarningStatus) => {
    const config: Record<WarningStatus, { status: 'error' | 'warning' | 'success'; text: string }> = {
      active: { status: 'error', text: '活跃' },
      acknowledged: { status: 'warning', text: '已确认' },
      resolved: { status: 'success', text: '已解决' },
    };
    const { status: badgeStatus, text } = config[status];
    return <Badge status={badgeStatus} text={text} />;
  };

  const columns: ColumnsType<WarningEvent> = [
    {
      title: 'ID',
      dataIndex: 'warning_id',
      key: 'warning_id',
      width: 80,
      sorter: (a, b) => String(a.warning_id).localeCompare(String(b.warning_id)),
    },
    {
      title: 'Level',
      dataIndex: 'warning_level',
      key: 'warning_level',
      width: 120,
      render: (level: WarningLevel) => getLevelTag(level),
      filters: [
        { text: 'Alarm', value: 'Alarm' },
        { text: 'Warning', value: 'Warning' },
        { text: 'Attention', value: 'Attention' },
      ],
      onFilter: (value, record) => record.warning_level === value,
    },
    {
      title: 'Ring',
      dataIndex: 'ring_number',
      key: 'ring_number',
      width: 100,
      sorter: (a, b) => a.ring_number - b.ring_number,
    },
    {
      title: 'Indicator',
      dataIndex: 'indicator_type',
      key: 'indicator_type',
      width: 150,
      render: (type: string) => (
        <Text style={{ textTransform: 'capitalize' }}>
          {type.replace(/_/g, ' ')}
        </Text>
      ),
    },
    {
      title: 'Value',
      dataIndex: 'indicator_value',
      key: 'indicator_value',
      width: 100,
      render: (value: number) => value?.toFixed(2),
    },
    {
      title: 'Threshold',
      dataIndex: 'threshold',
      key: 'threshold',
      width: 100,
      render: (value: number) => value?.toFixed(2),
    },
    {
      title: 'Condition',
      dataIndex: 'triggering_condition',
      key: 'triggering_condition',
      width: 120,
      render: (condition: string) => (
        <Tag>{condition}</Tag>
      ),
    },
    {
      title: 'Time',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      sorter: (a, b) => a.timestamp - b.timestamp,
      defaultSortOrder: 'descend',
      render: (ts: number) => new Date(ts * 1000).toLocaleString(),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (status: WarningStatus) => getStatusBadge(status),
      filters: [
        { text: 'Active', value: 'active' },
        { text: 'Acknowledged', value: 'acknowledged' },
        { text: 'Resolved', value: 'resolved' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="link"
              size="small"
              onClick={() => handleViewDetail(record)}
            >
              Details
            </Button>
          </Tooltip>
          {record.status === 'active' && (
            <Tooltip title="Acknowledge">
              <Button
                type="link"
                size="small"
                onClick={() => handleAcknowledge(record)}
              >
                Ack
              </Button>
            </Tooltip>
          )}
          {record.status !== 'resolved' && (
            <Tooltip title="Resolve">
              <Button
                type="link"
                size="small"
                onClick={() => handleResolve(record)}
              >
                Resolve
              </Button>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  const handleTableChange = (
    pagination: TablePaginationConfig,
    filters: Record<string, FilterValue | null>,
    sorter: SorterResult<WarningEvent> | SorterResult<WarningEvent>[],
  ) => {
    setTableParams({
      pagination,
      filters,
      ...Array.isArray(sorter) ? {} : { sortField: sorter.field as string, sortOrder: sorter.order as string },
    });
  };

  const handleExport = () => {
    // Export to CSV
    const headers = ['ID', 'Level', 'Ring', 'Indicator', 'Value', 'Threshold', 'Condition', 'Time', 'Status'];
    const csvContent = [
      headers.join(','),
      ...filteredData.map(w => [
        w.warning_id,
        w.warning_level,
        w.ring_number,
        w.indicator_type,
        w.indicator_value,
        w.threshold,
        w.triggering_condition,
        new Date(w.timestamp * 1000).toISOString(),
        w.status,
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `warnings-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    message.success('Warnings exported successfully');
  };

  return (
    <div>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2} style={{ margin: 0 }}>
            <BellOutlined style={{ marginRight: 12 }} />
            Warning Management
          </Title>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={refreshWarnings}>
              Refresh
            </Button>
            <Button icon={<ExportOutlined />} onClick={handleExport}>
              Export CSV
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Active Warnings"
              value={stats.active}
              valueStyle={{ color: stats.active > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Active Alarms"
              value={stats.alarms}
              valueStyle={{ color: stats.alarms > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Acknowledged"
              value={stats.acknowledged}
              valueStyle={{ color: '#faad14' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Resolved Today"
              value={stats.resolved}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Input
              placeholder="Search by ring, indicator..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="Level"
              value={levelFilter}
              onChange={setLevelFilter}
            >
              <Select.Option value="all">All Levels</Select.Option>
              <Select.Option value="Alarm">Alarm</Select.Option>
              <Select.Option value="Warning">Warning</Select.Option>
              <Select.Option value="Attention">Attention</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="Status"
              value={statusFilter}
              onChange={setStatusFilter}
            >
              <Select.Option value="all">All Status</Select.Option>
              <Select.Option value="active">Active</Select.Option>
              <Select.Option value="acknowledged">Acknowledged</Select.Option>
              <Select.Option value="resolved">Resolved</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="Indicator Type"
              value={typeFilter}
              onChange={setTypeFilter}
            >
              <Select.Option value="all">All Types</Select.Option>
              {indicatorTypes.map(type => (
                <Select.Option key={type} value={type}>
                  {type.replace(/_/g, ' ')}
                </Select.Option>
              ))}
            </Select>
          </Col>
          <Col span={6}>
            <RangePicker
              style={{ width: '100%' }}
              onChange={(dates) => setDateRange(dates as [any, any])}
            />
          </Col>
        </Row>
      </Card>

      {/* Warnings Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="warning_id"
          loading={loading}
          pagination={tableParams.pagination}
          onChange={handleTableChange}
          scroll={{ x: 1400 }}
          size="middle"
          rowClassName={(record) => {
            if (record.status === 'active' && record.warning_level === 'Alarm') {
              return 'warning-row-alarm';
            }
            return '';
          }}
        />
      </Card>

      {/* Detail Drawer */}
      <Drawer
        title={`Warning #${selectedWarning?.warning_id}`}
        placement="right"
        width={500}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
      >
        {selectedWarning && (
          <div>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Level">
                {getLevelTag(selectedWarning.warning_level)}
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                {getStatusBadge(selectedWarning.status)}
              </Descriptions.Item>
              <Descriptions.Item label="Ring Number">
                {selectedWarning.ring_number}
              </Descriptions.Item>
              <Descriptions.Item label="Indicator">
                {selectedWarning.indicator_type.replace(/_/g, ' ')}
              </Descriptions.Item>
              <Descriptions.Item label="Value">
                {selectedWarning.indicator_value?.toFixed(2)}
              </Descriptions.Item>
              <Descriptions.Item label="Threshold">
                {selectedWarning.threshold?.toFixed(2)}
              </Descriptions.Item>
              <Descriptions.Item label="Condition">
                {selectedWarning.triggering_condition}
              </Descriptions.Item>
              <Descriptions.Item label="Created At">
                {new Date(selectedWarning.timestamp * 1000).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>

            <Title level={5} style={{ marginTop: 24 }}>
              <HistoryOutlined /> Timeline
            </Title>
            <Timeline
              items={[
                {
                  color: 'red',
                  children: (
                    <>
                      <Text strong>Warning Created</Text>
                      <br />
                      <Text type="secondary">
                        {new Date(selectedWarning.timestamp * 1000).toLocaleString()}
                      </Text>
                    </>
                  ),
                },
                ...(selectedWarning.acknowledged_at ? [{
                  color: 'orange',
                  children: (
                    <>
                      <Text strong>Acknowledged</Text>
                      <br />
                      <Text type="secondary">
                        By {selectedWarning.acknowledged_by} at{' '}
                        {new Date(selectedWarning.acknowledged_at * 1000).toLocaleString()}
                      </Text>
                    </>
                  ),
                }] : []),
                ...(selectedWarning.resolved_at ? [{
                  color: 'green',
                  children: (
                    <>
                      <Text strong>Resolved</Text>
                      <br />
                      <Text type="secondary">
                        By {selectedWarning.resolved_by} at{' '}
                        {new Date(selectedWarning.resolved_at * 1000).toLocaleString()}
                      </Text>
                      {selectedWarning.action_taken && (
                        <>
                          <br />
                          <Text>Action: {selectedWarning.action_taken}</Text>
                        </>
                      )}
                    </>
                  ),
                }] : []),
              ]}
            />

            <Space style={{ marginTop: 24, width: '100%' }} direction="vertical">
              {selectedWarning.status === 'active' && (
                <Button
                  type="primary"
                  block
                  onClick={() => handleAcknowledge(selectedWarning)}
                >
                  Acknowledge Warning
                </Button>
              )}
              {selectedWarning.status !== 'resolved' && (
                <Button
                  block
                  onClick={() => handleResolve(selectedWarning)}
                >
                  Mark as Resolved
                </Button>
              )}
            </Space>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default Warnings;
