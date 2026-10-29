# Proposal

## Why

一例真实 1Panel 站点 使用 OpenResty main 日志：标准 Combined 之后有一个带引号的附加字段。当前预检和解析均拒绝，导致无法在不更改主站配置的条件下接入。

## What Changes

- 严格兼容标准 Combined 后的一个可选带引号字段，预检和运行解析共用规则。
- 忽略附加字段，不推定代理信任、不作为客户端 IP，也不持久化其原文；保留原始 IP 仅在接收内存中核验的边界。
- 提供针对已核实 1Panel 路径的部署指引和不含本地环境 / 凭据的源码包；不操作真实主站或代替容器验收。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `incremental-log-collection`：增加明确的 Combined / main 格式兼容及附加字段忽略语义。

## Impact

修改 internal/logparse/__init__.py 的匹配规则，补充解析、预检和真实回环采集进程回归。无协议、数据库、依赖或主站变更；现有 HTTP 和采集隔离的真实容器待验任务保持不变。
