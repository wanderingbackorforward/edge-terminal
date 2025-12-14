/**
 * Settings Page
 * System configuration and preferences management
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Tabs,
  Form,
  Input,
  InputNumber,
  Switch,
  Select,
  Button,
  Table,
  Space,
  Tag,
  Modal,
  message,
  Divider,
  Typography,
  Row,
  Col,
  Statistic,
  Alert,
  Tooltip,
} from 'antd';
import {
  SettingOutlined,
  BellOutlined,
  TeamOutlined,
  ApiOutlined,
  SaveOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  MailOutlined,
  MobileOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

// Types
interface NotificationChannel {
  id: number;
  channel_type: string;
  channel_name: string;
  description?: string;
  is_enabled: boolean;
  last_test_result?: string;
  last_test_at?: string;
}

interface Personnel {
  id: number;
  employee_id: string;
  name: string;
  email?: string;
  phone?: string;
  role_name?: string;
  department?: string;
  is_active: boolean;
}

interface SystemStatus {
  mqtt_connected: boolean;
  cloud_connected: boolean;
  edge_connected: boolean;
  last_sync?: string;
}

// Mock data - in production, this would come from API
const mockChannels: NotificationChannel[] = [
  { id: 1, channel_type: 'email', channel_name: 'Primary Email', is_enabled: true, last_test_result: 'success' },
  { id: 2, channel_type: 'sms', channel_name: 'Emergency SMS', is_enabled: true, last_test_result: 'success' },
  { id: 3, channel_type: 'webhook', channel_name: 'Slack Webhook', is_enabled: false, last_test_result: 'failure' },
];

const mockPersonnel: Personnel[] = [
  { id: 1, employee_id: 'EMP001', name: '张三', email: 'zhang@example.com', phone: '13800138001', role_name: '项目经理', department: '工程部', is_active: true },
  { id: 2, employee_id: 'EMP002', name: '李四', email: 'li@example.com', phone: '13800138002', role_name: '技术工程师', department: '工程部', is_active: true },
  { id: 3, employee_id: 'EMP003', name: '王五', email: 'wang@example.com', phone: '13800138003', role_name: '操作员', department: '施工部', is_active: true },
];

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState('system');
  const [systemForm] = Form.useForm();
  const [notificationForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [channels, setChannels] = useState<NotificationChannel[]>(mockChannels);
  const [personnel, setPersonnel] = useState<Personnel[]>(mockPersonnel);
  const [channelModalVisible, setChannelModalVisible] = useState(false);
  const [editingChannel, setEditingChannel] = useState<NotificationChannel | null>(null);

  const [systemStatus] = useState<SystemStatus>({
    mqtt_connected: true,
    cloud_connected: true,
    edge_connected: true,
    last_sync: new Date().toISOString(),
  });

  // Initialize form values
  useEffect(() => {
    systemForm.setFieldsValue({
      mqtt_host: 'localhost',
      mqtt_port: 1883,
      cloud_api_url: 'http://localhost:8001',
      edge_api_url: 'http://localhost:8000',
      sync_interval: 300,
      auto_reconnect: true,
    });

    notificationForm.setFieldsValues({
      sound_enabled: true,
      desktop_notifications: true,
      alarm_sound: 'alarm',
      warning_sound: 'warning',
      quiet_hours_enabled: false,
      quiet_start: '22:00',
      quiet_end: '06:00',
    });
  }, [systemForm, notificationForm]);

  const handleSaveSystem = async () => {
    try {
      setLoading(true);
      await systemForm.validateFields();
      // In production: await api.saveSystemSettings(values);
      message.success('系统设置已保存');
    } catch (error) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNotifications = async () => {
    try {
      setLoading(true);
      await notificationForm.validateFields();
      message.success('通知设置已保存');
    } catch (error) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTestChannel = async (channelId: number) => {
    message.loading({ content: '正在测试连接...', key: 'test' });
    // Simulate test
    setTimeout(() => {
      message.success({ content: '连接测试成功', key: 'test' });
      setChannels(prev => prev.map(ch =>
        ch.id === channelId
          ? { ...ch, last_test_result: 'success', last_test_at: new Date().toISOString() }
          : ch
      ));
    }, 1500);
  };

  const handleToggleChannel = (channelId: number, enabled: boolean) => {
    setChannels(prev => prev.map(ch =>
      ch.id === channelId ? { ...ch, is_enabled: enabled } : ch
    ));
    message.success(enabled ? '通知渠道已启用' : '通知渠道已禁用');
  };

  const channelColumns: ColumnsType<NotificationChannel> = [
    {
      title: '渠道名称',
      dataIndex: 'channel_name',
      key: 'channel_name',
      render: (name, record) => (
        <Space>
          {record.channel_type === 'email' && <MailOutlined />}
          {record.channel_type === 'sms' && <MobileOutlined />}
          {record.channel_type === 'webhook' && <GlobalOutlined />}
          <span>{name}</span>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'channel_type',
      key: 'channel_type',
      render: (type) => (
        <Tag color={type === 'email' ? 'blue' : type === 'sms' ? 'green' : 'purple'}>
          {type.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleToggleChannel(record.id, checked)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      ),
    },
    {
      title: '测试结果',
      dataIndex: 'last_test_result',
      key: 'last_test_result',
      render: (result) => result ? (
        <Tag color={result === 'success' ? 'success' : 'error'}>
          {result === 'success' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          {' '}{result === 'success' ? '成功' : '失败'}
        </Tag>
      ) : <Text type="secondary">未测试</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<SyncOutlined />}
            onClick={() => handleTestChannel(record.id)}
          >
            测试
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingChannel(record);
              setChannelModalVisible(true);
            }}
          >
            编辑
          </Button>
        </Space>
      ),
    },
  ];

  const personnelColumns: ColumnsType<Personnel> = [
    {
      title: '工号',
      dataIndex: 'employee_id',
      key: 'employee_id',
    },
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '角色',
      dataIndex: 'role_name',
      key: 'role_name',
      render: (role) => <Tag color="blue">{role}</Tag>,
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '电话',
      dataIndex: 'phone',
      key: 'phone',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '在职' : '离职'}
        </Tag>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Title level={3}>
        <SettingOutlined /> 系统设置
      </Title>

      {/* System Status Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="MQTT 连接"
              value={systemStatus.mqtt_connected ? '已连接' : '断开'}
              valueStyle={{ color: systemStatus.mqtt_connected ? '#52c41a' : '#ff4d4f' }}
              prefix={systemStatus.mqtt_connected ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Cloud API"
              value={systemStatus.cloud_connected ? '已连接' : '断开'}
              valueStyle={{ color: systemStatus.cloud_connected ? '#52c41a' : '#ff4d4f' }}
              prefix={systemStatus.cloud_connected ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Edge API"
              value={systemStatus.edge_connected ? '已连接' : '断开'}
              valueStyle={{ color: systemStatus.edge_connected ? '#52c41a' : '#ff4d4f' }}
              prefix={systemStatus.edge_connected ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="最后同步"
              value={systemStatus.last_sync ? new Date(systemStatus.last_sync).toLocaleTimeString() : '-'}
              prefix={<SyncOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          {/* System Settings Tab */}
          <TabPane
            tab={<span><ApiOutlined /> 系统配置</span>}
            key="system"
          >
            <Form
              form={systemForm}
              layout="vertical"
              style={{ maxWidth: 600 }}
            >
              <Divider orientation="left">连接设置</Divider>

              <Row gutter={16}>
                <Col span={16}>
                  <Form.Item
                    name="mqtt_host"
                    label="MQTT 服务器地址"
                    rules={[{ required: true, message: '请输入 MQTT 地址' }]}
                  >
                    <Input placeholder="localhost" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="mqtt_port"
                    label="端口"
                    rules={[{ required: true, message: '请输入端口' }]}
                  >
                    <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="cloud_api_url"
                label="Cloud API 地址"
                rules={[{ required: true, message: '请输入 Cloud API 地址' }]}
              >
                <Input placeholder="http://localhost:8001" />
              </Form.Item>

              <Form.Item
                name="edge_api_url"
                label="Edge API 地址"
                rules={[{ required: true, message: '请输入 Edge API 地址' }]}
              >
                <Input placeholder="http://localhost:8000" />
              </Form.Item>

              <Divider orientation="left">同步设置</Divider>

              <Form.Item
                name="sync_interval"
                label="同步间隔 (秒)"
                rules={[{ required: true, message: '请输入同步间隔' }]}
              >
                <InputNumber min={60} max={3600} style={{ width: 200 }} />
              </Form.Item>

              <Form.Item
                name="auto_reconnect"
                label="自动重连"
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSaveSystem}
                  loading={loading}
                >
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </TabPane>

          {/* Notification Settings Tab */}
          <TabPane
            tab={<span><BellOutlined /> 通知设置</span>}
            key="notifications"
          >
            <Form
              form={notificationForm}
              layout="vertical"
              style={{ maxWidth: 600 }}
            >
              <Divider orientation="left">声音提醒</Divider>

              <Form.Item
                name="sound_enabled"
                label="启用声音提醒"
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="alarm_sound" label="ALARM 级别声音">
                    <Select>
                      <Select.Option value="alarm">紧急警报</Select.Option>
                      <Select.Option value="siren">警笛</Select.Option>
                      <Select.Option value="beep">蜂鸣</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="warning_sound" label="WARNING 级别声音">
                    <Select>
                      <Select.Option value="warning">警告提示</Select.Option>
                      <Select.Option value="chime">铃声</Select.Option>
                      <Select.Option value="beep">蜂鸣</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">桌面通知</Divider>

              <Form.Item
                name="desktop_notifications"
                label="启用桌面通知"
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Divider orientation="left">静默时段</Divider>

              <Form.Item
                name="quiet_hours_enabled"
                label="启用静默时段"
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="quiet_start" label="开始时间">
                    <Input placeholder="22:00" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="quiet_end" label="结束时间">
                    <Input placeholder="06:00" />
                  </Form.Item>
                </Col>
              </Row>

              <Alert
                message="静默时段内仅显示 ALARM 级别警告的声音提醒"
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />

              <Form.Item>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSaveNotifications}
                  loading={loading}
                >
                  保存设置
                </Button>
              </Form.Item>
            </Form>

            <Divider orientation="left">通知渠道管理</Divider>

            <div style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingChannel(null);
                  setChannelModalVisible(true);
                }}
              >
                添加渠道
              </Button>
            </div>

            <Table
              columns={channelColumns}
              dataSource={channels}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </TabPane>

          {/* Personnel Tab */}
          <TabPane
            tab={<span><TeamOutlined /> 人员管理</span>}
            key="personnel"
          >
            <Alert
              message="人员管理"
              description="在此查看项目人员信息。完整的人员和角色管理请通过 Cloud 管理后台进行。"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            <Table
              columns={personnelColumns}
              dataSource={personnel}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              size="small"
            />
          </TabPane>
        </Tabs>
      </Card>

      {/* Channel Edit Modal */}
      <Modal
        title={editingChannel ? '编辑通知渠道' : '添加通知渠道'}
        open={channelModalVisible}
        onCancel={() => setChannelModalVisible(false)}
        onOk={() => {
          setChannelModalVisible(false);
          message.success(editingChannel ? '渠道已更新' : '渠道已添加');
        }}
      >
        <Form layout="vertical">
          <Form.Item label="渠道类型" required>
            <Select defaultValue={editingChannel?.channel_type || 'email'}>
              <Select.Option value="email">Email</Select.Option>
              <Select.Option value="sms">SMS</Select.Option>
              <Select.Option value="webhook">Webhook</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="渠道名称" required>
            <Input defaultValue={editingChannel?.channel_name} placeholder="例如: 主邮箱通知" />
          </Form.Item>
          <Form.Item label="描述">
            <Input.TextArea defaultValue={editingChannel?.description} placeholder="渠道描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Settings;
