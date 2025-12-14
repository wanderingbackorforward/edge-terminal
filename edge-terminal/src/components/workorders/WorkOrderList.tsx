/**
 * Work Order List Component (T189)
 * Displays work orders in a compact list format
 */
import React from 'react';
import { List, Tag, Space, Typography, Avatar, Badge, Button, Empty } from 'antd';
import {
  UserOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { WorkOrder, WorkOrderStatus, WorkOrderPriority } from '../../types/api';

const { Text } = Typography;

interface WorkOrderListProps {
  workOrders: WorkOrder[];
  loading?: boolean;
  onSelect?: (workOrder: WorkOrder) => void;
  onAssign?: (workOrder: WorkOrder) => void;
  compact?: boolean;
}

export const WorkOrderList: React.FC<WorkOrderListProps> = ({
  workOrders,
  loading = false,
  onSelect,
  onAssign,
  compact = false,
}) => {
  const getPriorityColor = (priority: WorkOrderPriority) => {
    const colors: Record<WorkOrderPriority, string> = {
      critical: 'red',
      high: 'orange',
      medium: 'blue',
      low: 'default',
    };
    return colors[priority];
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

  if (workOrders.length === 0) {
    return <Empty description="No work orders" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <List
      loading={loading}
      dataSource={workOrders}
      size={compact ? 'small' : 'default'}
      renderItem={(item) => (
        <List.Item
          key={item.work_order_id}
          style={{ cursor: onSelect ? 'pointer' : 'default' }}
          onClick={() => onSelect?.(item)}
          actions={
            !compact && item.status === 'pending' && onAssign
              ? [
                  <Button
                    type="link"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAssign(item);
                    }}
                  >
                    Assign
                  </Button>,
                ]
              : undefined
          }
        >
          <List.Item.Meta
            avatar={
              <Avatar
                style={{
                  backgroundColor:
                    item.priority === 'critical'
                      ? '#ff4d4f'
                      : item.priority === 'high'
                      ? '#fa8c16'
                      : '#1890ff',
                }}
                icon={
                  item.priority === 'critical' || item.priority === 'high' ? (
                    <ExclamationCircleOutlined />
                  ) : (
                    <ClockCircleOutlined />
                  )
                }
              />
            }
            title={
              <Space>
                <Text ellipsis style={{ maxWidth: compact ? 150 : 250 }}>
                  {item.title}
                </Text>
                <Tag color={getPriorityColor(item.priority)}>
                  {item.priority.toUpperCase()}
                </Tag>
              </Space>
            }
            description={
              <Space direction="vertical" size={0}>
                <Space size="small">
                  {getStatusBadge(item.status)}
                  <Tag>{item.category}</Tag>
                </Space>
                {!compact && (
                  <Space size="small">
                    {item.assigned_to ? (
                      <Space size={4}>
                        <UserOutlined />
                        <Text type="secondary">{item.assigned_to}</Text>
                      </Space>
                    ) : (
                      <Text type="secondary">Unassigned</Text>
                    )}
                    {item.ring_number && (
                      <Text type="secondary">Ring #{item.ring_number}</Text>
                    )}
                  </Space>
                )}
              </Space>
            }
          />
        </List.Item>
      )}
    />
  );
};

export default WorkOrderList;
