/**
 * Work Order Detail Component (T190)
 * Detailed view of a single work order
 */
import React from 'react';
import {
  Card,
  Descriptions,
  Tag,
  Badge,
  Timeline,
  Typography,
  Space,
  Button,
  Divider,
  Avatar,
  Progress,
} from 'antd';
import {
  UserOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import type { WorkOrder, WorkOrderStatus, WorkOrderPriority } from '../../types/api';

const { Title, Text, Paragraph } = Typography;

interface WorkOrderDetailProps {
  workOrder: WorkOrder;
  onAssign?: () => void;
  onUpdateStatus?: (status: WorkOrderStatus) => void;
  onVerify?: () => void;
}

export const WorkOrderDetail: React.FC<WorkOrderDetailProps> = ({
  workOrder,
  onAssign,
  onUpdateStatus,
  onVerify,
}) => {
  const getPriorityTag = (priority: WorkOrderPriority) => {
    const colors: Record<WorkOrderPriority, string> = {
      critical: 'red',
      high: 'orange',
      medium: 'blue',
      low: 'default',
    };
    return <Tag color={colors[priority]}>{priority.toUpperCase()}</Tag>;
  };

  const getStatusBadge = (status: WorkOrderStatus) => {
    const config: Record<WorkOrderStatus, { status: 'default' | 'processing' | 'success' | 'warning' | 'error'; text: string }> = {
      pending: { status: 'warning', text: 'Pending' },
      assigned: { status: 'processing', text: 'Assigned' },
      in_progress: { status: 'processing', text: 'In Progress' },
      completed: { status: 'success', text: 'Completed' },
      cancelled: { status: 'default', text: 'Cancelled' },
    };
    return <Badge status={config[status].status} text={config[status].text} />;
  };

  const getProgressPercent = (status: WorkOrderStatus) => {
    const progress: Record<WorkOrderStatus, number> = {
      pending: 0,
      assigned: 25,
      in_progress: 50,
      completed: 100,
      cancelled: 0,
    };
    return progress[status];
  };

  const buildTimeline = () => {
    const items: any[] = [];

    // Created
    items.push({
      color: 'green',
      dot: <FileTextOutlined />,
      children: (
        <>
          <Text strong>Work Order Created</Text>
          <br />
          <Text type="secondary">
            {new Date(workOrder.created_at * 1000).toLocaleString()}
          </Text>
        </>
      ),
    });

    // Assigned
    if (workOrder.assigned_at) {
      items.push({
        color: 'blue',
        dot: <UserOutlined />,
        children: (
          <>
            <Text strong>Assigned to {workOrder.assigned_to}</Text>
            <br />
            <Text type="secondary">
              By {workOrder.assigned_by} at {new Date(workOrder.assigned_at * 1000).toLocaleString()}
            </Text>
          </>
        ),
      });
    }

    // In Progress (status updated)
    if (workOrder.status === 'in_progress' || workOrder.status === 'completed') {
      items.push({
        color: 'blue',
        dot: <SyncOutlined />,
        children: (
          <>
            <Text strong>Work Started</Text>
            <br />
            <Text type="secondary">
              {new Date(workOrder.status_updated_at * 1000).toLocaleString()}
            </Text>
          </>
        ),
      });
    }

    // Completed
    if (workOrder.completed_at) {
      items.push({
        color: 'green',
        dot: <CheckCircleOutlined />,
        children: (
          <>
            <Text strong>Completed by {workOrder.completed_by}</Text>
            <br />
            <Text type="secondary">
              {new Date(workOrder.completed_at * 1000).toLocaleString()}
            </Text>
            {workOrder.completion_notes && (
              <>
                <br />
                <Text>Notes: {workOrder.completion_notes}</Text>
              </>
            )}
          </>
        ),
      });
    }

    // Verified
    if (workOrder.verified_at) {
      items.push({
        color: workOrder.verification_result === 'success' ? 'green' : 'red',
        dot: <CheckCircleOutlined />,
        children: (
          <>
            <Text strong>
              Verification: {workOrder.verification_result === 'success' ? 'Successful' : 'Failed'}
            </Text>
            <br />
            <Text type="secondary">
              {new Date(workOrder.verified_at * 1000).toLocaleString()}
            </Text>
          </>
        ),
      });
    }

    return items;
  };

  return (
    <div>
      {/* Header */}
      <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
        <Space>
          {getPriorityTag(workOrder.priority)}
          {getStatusBadge(workOrder.status)}
          <Tag>{workOrder.category}</Tag>
        </Space>
        <Title level={4} style={{ margin: 0 }}>
          {workOrder.title}
        </Title>
      </Space>

      {/* Progress */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Progress
          percent={getProgressPercent(workOrder.status)}
          status={workOrder.status === 'cancelled' ? 'exception' : undefined}
          format={() => workOrder.status.replace('_', ' ').toUpperCase()}
        />
      </Card>

      {/* Details */}
      <Descriptions column={1} bordered size="small" style={{ marginBottom: 16 }}>
        <Descriptions.Item label="ID">
          <Text copyable>{workOrder.work_order_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Ring Number">
          {workOrder.ring_number ?? 'N/A'}
        </Descriptions.Item>
        <Descriptions.Item label="Indicator">
          {workOrder.indicator_name ?? 'N/A'}
        </Descriptions.Item>
        <Descriptions.Item label="Assigned To">
          {workOrder.assigned_to ? (
            <Space>
              <Avatar size="small" icon={<UserOutlined />} />
              {workOrder.assigned_to}
            </Space>
          ) : (
            <Text type="secondary">Not assigned</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Warning ID">
          {workOrder.warning_id ?? 'N/A'}
        </Descriptions.Item>
        <Descriptions.Item label="Verification Required">
          {workOrder.verification_required ? (
            <Tag color="blue">Yes ({workOrder.verification_ring_count} rings)</Tag>
          ) : (
            <Tag>No</Tag>
          )}
        </Descriptions.Item>
      </Descriptions>

      {/* Description */}
      <Card size="small" title="Description" style={{ marginBottom: 16 }}>
        <Paragraph>{workOrder.description}</Paragraph>
      </Card>

      {/* Timeline */}
      <Card size="small" title="Activity Timeline" style={{ marginBottom: 16 }}>
        <Timeline items={buildTimeline()} />
      </Card>

      {/* Actions */}
      <Space direction="vertical" style={{ width: '100%' }}>
        {workOrder.status === 'pending' && onAssign && (
          <Button type="primary" block onClick={onAssign}>
            Assign Work Order
          </Button>
        )}
        {workOrder.status === 'assigned' && onUpdateStatus && (
          <Button block onClick={() => onUpdateStatus('in_progress')}>
            Start Work
          </Button>
        )}
        {workOrder.status === 'in_progress' && onUpdateStatus && (
          <Button type="primary" block onClick={() => onUpdateStatus('completed')}>
            Mark as Completed
          </Button>
        )}
        {workOrder.status === 'completed' &&
          workOrder.verification_required &&
          !workOrder.verified_at &&
          onVerify && (
            <Button block onClick={onVerify}>
              Verify Effectiveness
            </Button>
          )}
      </Space>
    </div>
  );
};

export default WorkOrderDetail;
