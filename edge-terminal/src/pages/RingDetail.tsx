/**
 * Ring Detail Page (T178)
 * Detailed view for a specific ring with all data and predictions
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Descriptions,
  Statistic,
  Tag,
  Space,
  Button,
  InputNumber,
  Spin,
  Alert,
  Tabs,
  Table,
  Timeline,
  Progress,
  Tooltip,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  ReloadOutlined,
  AimOutlined,
  LineChartOutlined,
  AlertOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ringApi, predictionApi, warningApi } from '../services/api';
import { TrajectoryPlot, ParameterTimeSeries, SettlementContour } from '../components/charts';
import type { RingSummary, PredictionResult, WarningEvent } from '../types/api';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

export const RingDetail: React.FC = () => {
  const { ringNumber } = useParams<{ ringNumber: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [ringData, setRingData] = useState<RingSummary | null>(null);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [warnings, setWarnings] = useState<WarningEvent[]>([]);
  const [inputRing, setInputRing] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const currentRing = ringNumber ? parseInt(ringNumber, 10) : null;

  useEffect(() => {
    if (currentRing) {
      fetchRingData(currentRing);
      setInputRing(currentRing);
    }
  }, [currentRing]);

  const fetchRingData = async (ring: number) => {
    setLoading(true);
    setError(null);
    try {
      const [ringResponse, predResponse] = await Promise.all([
        ringApi.getRing(ring),
        predictionApi.getPrediction(ring).catch(() => null),
      ]);

      setRingData(ringResponse);
      setPrediction(predResponse);

      // Fetch warnings for this ring
      const warningsResponse = await warningApi.getWarnings({ ring_number: ring });
      setWarnings(warningsResponse.warnings || []);
    } catch (err: any) {
      setError(err.message || err.detail || 'Failed to load ring data');
      setRingData(null);
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = (direction: 'prev' | 'next') => {
    if (currentRing === null) return;
    const newRing = direction === 'prev' ? currentRing - 1 : currentRing + 1;
    if (newRing > 0) {
      navigate(`/rings/${newRing}`);
    }
  };

  const handleGoToRing = () => {
    if (inputRing && inputRing > 0) {
      navigate(`/rings/${inputRing}`);
    }
  };

  const getDataQualityColor = (flag?: string) => {
    switch (flag) {
      case 'complete':
        return 'success';
      case 'incomplete':
        return 'warning';
      case 'missing_plc':
      case 'missing_monitoring':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatValue = (value: number | null | undefined, decimals = 2, unit = '') => {
    if (value === null || value === undefined) return '-';
    return `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
  };

  // Parameter summary for table
  const parameterData = ringData ? [
    { key: 'thrust', name: '推力', mean: ringData.mean_thrust, max: ringData.max_thrust, min: ringData.min_thrust, std: ringData.std_thrust, unit: 'kN' },
    { key: 'torque', name: '扭矩', mean: ringData.mean_torque, max: ringData.max_torque, min: null, std: null, unit: 'kN·m' },
    { key: 'pressure', name: '仓压', mean: ringData.mean_chamber_pressure, max: null, min: null, std: null, unit: 'bar' },
    { key: 'advance', name: '推进速度', mean: ringData.mean_advance_rate, max: null, min: null, std: null, unit: 'mm/min' },
    { key: 'grout', name: '注浆压力', mean: ringData.mean_grout_pressure, max: null, min: null, std: null, unit: 'bar' },
  ] : [];

  const attitudeData = ringData ? [
    { key: 'pitch', name: '俯仰', mean: ringData.mean_pitch, max: null, unit: '°' },
    { key: 'roll', name: '横滚', mean: ringData.mean_roll, max: null, unit: '°' },
    { key: 'yaw', name: '偏航', mean: ringData.mean_yaw, max: null, unit: '°' },
    { key: 'h_dev', name: '水平偏差', mean: null, max: ringData.horizontal_deviation_max, unit: 'mm' },
    { key: 'v_dev', name: '垂直偏差', mean: null, max: ringData.vertical_deviation_max, unit: 'mm' },
  ] : [];

  const paramColumns = [
    { title: '参数', dataIndex: 'name', key: 'name' },
    { title: '均值', dataIndex: 'mean', key: 'mean', render: (v: number | null, r: any) => formatValue(v, 2, r.unit) },
    { title: '最大', dataIndex: 'max', key: 'max', render: (v: number | null, r: any) => formatValue(v, 2, r.unit) },
    { title: '最小', dataIndex: 'min', key: 'min', render: (v: number | null, r: any) => formatValue(v, 2, r.unit) },
    { title: '标准差', dataIndex: 'std', key: 'std', render: (v: number | null) => formatValue(v) },
  ];

  if (!currentRing) {
    return (
      <div>
        <Title level={2}>
          <AimOutlined style={{ marginRight: 12 }} />
          环详情
        </Title>
        <Card>
          <Space direction="vertical" style={{ width: '100%' }} align="center">
            <Text>请输入环号查看详情：</Text>
            <Space>
              <InputNumber
                min={1}
                placeholder="环号"
                value={inputRing}
                onChange={(v) => setInputRing(v)}
                style={{ width: 150 }}
              />
              <Button type="primary" onClick={handleGoToRing}>
                跳转
              </Button>
            </Space>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => handleNavigate('prev')}
              disabled={currentRing <= 1}
            />
            <Title level={2} style={{ margin: 0 }}>
              <AimOutlined style={{ marginRight: 12 }} />
              Ring #{currentRing}
            </Title>
            <Button
              icon={<ArrowRightOutlined />}
              onClick={() => handleNavigate('next')}
            />
          </Space>
        </Col>
        <Col>
          <Space>
            <InputNumber
              min={1}
              value={inputRing}
              onChange={(v) => setInputRing(v)}
              style={{ width: 100 }}
            />
            <Button onClick={handleGoToRing}>Go</Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => fetchRingData(currentRing)}
            >
              Refresh
            </Button>
          </Space>
        </Col>
      </Row>

      {loading ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>正在加载环数据...</div>
          </div>
        </Card>
      ) : error ? (
        <Alert
          message="环数据加载失败"
          description={error}
          type="error"
          showIcon
          action={
            <Button onClick={() => fetchRingData(currentRing)}>
              重试
            </Button>
          }
        />
      ) : ringData ? (
        <>
          {/* Summary Cards */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Settlement"
                  value={ringData.settlement_value ?? '-'}
                  suffix="mm"
                  precision={2}
                  valueStyle={{
                    color: (ringData.settlement_value ?? 0) > 30 ? '#ff4d4f' : '#52c41a'
                  }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Predicted Settlement"
                  value={prediction?.predicted_settlement ?? '-'}
                  suffix="mm"
                  precision={2}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Specific Energy"
                  value={ringData.specific_energy ?? '-'}
                  suffix="kJ/m³"
                  precision={1}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Ground Loss Rate"
                  value={ringData.ground_loss_rate ?? '-'}
                  suffix="%"
                  precision={2}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Active Warnings"
                  value={warnings.filter(w => w.status === 'active').length}
                  valueStyle={{
                    color: warnings.filter(w => w.status === 'active').length > 0 ? '#ff4d4f' : '#52c41a'
                  }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="Data Quality"
                  value={ringData.data_completeness_flag || 'Unknown'}
                  valueStyle={{ fontSize: 16 }}
                  prefix={
                    ringData.data_completeness_flag === 'complete' ?
                      <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                      <ExclamationCircleOutlined style={{ color: '#faad14' }} />
                  }
                />
              </Card>
            </Col>
          </Row>

          {/* Tabs for different sections */}
          <Tabs defaultActiveKey="overview">
            <TabPane tab={<span><LineChartOutlined /> Overview</span>} key="overview">
              <Row gutter={16}>
                <Col span={12}>
                  <Card title="Ring Information" style={{ marginBottom: 16 }}>
                    <Descriptions column={2} size="small">
                      <Descriptions.Item label="Start Time">
                        {new Date(ringData.start_time * 1000).toLocaleString()}
                      </Descriptions.Item>
                      <Descriptions.Item label="End Time">
                        {new Date(ringData.end_time * 1000).toLocaleString()}
                      </Descriptions.Item>
                      <Descriptions.Item label="Duration">
                        {((ringData.end_time - ringData.start_time) / 60).toFixed(0)} min
                      </Descriptions.Item>
                      <Descriptions.Item label="Geological Zone">
                        <Tag>{ringData.geological_zone || 'Unknown'}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Soil Type">
                        {ringData.soil_type || '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Overburden">
                        {formatValue(ringData.overburden_depth, 1, 'm')}
                      </Descriptions.Item>
                      <Descriptions.Item label="Groundwater">
                        {formatValue(ringData.groundwater_level, 1, 'm')}
                      </Descriptions.Item>
                      <Descriptions.Item label="Data Quality">
                        <Tag color={getDataQualityColor(ringData.data_completeness_flag)}>
                          {ringData.data_completeness_flag || 'Unknown'}
                        </Tag>
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>

                  <Card title="Tunneling Parameters" style={{ marginBottom: 16 }}>
                    <Table
                      dataSource={parameterData}
                      columns={paramColumns}
                      pagination={false}
                      size="small"
                    />
                  </Card>
                </Col>

                <Col span={12}>
                  {prediction && (
                    <Card title="Prediction Results" style={{ marginBottom: 16 }}>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="Predicted Settlement">
                          <Text strong>{formatValue(prediction.predicted_settlement, 2, 'mm')}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="Confidence Interval">
                          [{formatValue(prediction.confidence_lower, 2)} - {formatValue(prediction.confidence_upper, 2)}] mm
                        </Descriptions.Item>
                        <Descriptions.Item label="Model Version">
                          <Tag color="blue">{prediction.model_version}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="Uncertainty">
                          <Tag color={prediction.uncertainty_flag === 'normal' ? 'green' : 'orange'}>
                            {prediction.uncertainty_flag}
                          </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="Prediction Time">
                          {new Date(prediction.timestamp * 1000).toLocaleString()}
                        </Descriptions.Item>
                      </Descriptions>

                      {/* Comparison Chart */}
                      <div style={{ marginTop: 16 }}>
                        <Text type="secondary">Actual vs Predicted:</Text>
                        <Progress
                          percent={Math.min(100, ((ringData.settlement_value ?? 0) / (prediction.predicted_settlement || 1)) * 100)}
                          format={() => `${formatValue(ringData.settlement_value)} / ${formatValue(prediction.predicted_settlement)} mm`}
                          status={Math.abs((ringData.settlement_value ?? 0) - (prediction.predicted_settlement || 0)) > 5 ? 'exception' : 'success'}
                        />
                      </div>
                    </Card>
                  )}

                  <Card title="Attitude Data">
                    <Table
                      dataSource={attitudeData}
                      columns={[
                        { title: 'Parameter', dataIndex: 'name', key: 'name' },
                        { title: 'Mean', dataIndex: 'mean', key: 'mean', render: (v: number | null, r: any) => formatValue(v, 2, r.unit) },
                        { title: 'Max', dataIndex: 'max', key: 'max', render: (v: number | null, r: any) => formatValue(v, 2, r.unit) },
                      ]}
                      pagination={false}
                      size="small"
                    />
                  </Card>
                </Col>
              </Row>
            </TabPane>

            <TabPane tab={<span><AlertOutlined /> Warnings ({warnings.length})</span>} key="warnings">
              {warnings.length > 0 ? (
                <Card>
                  <Table
                    dataSource={warnings}
                    rowKey="warning_id"
                    columns={[
                      { title: 'ID', dataIndex: 'warning_id', key: 'warning_id', width: 80 },
                      {
                        title: 'Level',
                        dataIndex: 'warning_level',
                        key: 'level',
                        render: (level: string) => (
                          <Tag color={level === 'Alarm' ? 'red' : level === 'Warning' ? 'orange' : 'blue'}>
                            {level}
                          </Tag>
                        ),
                      },
                      { title: 'Indicator', dataIndex: 'indicator_type', key: 'indicator' },
                      { title: 'Value', dataIndex: 'indicator_value', key: 'value', render: (v: number) => formatValue(v) },
                      { title: 'Threshold', dataIndex: 'threshold', key: 'threshold', render: (v: number) => formatValue(v) },
                      {
                        title: 'Status',
                        dataIndex: 'status',
                        key: 'status',
                        render: (status: string) => (
                          <Tag color={status === 'active' ? 'red' : status === 'acknowledged' ? 'orange' : 'green'}>
                            {status}
                          </Tag>
                        ),
                      },
                      {
                        title: 'Time',
                        dataIndex: 'timestamp',
                        key: 'time',
                        render: (ts: number) => new Date(ts * 1000).toLocaleString(),
                      },
                    ]}
                    pagination={false}
                  />
                </Card>
              ) : (
                <Empty description="No warnings for this ring" />
              )}
            </TabPane>

            <TabPane tab={<span><HistoryOutlined /> History</span>} key="history">
              <Card>
                <Timeline
                  items={[
                    {
                      color: 'green',
                      children: (
                        <>
                          <Text strong>Ring Started</Text>
                          <br />
                          <Text type="secondary">
                            {new Date(ringData.start_time * 1000).toLocaleString()}
                          </Text>
                        </>
                      ),
                    },
                    {
                      color: 'blue',
                      children: (
                        <>
                          <Text strong>Ring Completed</Text>
                          <br />
                          <Text type="secondary">
                            {new Date(ringData.end_time * 1000).toLocaleString()}
                          </Text>
                          <br />
                          <Text>
                            Duration: {((ringData.end_time - ringData.start_time) / 60).toFixed(0)} minutes
                          </Text>
                        </>
                      ),
                    },
                    ...(prediction ? [{
                      color: 'purple',
                      children: (
                        <>
                          <Text strong>Prediction Generated</Text>
                          <br />
                          <Text type="secondary">
                            {new Date(prediction.timestamp * 1000).toLocaleString()}
                          </Text>
                          <br />
                          <Text>
                            Predicted: {formatValue(prediction.predicted_settlement, 2, 'mm')}
                          </Text>
                        </>
                      ),
                    }] : []),
                    ...warnings.map(w => ({
                      color: w.warning_level === 'Alarm' ? 'red' : 'orange',
                      children: (
                        <>
                          <Text strong>{w.warning_level}: {w.indicator_type}</Text>
                          <br />
                          <Text type="secondary">
                            {new Date(w.timestamp * 1000).toLocaleString()}
                          </Text>
                          <br />
                          <Text>
                            Value: {formatValue(w.indicator_value)} (Threshold: {formatValue(w.threshold)})
                          </Text>
                        </>
                      ),
                    })),
                    ...(ringData.settlement_value ? [{
                      color: 'cyan',
                      children: (
                        <>
                          <Text strong>Settlement Measured</Text>
                          <br />
                          <Text>
                            {formatValue(ringData.settlement_value, 2, 'mm')}
                          </Text>
                        </>
                      ),
                    }] : []),
                  ]}
                />
              </Card>
            </TabPane>
          </Tabs>
        </>
      ) : (
        <Empty description={`No data found for Ring #${currentRing}`} />
      )}
    </div>
  );
};

export default RingDetail;
