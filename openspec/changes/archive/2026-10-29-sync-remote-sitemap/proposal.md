# Proposal

## Why

内容目录目前只能上传本地文件，官网更新后需要重复上传。管理员应能保存官网 Sitemap 地址，由服务端持续更新已知页面清单。

## What Changes

- 内容目录增加单一 Sitemap 地址、自动同步开关、立即同步和上次结果展示；保留本地导入。
- 保存后后台立即获取，启用时每 24 小时再次同步，重启后继续；支持 urlset、单层 sitemapindex 和 gzip。
- 同站合并、路径去重，保留手动标题及现有页面，不自动删除清单中消失的路径。失败保留目录，明确展示错误和最后成功时间。
- 抓取限制公网同官网主机的标准 HTTP/HTTPS 地址，拒绝重定向、内网及不完整或越界输入；不访问内容页面。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `content-inventory`: 增加远程 Sitemap 配置、受限抓取、后台调度和一致性场景，保留本地导入与覆盖口径。

## Impact

影响 inventory API、服务、生命周期、SQLite 迁移和 Vue 内容目录页；新增受限 Sitemap 获取及同步模块，无生产依赖。同步正式规范、AGENTS 和运维说明。Docker 恢复与真实官网验收沿用既有未验收边界。
