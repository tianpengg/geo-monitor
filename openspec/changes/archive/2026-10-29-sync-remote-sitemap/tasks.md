# Tasks

## 1. 服务端

- [x] 1.1 实现同站 HTTP/HTTPS、固定公网地址、XML/index/gzip 与资源上限，补齐安全及解析回归并记录限制，通过相关 pytest。
- [x] 1.2 实现迁移、配置与排队 API、后台调度、原子合并及旧任务防护，补齐权限、失败、重启与并发回归，更新协议和运维说明，通过相关 pytest。

## 2. 管理界面

- [x] 2.1 增加 Sitemap 配置、自动及立即同步、真实状态与结果呈现，复用自定义控件和会话隔离；更新使用说明，通过前端回归与类型构建。

## 3. 集成验收

- [x] 3.1 完成受控浏览器成功与失败、保留目录、手机与迟到响应验证，执行 Python、前端、Ruff、构建与规范检查，更新 AGENTS、架构及验收记录，保留 Docker 与真实官网未验收边界。

## Workflow follow-up

- 同步 content-inventory 正式规范并归档；不改变 support-http-deployment 未完成状态。
