# Proposal

## Why

用户明确取消首页动画人物，需要将采集健康区域改为清晰的纯数据卡片。

## What Changes

- 移除人物、轨道、扫描、放大预览及暂停重播入口，停止打包精灵素材。
- 用状态、链路检查、最后心跳、最后日志时间与异常指标填充健康卡；保留三种演示状态。
- 健康导航直接定位数据卡，更新预览说明和验收记录。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `overview-motion-preview`：取消人物动效，改为采集健康数据卡及对应导航、可访问性行为。

## Impact

仅修改现有独立 HTML 预览、构建脚本与说明，不修改业务接口、统计或正式 Vue 后台。
