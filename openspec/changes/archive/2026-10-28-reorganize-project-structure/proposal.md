# Proposal

## Why

根目录混有数据、构建及验收产物；前端页面、状态与请求集中在 App.vue，服务端入口混入模型、认证与全部路由。需要整理实际代码及工具路径，避免每次增量开发继续堆积。

## What Changes

- 按确认的一级目录保留 cmd、internal、web、deploy、scripts、tests、docs、openspec；Python 包从 src/geo_monitor 移到 internal，直接包含业务模块，cmd 提供两个启动入口。
- 本地数据库、构建包、报告及工具缓存归入忽略的 .local；现有文件安全迁移并校验，保留标准隐藏环境及工具目录。
- Vue 拆分 layouts、views、components/ui、components/dashboard、composables、api、types、styles、utils，App 仅组装；保留页面与业务行为。
- FastAPI 拆分 API 路由、模型、依赖、中间件和生命周期，业务模块归入 services，入口只组装。
- 同步导入、安装包、Compose、Docker、CI、验证脚本及文档，运行数据库默认新路径并兼容旧路径及显式配置。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `self-hosted-deployment`：统一运维入口与本地产物路径，保持部署、安装包和数据兼容性。

## Impact

涉及 Python 服务端、Vue、运维及测试路径；HTTP API、数据模型、采集协议、生产卷路径和界面含义保持兼容。不引入业务框架或新生产依赖。不删除用户数据或既有验收历史。
