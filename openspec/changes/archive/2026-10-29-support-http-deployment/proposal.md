# Proposal

## Why

管理员希望无证书直接通过 HTTP 部署控制台并接收采集器上报。现有服务端和采集器已有底层 HTTP 能力，但部署入口、下载及安装流程仍强制 HTTPS，无法完成一键接入。

## What Changes

- 控制台一键入口接受 HTTP / HTTPS 地址，按协议设置 Cookie 与默认绑定；HTTP 可直接使用服务器 IP 和端口，HTTPS 保留现有本机代理方式。
- 采集器安装支持两种协议，HTTP 安装显式写入 `allow_http`；HTTPS 继续验证证书并禁止下载重定向降级。
- 保留密码隐藏输入、配置权限、重复执行不覆盖配置或数据、预检和健康确认。
- 文档说明 HTTP 明文传输范围及两种部署方式，验证 HTTP 端到端和 HTTPS 回归。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `self-hosted-deployment`: 可选传输协议、对应 Cookie 和端口配置、一键部署及明文说明。
- `collector-installation`: 按所选 HTTP / HTTPS 地址下载、安装并上报，保留 HTTPS 校验。

## Impact

涉及现有部署和采集器安装脚本、配置说明、采集器配置提示、前端安装命令、相关测试与 AGENTS。无新增生产依赖、数据库迁移、目录调整或原始日志持久化。
