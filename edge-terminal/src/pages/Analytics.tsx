/**
 * 数据分析页：轨迹分析 / 沉降趋势 / 参数相关性（示例占位）
 */
import React, { useMemo } from 'react';
import { Row, Col, Card, Space, Button, Empty, Typography } from 'antd';
import { ReloadOutlined, LineChartOutlined, DeploymentUnitOutlined } from '@ant-design/icons';
import { TrajectoryPlot, ParameterTimeSeries } from '../components/charts';
import type { TrajectoryData, MultiSeriesData } from '../types/charts';
import { useRealTimeData } from '../hooks/useRealTimeData';

const { Title, Paragraph, Text } = Typography;

const Analytics: React.FC = () => {
  const { recentRings, refresh, loading } = useRealTimeData({
    enabled: true,
    ringHistorySize: 120,
  });

  const rings = recentRings || [];

  const trajectoryData: TrajectoryData | null = useMemo(() => {
    if (!rings.length) return null;
    return {
      actual: rings.map((r) => ({
        ring_number: r.ring_number,
        horizontal: r.horizontal_deviation || 0,
        vertical: r.vertical_deviation || 0,
        timestamp: r.start_time || Date.now(),
      })),
      design: rings.map((r) => ({
        ring_number: r.ring_number,
        horizontal: 0,
        vertical: 0,
        timestamp: r.start_time || Date.now(),
      })),
      tolerance_upper: rings.map((r) => ({
        ring_number: r.ring_number,
        horizontal: 30,
        vertical: 30,
        timestamp: r.start_time || Date.now(),
      })),
      tolerance_lower: rings.map((r) => ({
        ring_number: r.ring_number,
        horizontal: -30,
        vertical: -30,
        timestamp: r.start_time || Date.now(),
      })),
    };
  }, [rings]);

  const settlementSeries: MultiSeriesData | null = useMemo(() => {
    if (!rings.length) return null;
    return {
      xAxisType: 'ring',
      series: [
        {
          label: '沉降(mm)',
          unit: 'mm',
          data: rings.map((r) => ({
            timestamp: r.ring_number,
            value: r.settlement_value ?? 0,
            ring_number: r.ring_number,
          })),
        },
      ],
    };
  }, [rings]);

  const correlationContent = (
    <Space direction="vertical">
      <Paragraph>当前为演示数据，尚未接入相关性分析模型。</Paragraph>
      <Paragraph>可从沉降、推力、注浆压力等参数中计算皮尔逊/斯皮尔曼相关系数，后续版本接入。</Paragraph>
      <Button icon={<ReloadOutlined />} onClick={() => refresh?.()}>
        重新拉取数据
      </Button>
    </Space>
  );

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space align="center">
        <LineChartOutlined style={{ color: '#1890ff', fontSize: 20 }} />
        <Title level={4} style={{ margin: 0 }}>
          数据分析
        </Title>
        <Button icon={<ReloadOutlined />} size="small" onClick={() => refresh?.()} loading={loading.rings}>
          刷新
        </Button>
      </Space>

      <Row gutter={[16, 16]}>
        <Col span={24} xl={12}>
          <Card title="轨迹分析">
            {trajectoryData ? (
              <TrajectoryPlot data={trajectoryData} height={320} showDataZoom />
            ) : (
              <Empty description="暂无环数据，可稍后刷新" />
            )}
          </Card>
        </Col>
        <Col span={24} xl={12}>
          <Card title="沉降趋势">
            {settlementSeries ? (
              <ParameterTimeSeries
                data={settlementSeries}
                title="沉降随环号"
                height={320}
                showLegend={false}
                yAxisName="沉降 (mm)"
                yAxisUnit="mm"
              />
            ) : (
              <Empty description="暂无沉降数据" />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="参数相关性" extra={<DeploymentUnitOutlined />}>
        {correlationContent}
      </Card>
    </Space>
  );
};

export default Analytics;
