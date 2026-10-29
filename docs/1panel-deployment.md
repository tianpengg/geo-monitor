# 1Panel 部署与日志接入

控制台与采集器分别安装。控制台负责后台和数据保存；采集器在官网日志所在服务器只读采集并主动上报，可以与控制台同机或分机运行。以下 `192.0.2.10` 和 `example.com` 都是文档示例，运行前替换为实际后台地址和官网域名。

## 1. 检查环境

在 1Panel 的系统终端连接宿主机，执行：

```sh
docker --version
docker compose version
df -h /opt
free -h
docker system df
ss -lnt
```

Docker Engine 应正常运行，Compose 应支持 `docker compose`，端口 18018 应未被使用。首次源码构建会下载 Python、Node、uv 镜像和依赖；源码 ZIP 大小不能代表所需磁盘空间。记录可用空间及 CPU / 内存余量，资源不足先调整部署位置或扩容，不清理不明用途的主站文件、容器或卷。

若 `docker compose version` 提示没有此命令，先检查：

```sh
docker-compose version
command -v docker-compose
```

如果确认已经安装独立的 Compose v2，且返回路径确为 `/usr/bin/docker-compose`，可用 root 将它注册为 CLI 插件：

```sh
mkdir -p /usr/local/lib/docker/cli-plugins
ln -s /usr/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
```

使用实际返回的路径；如果目标已存在，先检查原因，不强制覆盖。此步骤不需要重启 Docker。未安装 Compose 时，按 [Docker 官方安装说明](https://docs.docker.com/compose/install/linux/) 单独安装适合当前系统的插件，不重装承载官网的 Docker。

## 2. 获取源码

有 Git 时：

```sh
cd /opt
git clone https://github.com/tianpengg/geo-monitor.git
cd geo-monitor
```

也可从仓库 Code → Download ZIP 下载，在 1Panel 文件管理中上传到 `/opt` 后解压，进入实际包含 `scripts/deploy.sh` 的源码目录。GitHub ZIP 顶层名称可能含分支名，不要假定解压后必然叫 `geo-monitor`，也不要覆盖既有项目。

宿主机无需安装 Python 或 Node.js。当前使用源码构建，不提供预构建镜像，项目没有内置公共镜像加速地址；镜像仓库和 npm / Python 包索引的网络需分别可达。

## 3. 部署控制台

在源码目录执行，先替换示例 IP：

```sh
bash scripts/deploy.sh --public-url http://192.0.2.10:18018 --port 18018
```

按提示设置并确认至少 12 字符的管理员密码，输入时不显示字符。默认账号 `admin`。脚本创建受限 `deploy/.env`，构建并启动控制台，检查健康后输出地址。数据库保存在独立卷。

在云安全组及已启用的主机防火墙中按实际访问来源放行 TCP 18018，通过实际后台地址登录。HTTP 不需要证书，但密码、会话、采集凭据和上报数据均未经传输加密。官网可以继续使用自身 HTTPS，与后台协议独立。

查看状态和脱敏后的错误摘要：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
docker compose --env-file deploy/.env -f deploy/compose.yaml logs --tail=80 monitor
curl -fsS http://127.0.0.1:18018/api/healthz
```

已有 `deploy/.env` 时执行 `bash scripts/deploy.sh`，复用配置与数据卷；不要继续带首次参数覆盖原配置。下载或构建失败按错误定位，保留配置和卷。

## 4. 保存官网并生成凭据

登录后台的“官网配置”页，填写官网域名（如 `example.com`，不含协议 / 端口 / 路径），选择统计时区（中国大陆通常 `Asia/Shanghai`），保存配置。

“日志中的 IP 是真实访问者吗？”先保持“还不确定”，除非已核实 CDN / 代理及真实 IP 还原规则。该模式继续采集和识别 UA，但不将不可确认的客户端地址用于官方来源确认。

在下方“安装采集器”生成采集凭据，保留当前页面；完整凭据只在生成后展示。它与管理员密码不同，重新生成会使旧凭据失效。

## 5. 安装采集器

复制页面生成的安装命令，在**官网服务器的宿主机系统终端**执行。不要在 OpenResty 容器终端执行，因为安装器需要访问宿主机 Docker 和日志目录。

按提示输入本站独立日志文件的宿主机绝对路径，以及隐藏输入的采集凭据。1Panel 的常见路径形式如下，必须在文件管理和 OpenResty 挂载中核实，不能直接照抄：

```text
/opt/1panel/apps/openresty/openresty/www/sites/example.com/log/access.log
```

OpenResty 配置里的 `/www/sites/example.com/log/access.log` 是容器内路径；宿主机路径取决于安装目录和挂载。不能使用包含多个官网请求的混合日志。项目支持标准 Combined 和 UA 后一个附加引号字段的 main；附加值会被忽略，不自动信任转发地址。

预检确认读取权限、格式和后台连接，通过后持续采集。安装器默认将配置保存到安装用户的 `$HOME/.local/share/geo-monitor-collector`，读取状态保存在独立 Docker 卷；日志目录只读挂载，默认 0.25 CPU / 128 MiB。构建和运行仍有资源开销，实际限额及官网影响需单独验收，不扩大日志权限或挂载整个主机来绕过隔离。

## 6. 验证数据链路

在“采集健康”确认最后心跳持续更新，访问一次官网，等待批量上报和分钟级看板刷新，确认最后收到日志时间前进，没有解析异常或已知缺口。

普通浏览器请求不会计为 AI 爬虫；首次启用从文件末尾开始，不自动导入历史。正常但没有匹配时应显示“未观察到可识别的 AI 爬虫访问”，断连时应显示异常。

如需测试分类，替换域名后仅执行一次：

```sh
curl --max-time 10 -sS -o /dev/null -w 'HTTP %{http_code}\n' \
  -A 'KimiBot/1.0 GeoMonitor-Installation-Test/1.0' \
  https://example.com/__geo_monitor_installation_test
```

200 或 404 均可产生访问日志。在访问明细搜索该路径，初始 KimiBot 规则启用时应出现对应身份。这是模拟 UA，只证明分类与采集链路，不应视为真正 Kimi 访问或来源已核验；会计入一次测试请求，请在验收记录中注明。

## 7. 停止、重连与补采

使用原安装用户，保留来源和状态卷：

```sh
collector_root="$HOME/.local/share/geo-monitor-collector"
bash "$collector_root/scripts/collector-control.sh" "$collector_root" check
bash "$collector_root/scripts/collector-control.sh" "$collector_root" stop
bash "$collector_root/scripts/collector-control.sh" "$collector_root" reconnect
```

补采依赖旧未压缩源文件仍保留；gzip 历史归档不参与补采。不删除状态或执行 `down -v`。完整故障 / OOM / 轮转测试应在隔离环境进行，官网低峰再做小范围验证。

仅停止控制台时，在源码目录执行：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml stop monitor
```

## 可选 HTTPS

准备独立后台域名及 DNS，部署时使用实际 HTTPS 地址和选择的上游端口。在 1Panel 为该后台域名配置有效证书与反向代理，目标通常为 `http://127.0.0.1:18018`；OpenResty 必须能从其网络访问上游。不要覆盖被监测官网的现有站点配置。

HTTPS 保持 Secure Cookie 和本机端口绑定，采集器继续校验证书。切换协议时同步调整地址、Cookie、绑定与端口，具体见 [运维说明](operations.md)。
