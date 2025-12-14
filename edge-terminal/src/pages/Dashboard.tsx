/**
 * T177: Main Dashboard Page
 * Central monitoring interface with real-time data visualization
 */
import React, { useState, useCallback, useMemo } from 'react';
import {
  Layout,
  Row,
  Col,
  Card,
  Statistic,
  Badge,
  Space,
  Button,
  Typography,
  Tooltip,
  Spin,
  Alert,
} from 'antd';
import {
  DashboardOutlined,
  AlertOutlined,
  LineChartOutlined,
  SyncOutlined,
  WifiOutlined,
  DisconnectOutlined,
  SettingOutlined,
} from '@ant-design/icons';

// Components
import { TrajectoryPlot, ParameterTimeSeries, WarningHeatmap } from '../components/charts';
import { WarningPanel, WarningDetail, WarningToastProvider, SoundToggle } from '../components/warnings';

// Hooks
import { useRealTimeData } from '../hooks/useRealTimeData';

// Types
import type { WarningEvent } from '../types/api';
import type { TrajectoryData, MultiSeriesData, WarningHeatmapData } from '../types/charts';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

// ============================================================================
// Helper Functions
// ============================================================================

function formatLastUpdate(timestamp: number): string {
  if (!timestamp) return '-';
  const diff = Date.now() - timestamp;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  return new Date(timestamp).toLocaleTimeString('zh-CN');
}

function ringsToTrajectory(rings: any[]): TrajectoryData {
  const actual = rings.map((r) => ({
    ring_number: r.ring_number,
    horizontal: r.horizontal_deviation || 0,
    vertical: r.vertical_deviation || 0,
    timestamp: r.timestamp,
  }));

  // Generate design trajectory (center line)
  const design = rings.map((r) => ({
    ring_number: r.ring_number,
    horizontal: 0,
    vertical: 0,
    timestamp: r.timestamp,
  }));

  // Generate tolerance bands (±30mm example)
  const tolerance = 30;
  const tolerance_upper = rings.map((r) => ({
    ring_number: r.ring_number,
    horizontal: tolerance,
    vertical: tolerance,
    timestamp: r.timestamp,
  }));
  const tolerance_lower = rings.map((r) => ({
    ring_number: r.ring_number,
    horizontal: -tolerance,
    vertical: -tolerance,
    timestamp: r.timestamp,
  }));

  return { actual, design, tolerance_upper, tolerance_lower };
}

function ringsToTimeSeries(rings: any[], key: string, label: string, unit: string): MultiSeriesData {
  return {
    series: [
      {
        label,
        unit,
        data: rings.map((r) => ({
          timestamp: r.timestamp,
          value: r[key] || 0,
          ring_number: r.ring_number,
        })),
      },
    ],
    xAxisType: 'ring',
  };
}

function warningsToHeatmap(warnings: WarningEvent[], ringRange: [number, number]): WarningHeatmapData {
  const indicators = [
    'thrust_mean',
    'earth_pressure',
    'grouting_pressure',
    'advance_rate',
    'horizontal_deviation',
    'vertical_deviation',
    'specific_energy',
    'settlement',
  ];
  const levelMap: Record<string, 'ATTENTION' | 'WARNING' | 'ALARM'> = {
    attention: 'ATTENTION',
    low: 'ATTENTION',
    warning: 'WARNING',
    medium: 'WARNING',
    alarm: 'ALARM',
    high: 'ALARM',
  };

  // Create cells from warnings
  const cellMap = new Map<string, { level: 'ATTENTION' | 'WARNING' | 'ALARM'; count: number }>();

  warnings.forEach((w) => {
    const indicator = (w.indicator as string) || (w as any).indicator_name || '';
    if (!w.ring_number || !indicator || !indicators.includes(indicator)) return;
    const key = `${w.ring_number}-${indicator}`;
    const existing = cellMap.get(key);

    const normalizedLevel = levelMap[(w.warning_level || '').toString().toLowerCase()] || 'WARNING';
    const levelOrder = { ALARM: 3, WARNING: 2, ATTENTION: 1 };
    if (!existing || levelOrder[normalizedLevel] > levelOrder[existing.level]) {
      cellMap.set(key, {
        level: normalizedLevel,
        count: (existing?.count || 0) + 1,
      });
    } else {
      cellMap.set(key, {
        ...existing,
        count: existing.count + 1,
      });
    }
  });

  const cells = Array.from(cellMap.entries()).map(([key, value]) => {
    const [ringStr, indicator] = key.split('-');
    return {
      ring_number: parseInt(ringStr, 10),
      indicator,
      level: value.level,
      count: value.count,
    };
  });

  return {
    cells,
    indicators,
    ringRange,
  };
}

// ============================================================================
// Dashboard Component
// ============================================================================

const Dashboard: React.FC = () => {
  // State
  const [selectedWarning, setSelectedWarning] = useState<WarningEvent | null>(null);
  const [showWarningDetail, setShowWarningDetail] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Real-time data hook
  const {
    latestRing,
    activeWarnings,
    latestPrediction,
    recentRings,
    warningStats,
    connected,
    lastUpdate,
    loading,
    error,
    refresh,
    refreshWarnings,
  } = useRealTimeData({
    enabled: true,
    pollingInterval: 30000,
    ringHistorySize: 100,
    onNewWarning: (warning) => {
      console.log('New warning:', warning.warning_id);
    },
  });

  // Derived data
  const trajectoryData = useMemo(() => {
    if (!recentRings.length) return null;
    return ringsToTrajectory(recentRings);
  }, [recentRings]);

  const thrustData = useMemo(() => {
    if (!recentRings.length) return null;
    return ringsToTimeSeries(recentRings, 'mean_thrust', '推力均值', 'kN');
  }, [recentRings]);

  const heatmapData = useMemo(() => {
    if (!activeWarnings.length || !recentRings.length) return null;
    const ringNumbers = recentRings.map((r) => r.ring_number).filter(Boolean);
    if (!ringNumbers.length) return null;
    const minRing = Math.min(...ringNumbers);
    const maxRing = Math.max(...ringNumbers);
    return warningsToHeatmap(activeWarnings, [minRing, maxRing]);
  }, [activeWarnings, recentRings]);

  // Handlers
  const handleWarningClick = useCallback((warning: WarningEvent) => {
    setSelectedWarning(warning);
    setShowWarningDetail(true);
  }, []);

  const handleWarningClose = useCallback(() => {
    setShowWarningDetail(false);
  }, []);

  const handleAcknowledge = useCallback(
    async (warningId: string) => {
      // TODO: Call API
      console.log('Acknowledge:', warningId);
      refreshWarnings();
    },
    [refreshWarnings]
  );

  const handleResolve = useCallback(
    async (warningId: string) => {
      // TODO: Call API
      console.log('Resolve:', warningId);
      refreshWarnings();
    },
    [refreshWarnings]
  );

  const isLoading = loading.rings || loading.warnings || loading.predictions;

  return (
    <WarningToastProvider
      config={{
        enabled: true,
        playSound: soundEnabled,
        duration: 8,
      }}
      onWarningClick={handleWarningClick}
      onAcknowledge={handleAcknowledge}
    >
      <Layout style={{ minHeight: '100vh', background: '#141414' }}>
        {/* Header */}
        <Header
          style={{
            background: '#1f1f1f',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #303030',
          }}
        >
          <Space>
            <DashboardOutlined style={{ fontSize: 24, color: '#1890ff' }} />
            <Title level={4} style={{ margin: 0, color: '#fff' }}>
              盾构隧道智能监控平台
            </Title>
          </Space>

          <Space size="middle">
            {/* Connection Status */}
            <Tooltip title={connected ? 'MQTT 已连接' : 'MQTT 未连接'}>
              <Badge status={connected ? 'success' : 'error'}>
                {connected ? (
                  <WifiOutlined style={{ fontSize: 18, color: '#52c41a' }} />
                ) : (
                  <DisconnectOutlined style={{ fontSize: 18, color: '#ff4d4f' }} />
                )}
              </Badge>
            </Tooltip>

            {/* Last Update */}
            <Text type="secondary">
              更新: {formatLastUpdate(lastUpdate)}
            </Text>

            {/* Sound Toggle */}
            <SoundToggle enabled={soundEnabled} onChange={setSoundEnabled} />

            {/* Refresh */}
            <Button
              type="text"
              icon={<SyncOutlined spin={isLoading} />}
              onClick={refresh}
            />

            {/* Settings */}
            <Button type="text" icon={<SettingOutlined />} />
          </Space>
        </Header>

        {/* Content */}
        <Content style={{ padding: 24 }}>
          {error && (
            <Alert
              message="数据加载错误"
              description={error}
              type="error"
              showIcon
              closable
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Stats Row */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="当前环号"
                  value={latestRing?.ring_number || '-'}
                  prefix={<LineChartOutlined />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="活跃告警"
                  value={warningStats.active}
                  valueStyle={{
                    color: warningStats.active > 0 ? '#ff4d4f' : '#52c41a',
                  }}
                  prefix={<AlertOutlined />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="推力均值"
                  value={latestRing?.mean_thrust?.toFixed(0) || '-'}
                  suffix="kN"
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="推进速度"
                  value={latestRing?.advance_rate?.toFixed(1) || '-'}
                  suffix="mm/min"
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="水平偏差"
                  value={latestRing?.horizontal_deviation?.toFixed(1) || '-'}
                  suffix="mm"
                  valueStyle={{
                    color:
                      Math.abs(latestRing?.horizontal_deviation || 0) > 20
                        ? '#faad14'
                        : undefined,
                  }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} lg={4}>
              <Card size="small">
                <Statistic
                  title="垂直偏差"
                  value={latestRing?.vertical_deviation?.toFixed(1) || '-'}
                  suffix="mm"
                  valueStyle={{
                    color:
                      Math.abs(latestRing?.vertical_deviation || 0) > 20
                        ? '#faad14'
                        : undefined,
                  }}
                />
              </Card>
            </Col>
          </Row>

          {/* Main Content Grid */}
          <Row gutter={[16, 16]}>
            {/* Left Column: Charts */}
            <Col xs={24} lg={16}>
              <Row gutter={[16, 16]}>
                {/* Trajectory Plot */}
                <Col span={24}>
                  <Card
                    title={
                      <Space>
                        <LineChartOutlined />
                        轨迹偏差
                      </Space>
                    }
                    size="small"
                    bodyStyle={{ padding: 0 }}
                  >
                    <Spin spinning={loading.rings}>
                      <TrajectoryPlot
                        data={trajectoryData}
                        height={300}
                        showDataZoom
                        onRingClick={(ring) => console.log('Ring clicked:', ring)}
                      />
                    </Spin>
                  </Card>
                </Col>

                {/* Parameter Time Series */}
                <Col xs={24} md={12}>
                  <Card
                    title="推力监测"
                    size="small"
                    bodyStyle={{ padding: 0 }}
                  >
                    <Spin spinning={loading.rings}>
                      <ParameterTimeSeries
                        data={thrustData}
                        height={250}
                        yAxisUnit="kN"
                        thresholds={{
                          attention: 15000,
                          warning: 18000,
                          alarm: 20000,
                        }}
                        showArea
                      />
                    </Spin>
                  </Card>
                </Col>

                {/* Warning Heatmap */}
                <Col xs={24} md={12}>
                  <Card
                    title="告警分布"
                    size="small"
                    bodyStyle={{ padding: 0 }}
                  >
                    <Spin spinning={loading.warnings}>
                      <WarningHeatmap
                        data={heatmapData}
                        height={250}
                        showCounts
                        onCellClick={(cell) =>
                          console.log('Heatmap cell clicked:', cell)
                        }
                      />
                    </Spin>
                  </Card>
                </Col>
              </Row>
            </Col>

            {/* Right Column: Warning Panel */}
            <Col xs={24} lg={8}>
              <WarningPanel
                warnings={activeWarnings}
                loading={loading.warnings}
                onWarningClick={handleWarningClick}
                onAcknowledge={handleAcknowledge}
                onResolve={handleResolve}
                onRefresh={refreshWarnings}
                maxHeight={650}
                compact
              />
            </Col>
          </Row>
        </Content>

        {/* Warning Detail Drawer */}
        <WarningDetail
          warning={selectedWarning}
          open={showWarningDetail}
          onClose={handleWarningClose}
          onAcknowledge={handleAcknowledge}
          onResolve={handleResolve}
        />
      </Layout>
    </WarningToastProvider>
  );
};

export default Dashboard;
