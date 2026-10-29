# Design

## Context

见 proposal.md。`ServerConfig` 已接受 HTTP，Cookie 由环境设置；`CollectorConfig` 的 `allow_http` 已存在但说明仅限本地开发。当前部署脚本限制 HTTPS / 本机绑定，安装脚本只允许 HTTPS curl，Vue 安装命令未限定下载跳转协议。

## Goals / Non-Goals

Goals：从同一入口完成 HTTP 直连或 HTTPS 代理部署，按协议生成一致的配置；保持既有凭据、状态卷、去重和核验语义。

Non-Goals：自动安装 Docker、申请证书、修改 1Panel、防火墙或官网日志；不增加新数据源、数据库迁移及生产依赖。

## Decisions

- 以地址中的协议作为唯一选择，不增加容易与地址冲突的独立开关。交互提示支持两种地址；HTTP 默认绑定 `0.0.0.0`、Cookie false，HTTPS 继续 `127.0.0.1`、Cookie true。HTTP 地址未写端口时默认监听 80，写端口时默认使用该端口；显式 `--port` 可用于反向代理或端口转发。HTTPS 默认上游仍为 8000。
- 既有文件不自动迁移。校验支持 HTTP 对应 false Cookie，HTTPS 对应 true；HTTP 允许 IPv4 / IPv6 通配或本机绑定，HTTPS 保持本机绑定。修改地址、Cookie 和绑定后重跑仍使用原项目和卷。原配置冲突报错，不私自变更管理员密码。
- HTTP 安装写入 `allow_http: true`，HTTPS 写 false；保留手动配置的显式许可，删除仅开发环境的限制说明。curl 按初始协议设置 `--proto` 与 `--proto-redir`，HTTPS 不跳过证书验证、不降级。Vue 生成的安装脚本下载命令采用相同协议限制，凭据仍隐藏输入。
- 复用现有隔离 Linux 部署执行器，参数化 HTTP / HTTPS 控制台测试；扩展已有完整容器验收支持 HTTP 模式，并覆盖真实安装、追加、重传、重启、轮转和隐私检查。临时资源继续使用随机项目与卷，避免接入真实官网。

## Risks / Trade-offs

- HTTP 明文传输包括管理员密码、会话、采集凭据、核验前原始日志 → 安装输出和文档一次明确提示，不增加重复确认，选择 HTTPS 可加密传输。
- HTTP 开放主机端口 → 只开放所选后台端口，提示自行设置 1Panel / 云防火墙；不变更系统规则。
- 地址端口与主机映射不同 → 明确地址为实际访问入口，默认端口跟随 HTTP 地址，可显式覆盖以适应代理；容器健康不宣称公网已连通。

## Migration Plan

既有 HTTPS 文件原样继续部署。切换时手动同时更改地址、Cookie、绑定和端口，重跑同一入口保留数据，再重新生成采集配置；不删除读取状态。回退切换至 HTTPS 配置及有效代理证书，重新安装或更新采集配置后重连。
