# 第三方许可与归属

项目自身代码采用根目录 [MIT License](LICENSE)。下列随源码分发的素材和工作流文件保留其原许可，项目许可不替代这些许可。

| 内容 | 来源及许可 | 许可文本 |
|---|---|---|
| Inter 字体 | [The Inter Project Authors](https://github.com/rsms/inter)，SIL Open Font License 1.1 | [正式前端](web/public/licenses/Inter.txt)、[独立预览](web/prototypes/overview-motion/assets/Inter-LICENSE.txt) |
| Tabler 图标 | [Paweł Kuna / Tabler Icons](https://github.com/tabler/tabler-icons)，MIT | [正式前端](web/public/licenses/Tabler.txt)、[独立预览](web/prototypes/overview-motion/assets/tabler-LICENSE.txt) |
| OpenSpec 生成的工作流技能 | [OpenSpec](https://github.com/Fission-AI/OpenSpec)，技能文件标注 MIT，保留原始元数据 | [许可文本](.agents/LICENSE-OpenSpec)、[工作流文件](.agents/skills/) |

正式前端的字体和图标许可随 `web/public/licenses/` 构建进入静态资源，部署时继续提供。其他 Python / JavaScript 依赖未直接复制入源码仓库，安装和分发时仍须遵守其各自许可；依赖清单及精确版本见 `pyproject.toml` / `uv.lock` 和 `web/package.json` / `web/package-lock.json`。

界面设计参考 [Dub Analytics](https://dub.co/analytics) 与 [OpenPanel](https://openpanel.dev/) 的视觉和信息组织；界面由本项目实现，不包含其业务源码。爬虫运营方、品牌和服务名称仅用于身份说明，不代表官方关联、合作或背书。
