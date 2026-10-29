# Design

## Context

项目已有生产 Compose、配置示例和交互式采集器安装脚本。控制台镜像有健康检查，使用固定 Compose 项目和 SQLite 卷；1Panel 管理的 OpenResty 可能使用 host 或 bridge 网络，项目没有面板管理 API 凭据。

## Goals / Non-Goals

**Goals:** 一条命令启动控制台，配置可复用，凭据受保护，失败可定位，并给出 1Panel 接入及采集器入口。

**Non-Goals:** 不自动安装 Docker，不自动操作 1Panel、签发证书或改写官网日志，不自动创建官网、轮换采集凭据或连接真实官网；不改变项目目录或生产依赖。

## Decisions

- scripts/deploy.sh 为唯一新运维入口，默认交互部署；支持 --non-interactive、--public-url、--port、--admin-user、--env-file。密码从隐藏终端或 GEO_ADMIN_PASSWORD 环境变量输入，不提供密码参数，脚本关闭命令追踪。
- 默认 deploy/.env，首次原子创建并设为 0600，既有常规文件只复用，拒绝符号链接。配置采用转义后的 dotenv 值，验证美元、引号及反斜杠保持原值；不 source 配置文件。写入后清除覆盖 Compose 的同名 shell 环境变量，以免重复部署意外更换凭据。
- Docker Compose 解析配置，经无网络临时 Python 容器校验 HTTPS、凭据范围、Secure Cookie 及本机映射，输出仅包含非敏感地址；无需宿主机 Python。随后使用现有 Compose 构建启动并等待健康；不执行 down 或删除卷，不输出完整配置和密码。
- --collector 模式校验 URL 和标识后转交 install-collector.sh，保持原交互、预检、HTTPS 和状态卷行为。
- 输出区分容器就绪与公网 HTTPS 接入，给出 1Panel 上游地址和网络条件、请求体设置、配置官网及安装采集器步骤；不声称证书或官网接入已经完成。

## Risks / Trade-offs

- dotenv 解析与 shell 字符转义不同：通过真实 Compose CLI 校验特殊字符，并以真实 Linux Docker 部署和再次部署验证密码与数据保留。
- 构建依赖网络：任何失败均保留配置和数据，返回非零并输出不含凭据的诊断命令。
- 管理员仍需在 1Panel 配置 HTTPS 和反向代理：这是明确的外部步骤，脚本不调用未经提供的面板接口或猜测配置路径。
- 自动化测试使用随机 Compose 项目、临时配置和数据卷；宿主工作区只读挂载，避免影响当前预览及用户容器，不保留新根目录产物。
