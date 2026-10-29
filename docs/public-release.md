# 首次开源发布检查

日期：2026-10-29。目标：公开仓库 `tianpengg/geo-monitor`，初始版本 0.1.0，MIT 许可证。

## 公开内容

- README 面向使用者介绍功能、数据流、HTTP / HTTPS 部署、采集器安装和识别边界。
- 增加项目许可、第三方许可说明、贡献与安全反馈说明，以及 Issue / PR 模板。
- 通用 1Panel 指引使用文档保留地址和示例域名，真实部署操作说明保留在被忽略的本地目录；公开审查记录不包含实际服务器明细。
- Git 忽略配置、数据库、状态、密钥、本机环境和测试产物；首次提交前检查全部索引文件。测试夹具是合成数据。
- 许可证随镜像构建、Python wheel 和采集器下载包保留；保留原有 Inter / Tabler 许可。

## 验证口径

首次发布时，完整 Python 为 223 passed / 36 skipped，前端最近记录为 35 项通过。维护者反馈 HTTP 实际部署及基础采集展示正常，工具当时未独立复验真实后台；该反馈不构成完整故障矩阵、实际资源限额、OOM 或官网性能验收。两个既有活动变更当时保留未验任务，后续收口见文末。

本次发布的实际验证：

| 检查 | 结果 |
|---|---|
| 许可下载包、部署基础与夹具相关 Python 回归 | 17 项通过；沿用一条 Starlette / httpx 弃用提醒 |
| 前端回归、类型与生产构建 | 35 项通过，类型与构建通过 |
| Ruff、uv 锁文件及严格 OpenSpec | 通过；npm 清单与锁文件一致 |
| Python wheel | SPDX 为 MIT，License-File 正确，包内许可与根 LICENSE 逐字一致 |
| 前端第三方许可 | 构建后 Inter / Tabler 许可与源文件一致 |
| 公开入口文档本地链接 | 全部可解析 |
| 待发布文件预检查 | 346 个候选文件；未发现已知私人地址 / 路径或令牌模式，运行数据与私人说明被忽略 |
| 镜像许可 | 直接检查两个 Dockerfile 的 LICENSE 复制输入；本轮未启动实际构建或容器 |

本次只调整说明与许可分发，未重跑完整 Python / 容器故障矩阵，不将 GitHub 初次上传视为测试通过。

## GitHub 状态

公开仓库 [tianpengg/geo-monitor](https://github.com/tianpengg/geo-monitor) 已创建并推送至 main，首次提交为 `caba3da76c70d431d30e670aac0ff1e76ac9fc0c`。采用 GitHub noreply 邮箱；匿名 API 已确认公开可读，远程提交与本地一致，README / LICENSE 内容与提交一致，GitHub 识别为 MIT。仓库配置了描述、主题并开启私密漏洞报告入口，尚未生成正式 Release 或预构建镜像。

首次索引检查共 346 个文件，约 2.44 MB，未发现运行目录、实际配置或已知私人内容模式，Shell 脚本均为 LF。[首次 GitHub Actions 检查](https://github.com/tianpengg/geo-monitor/actions/runs/40856262530) 已全部成功：Linux Python 257 passed / 2 skipped，前端、Ruff、wheel、Bash 语法、HTTP / HTTPS 各 8 组完整矩阵及独立部署执行器 36 项均通过。两种 Python 运行计数有重叠，不累计为唯一用例数。收口依据见 [双协议验收记录](http-deployment-verification.md)。

`prepare-public-release` 三项任务完成，许可交付规范已同步至正式 `self-hosted-deployment` 并归档。后续归档提交仅涉及说明和规范，以 `[skip ci]` 避免重复构建；源码和发布配置对应的首次检查已完成，状态以上述运行链接为准。

后续 [CI 40895324515](https://github.com/tianpengg/geo-monitor/actions/runs/40895324515) 的 267 项 Python / 2 跳过、独立部署 36 项、前端及两协议各 9 组矩阵全部通过，新增了实际 cgroup、CPU 节流、写入拒绝、真实 OOM 和独立合成源站持续服务证据；两份 Artifact 已下载并核对摘要。维护者另提供了官网只读短窗口观测，见 [低干扰验收](collector-isolation-verification.md)。两项收口完成后以验证分支同步 main，后续只涉及说明和归档的提交不重复运行同一套故障测试。

最终收口检查确认运行代码、部署入口、测试及 CI 配置与上述通过的提交一致；24 个说明 / 规范文件、39 个本地链接和 350 个公开候选文件检查通过，12 组正式规范严格校验通过，两个变更均已归档。归档提交使用 `[skip ci]`，对应测试结果引用已通过的验证提交，不把跳过的新运行标为执行成功。
