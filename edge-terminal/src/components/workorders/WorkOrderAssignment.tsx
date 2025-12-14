/**
 * Work Order Assignment Component (T191)
 * Form for assigning work orders to team members
 */
import React, { useState } from 'react';
import {
  Form,
  Select,
  Input,
  Button,
  Space,
  Card,
  Typography,
  Tag,
  Avatar,
  List,
  message,
} from 'antd';
import { UserOutlined, TeamOutlined } from '@ant-design/icons';
import type { WorkOrder, AssignWorkOrderRequest } from '../../types/api';

const { TextArea } = Input;
const { Text } = Typography;

interface WorkOrderAssignmentProps {
  workOrder: WorkOrder;
  onAssign: (request: AssignWorkOrderRequest) => Promise<void>;
  onCancel?: () => void;
}

// Mock team members - in production, this would come from an API
const TEAM_MEMBERS = [
  { id: 'engineer_1', name: 'Zhang Wei', role: 'Senior Engineer', specialization: ['settlement', 'alignment'] },
  { id: 'engineer_2', name: 'Li Ming', role: 'Engineer', specialization: ['chamber_pressure', 'torque'] },
  { id: 'supervisor', name: 'Wang Jun', role: 'Supervisor', specialization: ['all'] },
  { id: 'maintenance_1', name: 'Chen Fang', role: 'Maintenance', specialization: ['maintenance'] },
  { id: 'maintenance_team', name: 'Maintenance Team', role: 'Team', specialization: ['maintenance', 'other'] },
];

export const WorkOrderAssignment: React.FC<WorkOrderAssignmentProps> = ({
  workOrder,
  onAssign,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [selectedMember, setSelectedMember] = useState<string | null>(null);

  // Get recommended assignees based on work order category
  const getRecommendedAssignees = () => {
    return TEAM_MEMBERS.filter(
      (member) =>
        member.specialization.includes('all') ||
        member.specialization.includes(workOrder.category)
    );
  };

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      await onAssign({
        assigned_to: values.assigned_to,
        assigned_by: 'Admin', // In production, get from auth context
        notes: values.notes,
      });
      message.success('Work order assigned successfully');
      form.resetFields();
    } catch (error) {
      message.error('Failed to assign work order');
    } finally {
      setLoading(false);
    }
  };

  const recommendedMembers = getRecommendedAssignees();

  return (
    <div>
      {/* Work Order Summary */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={4}>
          <Text strong>{workOrder.title}</Text>
          <Space>
            <Tag>{workOrder.category}</Tag>
            <Tag color={workOrder.priority === 'critical' ? 'red' : workOrder.priority === 'high' ? 'orange' : 'blue'}>
              {workOrder.priority.toUpperCase()}
            </Tag>
          </Space>
        </Space>
      </Card>

      {/* Recommended Assignees */}
      <Card
        size="small"
        title={
          <Space>
            <TeamOutlined />
            Recommended Assignees
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <List
          size="small"
          dataSource={recommendedMembers}
          renderItem={(member) => (
            <List.Item
              style={{
                cursor: 'pointer',
                background: selectedMember === member.id ? '#1890ff15' : 'transparent',
                borderRadius: 4,
                padding: '8px 12px',
              }}
              onClick={() => {
                setSelectedMember(member.id);
                form.setFieldValue('assigned_to', member.id);
              }}
            >
              <List.Item.Meta
                avatar={<Avatar icon={<UserOutlined />} />}
                title={member.name}
                description={
                  <Space size={4}>
                    <Text type="secondary">{member.role}</Text>
                    {member.specialization.map((s) => (
                      <Tag key={s} size="small">
                        {s}
                      </Tag>
                    ))}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      {/* Assignment Form */}
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="assigned_to"
          label="Assign To"
          rules={[{ required: true, message: 'Please select an assignee' }]}
        >
          <Select placeholder="Select team member" showSearch optionFilterProp="children">
            {TEAM_MEMBERS.map((member) => (
              <Select.Option key={member.id} value={member.id}>
                <Space>
                  <Avatar size="small" icon={<UserOutlined />} />
                  {member.name}
                  <Text type="secondary">({member.role})</Text>
                </Space>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="notes" label="Assignment Notes">
          <TextArea
            rows={3}
            placeholder="Add any additional instructions or context for the assignee..."
          />
        </Form.Item>

        <Form.Item>
          <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
            {onCancel && (
              <Button onClick={onCancel}>Cancel</Button>
            )}
            <Button type="primary" htmlType="submit" loading={loading}>
              Assign Work Order
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};

export default WorkOrderAssignment;
