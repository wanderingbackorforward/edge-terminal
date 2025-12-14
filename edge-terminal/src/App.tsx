/**
 * Shield Tunneling ICP - Edge Terminal
 * 边缘端实时监控前端
 */
import React from 'react';
import { ConfigProvider, theme } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import zhCN from 'antd/locale/zh_CN';
import { Layout } from './components/layout';
import { Dashboard, Warnings, RingDetail, Settings, Analytics } from './pages';

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
            <Route path="rings" element={<RingDetail />} />
            <Route path="rings/:ringNumber" element={<RingDetail />} />
            <Route path="analytics/*" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
