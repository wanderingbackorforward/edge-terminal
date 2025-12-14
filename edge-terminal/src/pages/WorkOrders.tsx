/**
 * Work Orders Page (T180)
 * Work order management with list, assignment, and tracking
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
  Row,
  Col,
  Statistic,
  Typography,
  Tooltip,
  Modal,
  message,
  Drawer,
  Form,
  Descriptions,
  Timeline,
  Badge,
  Avatar,
  Divider,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  ReloadOutlined,
  FileTextOutlined,
  UserOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { workOrderApi } from '../services/api';
import type {
  WorkOrder,
  WorkOrderStatus,
  WorkOrderPriority,
  CreateWorkOrderRequest,
  AssignWorkOrderRequest,
} from '../types/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

export const WorkOrders: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<WorkOrder | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [pagination, setPagination] = useState<TablePaginationConfig>({
    current: 1,
    pageSize: 20,
    total: 0,
  });

  // Filters
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<WorkOrderPriority | 'all'>('all');

  // Forms
  const [createForm] = Form.useForm();
  const [assignForm] = Form.useForm();

  // Fetch work orders
  const fetchWorkOrders = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: pagination.current,
        page_size: pagination.pageSize,
      };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (priorityFilter !== 'all') params.priority = priorityFilter;

      const response = await workOrderApi.getWorkOrders(params);
      setWorkOrders(response.work_orders || []);
      setPagination(prev => ({ ...prev, total: response.total }));
    } catch (err) {
      console.error('Failed to fetch work orders:', err);
      message.error('Failed to load work orders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkOrders();
  }, [pagination.current, statusFilter, priorityFilter]);

  // Statistics
  const stats = useMemo(() => {
    const pending = workOrders.filter(w => w.status === 'pending').length;
    const inProgress = workOrders.filter(w => w.status === 'in_progress').length;
    const completed = workOrders.filter(w => w.status === 'completed').length;
    const critical = workOrders.filter(w => w.priority === 'critical' && w.status !== 'completed').length;
    return { pending, inProgress, completed, critical };
  }, [workOrders]);

  // Filtered data
  const filteredData = useMemo(() => {
    if (!searchText) return workOrders;
    const search = searchText.toLowerCase();
    return workOrders.filter(w =>
      w.title.toLowerCase().includes(search) ||
      w.work_order_id.toLowerCase().includes(search) ||
      w.category.toLowerCase().includes(search)
    );
  }, [workOrders, searchText]);

  const handleViewDetail = (order: WorkOrder) => {
    setSelectedOrder(order);
    setDetailDrawerOpen(true);
  };

  const handleCreateOrder = async (values: any) => {
    try {
      const request: CreateWorkOrderRequest = {
        title: values.title,
        description: values.description,
        category: values.category,
        priority: values.priority,
        ring_number: values.ring_number,
      };
      await workOrderApi.createWorkOrder(request);
      message.success('工单创建成功');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchWorkOrders();
    } catch (error) {
      message.error('创建工单失败');
    }
  };

  const handleAssignOrder = async (values: any) => {
    if (!selectedOrder) return;
    try {
      const request: AssignWorkOrderRequest = {
        assigned_to: values.assigned_to,
        assigned_by: 'Admin',
        notes: values.notes,
      };
      await workOrderApi.assignWorkOrder(selectedOrder.work_order_id, request);
      message.success('工单已指派');
      setAssignModalOpen(false);
      assignForm.resetFields();
      fetchWorkOrders();
    } catch (error) {
      message.error('指派失败');
    }
  };

  const getPriorityTag = (priority: WorkOrderPriority) => {
    const config: Record<WorkOrderPriority, { color: string }> = {
      critical: { color: 'red' },
      high: { color: 'orange' },
      medium: { color: 'blue' },
      low: { color: 'default' },
    };
    return <Tag color={config[priority].color}>{priority.toUpperCase()}</Tag>;
  };

  const getStatusBadge = (status: WorkOrderStatus) => {
    const config: Record<WorkOrderStatus, { status: 'default' | 'processing' | 'success' | 'warning' | 'error'; text: string }> = {
      pending: { status: 'warning', text: '待处理' },
      assigned: { status: 'processing', text: '已指派' },
      in_progress: { status: 'processing', text: '处理中' },
      completed: { status: 'success', text: '已完成' },
      cancelled: { status: 'default', text: '已取消' },
    };
    const { status: badgeStatus, text } = config[status];
    return <Badge status={badgeStatus} text={text} />;
  };

  const columns: ColumnsType<WorkOrder> = [
    {
      title: 'ID',
      dataIndex: 'work_order_id',
      key: 'work_order_id',
      width: 100,
      render: (id: string) => <Text copyable={{ text: id }}>{id.slice(0, 8)}...</Text>,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      ellipsis: true,
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => <Tag>{cat}</Tag>,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority: WorkOrderPriority) => getPriorityTag(priority),
      filters: [
        { text: '紧急', value: 'critical' },
        { text: '高', value: 'high' },
        { text: '中', value: 'medium' },
        { text: '低', value: 'low' },
      ],
      onFilter: (value, record) => record.priority === value,
    },
    {
      title: '环号',
      dataIndex: 'ring_number',
      key: 'ring_number',
      width: 80,
      render: (ring: number | null) => ring ?? '-',
    },
    {
      title: '指派给',
      dataIndex: 'assigned_to',
      key: 'assigned_to',
      width: 120,
      render: (user: string | null) =>
        user ? (
          <Space>
            <Avatar size="small" icon={<UserOutlined />} />
            {user}
          </Space>
        ) : (
          <Text type="secondary">未指派</Text>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (status: WorkOrderStatus) => getStatusBadge(status),
      filters: [
        { text: '待处理', value: 'pending' },
        { text: '已指派', value: 'assigned' },
        { text: '处理中', value: 'in_progress' },
        { text: '已完成', value: 'completed' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      sorter: (a, b) => a.created_at - b.created_at,
      defaultSortOrder: 'descend',
      render: (ts: number) => new Date(ts * 1000).toLocaleDateString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => handleViewDetail(record)}>
            详情
          </Button>
          {record.status === 'pending' && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                setSelectedOrder(record);
                setAssignModalOpen(true);
              }}
            >
              指派
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const handleTableChange = (newPagination: TablePaginationConfig) => {
    setPagination(newPagination);
  };

  return (
    <div>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2} style={{ margin: 0 }}>
            <FileTextOutlined style={{ marginRight: 12 }} />
            工单管理
          </Title>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchWorkOrders}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              新建工单
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="待处理"
              value={stats.pending}
              valueStyle={{ color: '#faad14' }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="处理中"
              value={stats.inProgress}
              valueStyle={{ color: '#1890ff' }}
              prefix={<SyncOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已完成"
              value={stats.completed}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="紧急"
              value={stats.critical}
              valueStyle={{ color: stats.critical > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={8}>
            <Input
              placeholder="按标题/ID/类别搜索"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="状态"
              value={statusFilter}
              onChange={setStatusFilter}
            >
              <Select.Option value="all">全部状态</Select.Option>
              <Select.Option value="pending">待处理</Select.Option>
              <Select.Option value="assigned">已指派</Select.Option>
              <Select.Option value="in_progress">处理中</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="优先级"
              value={priorityFilter}
              onChange={setPriorityFilter}
            >
              <Select.Option value="all">全部优先级</Select.Option>
              <Select.Option value="critical">紧急</Select.Option>
              <Select.Option value="high">高</Select.Option>
              <Select.Option value="medium">中</Select.Option>
              <Select.Option value="low">低</Select.Option>
            </Select>
          </Col>
        </Row>
      </Card>

      {/* Work Orders Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="work_order_id"
          loading={loading}
          pagination={pagination}
          onChange={handleTableChange}
          scroll={{ x: 1200 }}
          size="middle"
        />
      </Card>

      {/* Detail Drawer */}
      <Drawer
        title={`工单详情：${selectedOrder?.title || ''}`}
        placement="right"
        width={600}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
      >
        {selectedOrder && (
          <div>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="ID">
                <Text copyable>{selectedOrder.work_order_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {getStatusBadge(selectedOrder.status)}
              </Descriptions.Item>
              <Descriptions.Item label="优先级">
                {getPriorityTag(selectedOrder.priority)}
              </Descriptions.Item>
              <Descriptions.Item label="类别">
                <Tag>{selectedOrder.category}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="环号">
                {selectedOrder.ring_number ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="描述">
                {selectedOrder.description}
              </Descriptions.Item>
              <Descriptions.Item label="指派给">
                {selectedOrder.assigned_to ?? '未指派'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(selectedOrder.created_at * 1000).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <Title level={5}>Timeline</Title>
            <Timeline
              items={[
                {
                  color: 'green',
                  children: (
                    <>
                      <Text strong>Created</Text>
                      <br />
                      <Text type="secondary">
                        {new Date(selectedOrder.created_at * 1000).toLocaleString()}
                      </Text>
                    </>
                  ),
                },
                ...(selectedOrder.assigned_at ? [{
                  color: 'blue',
                  children: (
                    <>
                      <Text strong>Assigned to {selectedOrder.assigned_to}</Text>
                      <br />
                      <Text type="secondary">
                        {new Date(selectedOrder.assigned_at * 1000).toLocaleString()}
                      </Text>
                    </>
                  ),
                }] : []),
                ...(selectedOrder.completed_at ? [{
                  color: 'green',
                  children: (
                    <>
                      <Text strong>Completed</Text>
                      <br />
                      <Text type="secondary">
                        {new Date(selectedOrder.completed_at * 1000).toLocaleString()}
                      </Text>
                      {selectedOrder.completion_notes && (
                        <>
                          <br />
                          <Text>Notes: {selectedOrder.completion_notes}</Text>
                        </>
                      )}
                    </>
                  ),
                }] : []),
              ]}
            />

            <Space style={{ marginTop: 24, width: '100%' }} direction="vertical">
              {selectedOrder.status === 'pending' && (
                <Button
                  type="primary"
                  block
                  onClick={() => setAssignModalOpen(true)}
                >
                  Assign Work Order
                </Button>
              )}
            </Space>
          </div>
        )}
      </Drawer>

      {/* Create Work Order Modal */}
      <Modal
        title="Create Work Order"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        okText="Create"
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateOrder}
        >
          <Form.Item
            name="title"
            label="Title"
            rules={[{ required: true, message: 'Please enter title' }]}
          >
            <Input placeholder="Work order title" />
          </Form.Item>
          <Form.Item
            name="description"
            label="Description"
            rules={[{ required: true, message: 'Please enter description' }]}
          >
            <TextArea rows={3} placeholder="Describe the work to be done" />
          </Form.Item>
          <Form.Item
            name="category"
            label="Category"
            rules={[{ required: true, message: 'Please select category' }]}
          >
            <Select placeholder="Select category">
              <Select.Option value="settlement">Settlement Issue</Select.Option>
              <Select.Option value="chamber_pressure">Chamber Pressure</Select.Option>
              <Select.Option value="torque">Torque Issue</Select.Option>
              <Select.Option value="alignment">Alignment Issue</Select.Option>
              <Select.Option value="maintenance">Maintenance</Select.Option>
              <Select.Option value="other">Other</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="priority"
            label="Priority"
            rules={[{ required: true, message: 'Please select priority' }]}
          >
            <Select placeholder="Select priority">
              <Select.Option value="critical">Critical</Select.Option>
              <Select.Option value="high">High</Select.Option>
              <Select.Option value="medium">Medium</Select.Option>
              <Select.Option value="low">Low</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="ring_number" label="Ring Number (optional)">
            <Input type="number" placeholder="Associated ring number" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Assign Work Order Modal */}
      <Modal
        title="Assign Work Order"
        open={assignModalOpen}
        onCancel={() => {
          setAssignModalOpen(false);
          assignForm.resetFields();
        }}
        onOk={() => assignForm.submit()}
        okText="Assign"
      >
        <Form
          form={assignForm}
          layout="vertical"
          onFinish={handleAssignOrder}
        >
          <Form.Item
            name="assigned_to"
            label="Assign To"
            rules={[{ required: true, message: 'Please select assignee' }]}
          >
            <Select placeholder="Select team member">
              <Select.Option value="engineer_1">Engineer 1</Select.Option>
              <Select.Option value="engineer_2">Engineer 2</Select.Option>
              <Select.Option value="supervisor">Supervisor</Select.Option>
              <Select.Option value="maintenance_team">Maintenance Team</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="notes" label="Notes">
            <TextArea rows={2} placeholder="Optional notes for the assignee" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default WorkOrders;
