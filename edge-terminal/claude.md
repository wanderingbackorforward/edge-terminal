# Shield Tunneling ICP - Edge Terminal

## 当前目标
边缘端前端已分离为独立项目

## 开发进度

### Phase 1: 边缘端分离 ✅ 完成
- [x] GitHub 仓库已创建并推送
- [x] 移除 WorkOrders 相关代码
- [x] 精简 api.ts 移除 cloudApi
- [x] 更新路由和导航
- [x] 推送到 GitHub

### Phase 2: 云端前端 (待开始)
- [ ] 创建 cloud-console 项目

## 技术决策
- **架构**: 完全独立项目 (非 Monorepo)
- **技术栈**: Vite + React 18 + TypeScript + Antd 5 + ECharts
- **边缘端功能**: Dashboard, Warnings, RingDetail, Analytics, Settings
- **移除功能**: WorkOrders (移至云端)

## 命令参考
```bash
# 开发
cd edge-terminal && npm run dev

# 构建
npm run build

# 推送
git add . && git commit -m "message" && git push
```
