# Proposal

## Why

内容目录的 Sitemap 设置和文件上传长期占据首屏，覆盖统计与页面记录被推到下方。将低频管理操作收进弹窗，使日常浏览优先看到目录及观察覆盖。

## What Changes

- 主页面保留目录覆盖统计、筛选、表格和分页，增加紧凑的同步摘要及“Sitemap 配置”“手动导入”入口。
- Sitemap 配置和手动导入分别在弹窗完成，继续使用自定义控件、既有接口和校验。
- 保存或导入成功后关闭弹窗并刷新；失败在弹窗内提示且保留输入，取消不提交。补齐忙碌保护、焦点及手机操作。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `admin-dashboard-interface`: 内容目录的紧凑布局与配置、导入弹窗行为。

## Impact

影响 InventoryView、InventoryPanel、SitemapPanel、共用 UiDialog 的复用、上传辅助函数及分析样式；工作区操作返回明确成功结果并保持会话隔离。后端、数据库、Sitemap 调度和覆盖统计口径保持既有行为，无新依赖。
