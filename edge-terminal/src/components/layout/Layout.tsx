/**
 * Main Layout Component (T194)
 * Application layout with header, sidebar, and content area
 */
import React, { useState, useEffect } from 'react';
import { Layout as AntLayout, Typography, Space, Badge, Avatar, Dropdown, Button, Tooltip } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BellOutlined,
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
  SyncOutlined,
  WifiOutlined,
  DisconnectOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate } from 'react-router-dom';
import type { MenuProps } from 'antd';
import { Navigation } from './Navigation';
import { useRealTimeData } from '../../hooks';

const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;

export const Layout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  // Get real-time data for counts
  const { activeWarnings, connected, lastUpdate } = useRealTimeData();

  // Calculate active warning count
  const activeWarningCount = activeWarnings.filter(w => w.status === 'active').length;
  const pendingWorkOrderCount = 0; // TODO: Get from work order hook

  // Connection status
  const isConnected = connected;

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
      onClick: () => navigate('/settings'),
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      {/* Sidebar */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={240}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 16px',
            borderBottom: '1px solid #303030',
          }}
        >
          {collapsed ? (
            <Text strong style={{ color: '#1890ff', fontSize: 20 }}>盾</Text>
          ) : (
            <Space>
              <Text strong style={{ color: '#1890ff', fontSize: 18 }}>盾构智能</Text>
              <Text style={{ color: '#8c8c8c', fontSize: 14 }}>监控终端</Text>
            </Space>
          )}
        </div>

        {/* Navigation Menu */}
        <Navigation
          collapsed={collapsed}
          activeWarningCount={activeWarningCount}
          pendingWorkOrderCount={pendingWorkOrderCount}
        />
      </Sider>

      {/* Main Layout */}
      <AntLayout style={{ marginLeft: collapsed ? 80 : 240, transition: 'margin-left 0.2s' }}>
        {/* Header */}
        <Header
          style={{
            padding: '0 24px',
            background: '#1f1f1f',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #303030',
            position: 'sticky',
            top: 0,
            zIndex: 99,
          }}
        >
          {/* Left side - collapse button and breadcrumb */}
          <Space>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, width: 48, height: 48 }}
            />
          </Space>

          {/* Right side - status indicators and user menu */}
          <Space size="middle">
            {/* Connection Status */}
            <Tooltip title={isConnected ? '已连接' : '未连接'}>
              <Badge status={isConnected ? 'success' : 'error'}>
                {isConnected ? (
                  <WifiOutlined style={{ fontSize: 18, color: '#52c41a' }} />
                ) : (
                  <DisconnectOutlined style={{ fontSize: 18, color: '#ff4d4f' }} />
                )}
              </Badge>
            </Tooltip>

            {/* Last Update Time */}
            {lastUpdate > 0 && (
            <Tooltip title="最近数据刷新">
              <Space size={4}>
                <SyncOutlined style={{ color: '#8c8c8c' }} />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {new Date(lastUpdate).toLocaleTimeString()}
                  </Text>
                </Space>
              </Tooltip>
            )}

            {/* Notification Bell */}
            <Tooltip title="预警通知">
              <Badge count={activeWarningCount} size="small">
                <Button
                  type="text"
                  icon={<BellOutlined style={{ fontSize: 18 }} />}
                  onClick={() => navigate('/warnings')}
                />
              </Badge>
            </Tooltip>

            {/* User Menu */}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
                <Text>Admin</Text>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        {/* Content Area */}
        <Content
          style={{
            margin: 24,
            minHeight: 'calc(100vh - 64px - 48px)',
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;
