/**
 * Shield Tunneling ICP Terminal (T193)
 * Main Application Entry Point with React Router
 */
import React from 'react';
import { ConfigProvider, theme } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import zhCN from 'antd/locale/zh_CN';
import { Layout } from './components/layout';
import { Dashboard, Warnings, RingDetail, WorkOrders, Settings } from './pages';
import Analytics from './pages/Analytics';

// Dark theme configuration
const darkThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#1890ff',
    colorBgContainer: '#1f1f1f',
    colorBgElevated: '#262626',
    colorBorder: '#303030',
    colorText: '#d9d9d9',
    colorTextSecondary: '#8c8c8c',
    borderRadius: 6,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Card: {
      colorBgContainer: '#1f1f1f',
    },
    Table: {
      colorBgContainer: '#1f1f1f',
      headerBg: '#262626',
    },
    Layout: {
      bodyBg: '#141414',
      headerBg: '#1f1f1f',
      siderBg: '#1f1f1f',
    },
  },
};

const App: React.FC = () => {
  return (
    <ConfigProvider theme={darkThemeConfig} locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="warnings" element={<Warnings />} />
            <Route path="workorders" element={<WorkOrders />} />
            <Route path="rings" element={<RingDetail />} />
            <Route path="rings/:ringNumber" element={<RingDetail />} />
            <Route path="settings" element={<Settings />} />
            <Route path="analytics/*" element={<Analytics />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
