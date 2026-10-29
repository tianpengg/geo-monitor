# 参与贡献

欢迎提交问题、文档修正和 Pull Request。当前保持单管理员、单官网、单独日志来源的范围，功能与限制见 [README](README.md)。

## 提交问题

先搜索已有 Issue。报告问题请说明项目版本 / 提交、操作系统、Docker / Compose 版本、最小复现步骤、预期和实际结果，以及脱敏后的错误摘要。

不要上传 `.env`、采集凭据、Cookie、原始访问日志或数据库。日志样本用 `example.com`、`192.0.2.0/24`、`198.51.100.0/24`、`203.0.113.0/24`、`2001:db8::/32` 等文档保留地址构造，删除查询参数和个人信息。安全问题按 [SECURITY.md](SECURITY.md) 私密报告。

## 开发环境

需要 Python 3.13、uv 和 Node.js 24：

```sh
uv sync --frozen
npm --prefix web ci
```

后端终端设置管理员密码（至少 12 个字符）和开发地址，再执行 `uv run python cmd/server/main.py`。例如 Windows PowerShell 使用隐藏输入：

```powershell
$adminSecret = Read-Host '管理员密码（至少 12 位）' -AsSecureString
$env:GEO_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $adminSecret).Password
$env:GEO_PUBLIC_URL = 'http://127.0.0.1:5173'
$env:GEO_COOKIE_SECURE = 'false'
uv run python cmd/server/main.py
```

另开终端执行 `npm --prefix web run dev`，访问 `http://127.0.0.1:5173`。实际配置与测试产物放在被忽略的本地目录，不加入提交。

## 变更约定

先阅读 [AGENTS.md](AGENTS.md)、相关 `openspec/specs/` 和活动变更。新增功能与行为变化先写 OpenSpec 的提案、场景和任务，再实现；文档修正和恢复既有行为的局部缺陷修复可按项目约定直接处理。

Python 代码直接位于 `internal/`，显式入口放 `cmd/`，前端放 `web/`。保持采集器独立，只读访问日志；不要在错误或调试输出中记录原始请求、IP 或凭据。新增规则需提供官方依据，不能仅凭 UA 推定来源已核验或产品归属。

修改应围绕一个清晰问题，附适当回归与文档。提交 PR 时说明改了什么、为什么、验证结果和仍未验证的部分。许可按 [MIT](LICENSE)，新增第三方素材保留原许可与归属。

## 验证

按变更范围执行相关检查：

```sh
uv run ruff check internal cmd tests scripts
uv run pytest -q
npm --prefix web test
npm --prefix web run build
uv build --wheel --out-dir .local/build/python
openspec validate --all --strict
```

完整容器检查需要正常运行的 Linux Docker Engine / Compose 和镜像仓库网络：

```sh
uv run python scripts/container_smoke.py --full
uv run python scripts/container_smoke.py --full --protocol http
uv run python tests/deployment/deploy_script.py
```

仅在隔离环境执行，会创建临时容器 / 网络 / 数据卷。跳过或环境阻塞的项目必须明确标注，不能视为通过；合成数据不代表官网容量和零影响承诺。
