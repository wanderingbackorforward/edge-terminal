/**
 * Navigation Component (T195)
 * Main navigation menu for the application
 */
import React from 'react';
import { Menu, Badge } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  AlertOutlined,
  FileTextOutlined,
  AimOutlined,
  SettingOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';

interface NavigationProps {
  collapsed?: boolean;
  activeWarningCount?: number;
  pendingWorkOrderCount?: number;
}

type MenuItem = Required<MenuProps>['items'][number];

function getItem(
  label: React.ReactNode,
  key: React.Key,
  icon?: React.ReactNode,
  children?: MenuItem[],
): MenuItem {
  return {
    key,
    icon,
    children,
    label,
  } as MenuItem;
}

export const Navigation: React.FC<NavigationProps> = ({
  collapsed = false,
  activeWarningCount = 0,
  pendingWorkOrderCount = 0,
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems: MenuItem[] = [
    getItem('总览', '/', <DashboardOutlined />),
    getItem(
      <span>
        预警告警
        {activeWarningCount > 0 && (
          <Badge
            count={activeWarningCount}
            size="small"
            style={{ marginLeft: 8 }}
          />
        )}
      </span>,
      '/warnings',
      <AlertOutlined />
    ),
    getItem(
      <span>
        工单
        {pendingWorkOrderCount > 0 && (
          <Badge
            count={pendingWorkOrderCount}
            size="small"
            style={{ marginLeft: 8 }}
          />
        )}
      </span>,
      '/workorders',
      <FileTextOutlined />
    ),
    getItem('环信息', '/rings', <AimOutlined />),
    getItem('数据分析', '/analytics', <LineChartOutlined />, [
      getItem('轨迹分析', '/analytics/trajectory'),
      getItem('沉降趋势', '/analytics/settlement'),
      getItem('参数相关性', '/analytics/correlation'),
    ]),
    getItem('设置', '/settings', <SettingOutlined />),
  ];

  const handleMenuClick: MenuProps['onClick'] = (e) => {
    navigate(e.key);
  };

  // Determine active key from current path
  const getSelectedKeys = (): string[] => {
    const path = location.pathname;
    if (path === '/') return ['/'];

    // Check for exact match first
    const exactMatch = menuItems.find(item => item?.key === path);
    if (exactMatch) return [path];

    // Check for parent path match (for nested routes)
    if (path.startsWith('/analytics')) return ['/analytics'];
    if (path.startsWith('/rings')) return ['/rings'];
    if (path.startsWith('/workorders')) return ['/workorders'];
    if (path.startsWith('/warnings')) return ['/warnings'];

    return ['/'];
  };

  const getOpenKeys = (): string[] => {
    const path = location.pathname;
    if (path.startsWith('/analytics')) return ['/analytics'];
    return [];
  };

  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={getSelectedKeys()}
      defaultOpenKeys={collapsed ? [] : getOpenKeys()}
      items={menuItems}
      onClick={handleMenuClick}
      style={{ borderRight: 0 }}
    />
  );
};

export default Navigation;
