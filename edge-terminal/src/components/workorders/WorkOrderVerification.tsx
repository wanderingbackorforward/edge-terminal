/**
 * Work Order Verification Component (T192)
 * Closed-loop verification tracking for work orders
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Typography,
  Space,
  Tag,
  Statistic,
  Row,
  Col,
  Progress,
  Table,
  Alert,
  Button,
  Form,
  Input,
  Radio,
  message,
  Tooltip,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  LineChartOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import type { WorkOrder, RingSummary, VerifyWorkOrderRequest } from '../../types/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface WorkOrderVerificationProps {
  workOrder: WorkOrder;
  subsequentRings?: RingSummary[];
  onVerify: (request: VerifyWorkOrderRequest) => Promise<void>;
  onCancel?: () => void;
}

export const WorkOrderVerification: React.FC<WorkOrderVerificationProps> = ({
  workOrder,
  subsequentRings = [],
  onVerify,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<{
    improved: boolean;
    beforeAvg: number;
    afterAvg: number;
    changePercent: number;
  } | null>(null);

  // Analyze subsequent ring data to determine effectiveness
  useEffect(() => {
    if (subsequentRings.length >= workOrder.verification_ring_count && workOrder.indicator_name) {
      // Simple analysis: compare average indicator value before and after
      // In production, this would be more sophisticated
      const indicatorKey = workOrder.indicator_name as keyof RingSummary;
      const beforeValue = 30; // Mock: value before work order
      const afterValues = subsequentRings
        .map((ring) => {
          const value = ring[indicatorKey];
          return typeof value === 'number' ? value : null;
        })
        .filter((v): v is number => v !== null);

      if (afterValues.length > 0) {
        const afterAvg = afterValues.reduce((a, b) => a + b, 0) / afterValues.length;
        const changePercent = ((afterAvg - beforeValue) / beforeValue) * 100;

        setAnalysis({
          improved: afterAvg < beforeValue, // For settlement, lower is better
          beforeAvg: beforeValue,
          afterAvg,
          changePercent,
        });
      }
    }
  }, [subsequentRings, workOrder]);

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      await onVerify({
        verified_by: 'Admin', // In production, get from auth context
        verification_result: values.verification_result,
        notes: values.notes,
      });
      message.success('Verification recorded successfully');
      form.resetFields();
    } catch (error) {
      message.error('Failed to record verification');
    } finally {
      setLoading(false);
    }
  };

  const ringsCollected = subsequentRings.length;
  const ringsRequired = workOrder.verification_ring_count;
  const progressPercent = Math.min(100, (ringsCollected / ringsRequired) * 100);
  const canVerify = ringsCollected >= ringsRequired;

  // Sample data for the verification table
  const ringColumns = [
    {
      title: 'Ring',
      dataIndex: 'ring_number',
      key: 'ring_number',
    },
    {
      title: 'Settlement (mm)',
      dataIndex: 'settlement_value',
      key: 'settlement',
      render: (val: number | null) => val?.toFixed(2) ?? '-',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: any, record: RingSummary) => {
        const val = record.settlement_value;
        if (val === null) return <Tag>No Data</Tag>;
        if (val < 25) return <Tag color="green">Normal</Tag>;
        if (val < 30) return <Tag color="orange">Attention</Tag>;
        return <Tag color="red">Elevated</Tag>;
      },
    },
  ];

  return (
    <div>
      {/* Work Order Info */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={4}>
          <Text strong>{workOrder.title}</Text>
          <Space>
            <Tag>{workOrder.category}</Tag>
            {workOrder.completed_at && (
              <Text type="secondary">
                Completed: {new Date(workOrder.completed_at * 1000).toLocaleDateString()}
              </Text>
            )}
          </Space>
        </Space>
      </Card>

      {/* Verification Progress */}
      <Card
        size="small"
        title={
          <Space>
            <HistoryOutlined />
            Verification Progress
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Statistic
              title="Rings Collected"
              value={ringsCollected}
              suffix={`/ ${ringsRequired}`}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Collection Progress"
              value={progressPercent}
              suffix="%"
              precision={0}
            />
          </Col>
        </Row>
        <Progress
          percent={progressPercent}
          status={canVerify ? 'success' : 'active'}
          style={{ marginTop: 16 }}
        />
        {!canVerify && (
          <Alert
            message={`Waiting for ${ringsRequired - ringsCollected} more ring(s) to complete verification analysis`}
            type="info"
            style={{ marginTop: 16 }}
            showIcon
          />
        )}
      </Card>

      {/* Analysis Results */}
      {analysis && (
        <Card
          size="small"
          title={
            <Space>
              <LineChartOutlined />
              Effectiveness Analysis
            </Space>
          }
          style={{ marginBottom: 16 }}
        >
          <Row gutter={16}>
            <Col span={8}>
              <Statistic
                title="Before Intervention"
                value={analysis.beforeAvg}
                suffix="mm"
                precision={2}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="After Intervention"
                value={analysis.afterAvg}
                suffix="mm"
                precision={2}
                valueStyle={{ color: analysis.improved ? '#52c41a' : '#ff4d4f' }}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="Change"
                value={Math.abs(analysis.changePercent)}
                suffix="%"
                prefix={analysis.changePercent < 0 ? '↓' : '↑'}
                precision={1}
                valueStyle={{ color: analysis.improved ? '#52c41a' : '#ff4d4f' }}
              />
            </Col>
          </Row>
          <Alert
            message={
              analysis.improved
                ? 'The intervention appears to be effective. Indicator values have improved.'
                : 'The intervention may not have been fully effective. Further action may be required.'
            }
            type={analysis.improved ? 'success' : 'warning'}
            style={{ marginTop: 16 }}
            showIcon
            icon={
              analysis.improved ? <CheckCircleOutlined /> : <QuestionCircleOutlined />
            }
          />
        </Card>
      )}

      {/* Subsequent Ring Data */}
      {subsequentRings.length > 0 && (
        <Card
          size="small"
          title="Subsequent Ring Data"
          style={{ marginBottom: 16 }}
        >
          <Table
            dataSource={subsequentRings}
            columns={ringColumns}
            rowKey="ring_number"
            size="small"
            pagination={false}
          />
        </Card>
      )}

      {/* Verification Form */}
      {canVerify && (
        <Card size="small" title="Record Verification">
          <Form form={form} layout="vertical" onFinish={handleSubmit}>
            <Form.Item
              name="verification_result"
              label="Verification Result"
              rules={[{ required: true, message: 'Please select verification result' }]}
            >
              <Radio.Group>
                <Space direction="vertical">
                  <Radio value="success">
                    <Space>
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      <Text>Successful - Intervention was effective</Text>
                    </Space>
                  </Radio>
                  <Radio value="failure">
                    <Space>
                      <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                      <Text>Unsuccessful - Further action required</Text>
                    </Space>
                  </Radio>
                </Space>
              </Radio.Group>
            </Form.Item>

            <Form.Item
              name="notes"
              label="Verification Notes"
              rules={[{ required: true, message: 'Please add verification notes' }]}
            >
              <TextArea
                rows={3}
                placeholder="Describe the verification outcome and any observations..."
              />
            </Form.Item>

            <Form.Item>
              <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                {onCancel && <Button onClick={onCancel}>Cancel</Button>}
                <Button type="primary" htmlType="submit" loading={loading}>
                  Submit Verification
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      )}
    </div>
  );
};

export default WorkOrderVerification;
