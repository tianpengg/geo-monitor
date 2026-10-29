# Proposal

## Why

用户已选定浅色靛蓝首页设计，希望重新绘制采集精灵和动画效果，通过可直接打开的 HTML 检查实际动效。需要将静态设计转为独立、可交互的演示，便于后续确认正式前端实现。

## What Changes

- 结合用户选定的浅色方向及后续确认的 Dub、OpenPanel 参考，重做首页卡片层级、统计、趋势、排行和最近访问。
- 重新绘制透明精灵素材，实现眨眼、悬浮、轨道扫描及状态切换，并提供放大、暂停和重播。
- 提供无联网依赖的独立 HTML，标注演示数据，支持键盘及减少动态效果偏好。
- 进行浏览器交互、响应式及视觉对照验证，记录验收结果。

## Capabilities

### New Capabilities

- `overview-motion-preview`：可离线打开、用于设计确认的首页交互动效预览。

### Modified Capabilities

无。既有业务、API、认证及实际采集口径不变。

## Impact

- 新增 `web/prototypes/overview-motion/`，保存 HTML、可复用原始素材、构建脚本及视觉验收记录。
- 更新 AGENTS.md 中的视觉设计授权及目录职责。
- 演示使用受控样本，不连接后台，不纳入 Vue 正式应用构建；用户已明确要求 HTML 预览。
