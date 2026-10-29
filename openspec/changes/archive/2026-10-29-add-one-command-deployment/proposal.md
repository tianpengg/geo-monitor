# Proposal

## Why

管理员在 1Panel 上传源码后仍需手工创建配置、执行 Compose 和检查健康。需要一个可重复执行的 Shell 入口，减少首次部署操作并保留原有持久化与凭据边界。

## What Changes

- 新增 scripts/deploy.sh，交互收集 HTTPS 后台地址、管理员密码及端口，支持环境变量和非交互执行。
- 生成权限受限配置并校验，构建并启动现有 Compose，等待健康后输出 1Panel 反向代理及后续采集器步骤。
- 重复执行复用既有配置和数据卷，失败明确退出；采集器模式转交既有安装脚本。
- 更新运维、目录职责和 Linux 回归，验证首次部署、密码特殊字符、失败及重复执行。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `self-hosted-deployment`：新增控制台一条命令部署与采集器安装入口。

## Impact

影响 scripts、部署说明、测试及 CI；不改 HTTP API、数据库模型或采集协议，不增加根目录文件或生产依赖。1Panel 管理的域名证书、反向代理和官网日志配置由管理员按输出完成，脚本不修改现有站点。
