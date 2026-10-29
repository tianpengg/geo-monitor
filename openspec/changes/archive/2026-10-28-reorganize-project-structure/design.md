# Design

## Context

当前源代码采用 Python src 包与 Vue web 项目，根目录存在 data、dist、output 和多个工具缓存。App.vue 同时承担七个界面及请求调度；FastAPI app.py 包含全部路由与应用初始化。现有 API、数据库迁移、合成验收与下载包可作为回归基准。

## Goals / Non-Goals

**Goals:** 根目录职责清晰，产物集中；页面、公共控件与业务请求有明确位置，服务入口只组装；文档与工具实际可运行，原数据保留。

**Non-Goals:** 不改采集协议、统计、认证和界面流程，不引入 Vue Router、Pinia、ORM 或新生产依赖，不进行数据库模型重设计。

## Decisions

- 一级目录采用 cmd、internal、web、deploy、scripts、tests、docs、openspec。Python 包移到 internal，目录本身作为唯一 Python 包，直接包含各业务模块，所有导入统一为 internal.*。cmd/server/main.py 和 cmd/collector/main.py 为显式启动入口，已安装 CLI 名称保持兼容，模块入口调整为 python -m internal.server / internal.collector 并更新说明。保留 pyproject.toml、uv.lock、README、AGENTS 和标准隐藏配置。
- 本地产物集中到 .local/data、.local/build、.local/output、.local/cache 和 .local/playwright。移动前检查绝对路径在项目内、无目标冲突，记录文件摘要并逐一核对。标准 .venv 保持原位置，避免环境内绝对路径失效；web/dist 作为前端项目自身产物保留。
- 本地默认数据库为 .local/data/monitor.sqlite3；如仅旧 data/monitor.sqlite3 存在则兼容使用旧库。GEO_DATABASE 优先，Compose 仍指向 /app/data。采集器显式 /state 路径不变，本地缺省状态采用同类兼容回退。
- Vue 页面移至 views、外壳移至 layouts，基础控件与业务展示分别进入 components/ui、components/dashboard。会话、筛选和工作区编排通过 composables 分工；HTTP 与业务接口放 api，类型、纯辅助函数及样式分别放 types、utils、styles。保持页签和刷新契约，清理旧表单样式覆盖；格式化可审阅代码。
- 服务端模型进入 schemas，中间件进入 middleware，生命周期进入 lifecycle，认证和网站依赖进入 dependencies，API 以 APIRouter 按认证、网站、采集、分析和系统划分。已有业务算法归 services，连接迁移及事务仍由 storage 提供；不为目录层次机械创建数据访问抽象。
- 移动源码后同步全部活动引用、测试与 CI。下载包使用 internal、cmd、deploy、scripts 目录，安装后包内结构一致；历史归档不重写，在新说明提供路径对应关系。

## Risks / Trade-offs

- 相对路径变化可能影响容器与安装包：运行完整 Linux Docker / HTTPS 验收，验证停止、重连、恢复及新接口。
- 状态拆分可能破坏旧响应与退出保护：保留请求序号和重置规则，执行前端单测与真实浏览器登录、筛选、导航、配置、导入及会话回归。
- 本地数据可能正在使用：不强行移动被占用的数据库，不删除源文件；本次仅迁移确认可移动的工作区产物，默认路径兼容回退保护外部既有部署。
- 不把所有历史文档批量改写为新路径；当前使用说明以新路径为准，既往验收证据由映射说明定位。
