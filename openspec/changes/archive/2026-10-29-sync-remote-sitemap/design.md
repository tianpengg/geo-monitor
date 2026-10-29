# Design

## Context

见 proposal.md。inventory.py 已有路径标准化、事务导入及主机隔离，生命周期现有证据维护线程；crawler/fetch.py 的 HTTPS 获取专用于官方证据，不能为 Sitemap 放宽它的协议限制。

## Goals / Non-Goals

Goals：一次配置持续合并页面，在同步失败和并发配置变更下保持数据一致；保持网页请求与 AI 爬虫事件来源分开。

Non-Goals：多来源、页面主动抓取、robots 自动发现、跨站 Sitemap、任意端口、无限文件、历史删除与自动清理。

## Decisions

- 新增 services/sitemap.py 负责同站地址、固定公网 IP 下载及 XML/gzip 有界解析，services/sitemap_sync.py 负责配置和任务；保留 crawler/fetch.py 的证据安全边界，不增加 HTTP 客户端依赖。采用显式地址及单层索引，便于控制请求范围；不递归任意索引。
- 新迁移 sitemap_sources 以 site_id/host 唯一，保存 URL、enabled、revision、状态、尝试/成功/下次时间、结果计数、run_token 和租约。设置更新使旧 token 失效；任务完成前在同一事务确认当前主机、修订及 token，再合并目录和记录结果。
- GET /api/inventory/sitemap 查询；PUT 保存配置；POST /sync 排队。均使用现有管理员及 CSRF。后台单线程每 30 秒检查到期任务，API 唤醒线程；默认 24 小时重试间隔，运行租约 5 分钟，进程中断后过期恢复。单次任务处理限时 60 秒，连接/读取最多 5 秒，不阻塞 ASGI；DNS 仍受系统解析器超时影响。未启用配置不执行自动请求。
- 目录合并沿用最多 10000 页，远程结果保留已有标题；本地上传仍仅解析文件，不展开索引。表格删除不改变 Sitemap，下次同步可能重新加入，界面说明。
- Vue 在内容目录增加独立 Sitemap 卡片，复用 UiInput/UiSelect，保留手动导入；状态由 API 返回，按现有 30 秒刷新，退出及过时响应保护适用于新状态。保存及立即同步只确认排队，显示最后结果与时间。

## Risks / Trade-offs

- 合并会保留 Sitemap 已移除的路径 → 明示合并口径并保留手动移除；不自动把页面消失当作应删除。
- CMS 地址跳转或跨主机分发会被拒绝 → 提示填写当前官网主机的最终地址，不任意跟随跳转。
- 规模超过测试基线会明确失败 → 界面和文档列出上限，失败不提交部分结果。
- Docker 当前不可用 → 执行隔离单元/API、调度重启及浏览器验收，不标记容器或真实官网通过。

## Migration Plan

部署前备份 SQLite，启动按现有迁移追加新表，原目录和事件不动。新配置默认不存在，不发外部请求。回退须停服务并恢复备份及旧版本，避免较新 schema 被旧程序打开。
