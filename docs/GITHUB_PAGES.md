# GitHub 发布指南

## 仓库内容

仓库根目录应能直接看到 `README.md`、`frontend/`、`backend/`、`desktop/`、`.github/`。请保留隐藏文件。不要上传 `.env`、数据库、`node_modules`、虚拟环境、运行日志或本机安装包；这些内容已由 `.gitignore` 排除。

本项目源码仓库为 [wyyy5111/xunke](https://github.com/wyyy5111/xunke)，默认分支为 `main`。源码发布与 Pages 网站部署分别配置；上传源码后，可以按 README 在本地运行完整服务。

## 自动发布过程

`ci-and-pages.yml` 对推送、拉取请求及手动运行执行前端 lint、类型检查、单元测试、生产构建、后端测试和仓库检查。只有仓库变量 `ENABLE_PAGES` 为 `true`，且默认分支通过全部检查后，才构建 `showcase` 模式并发布。

Pages 构建仅打包 `frontend/dist/`。源码、Python 服务和桌面打包文件保留在仓库中，不进入网站部署包。构建时读取 Pages 的真实基础路径，无需在代码中硬编码用户名或仓库名。

第三方 Action 固定为完整提交 SHA，并标注版本。部署任务只获得 Pages 和 OIDC 所需权限；普通检查仅读取仓库。

## 首次启用

在 GitHub 仓库设置中选择 **Pages → Source → GitHub Actions**，再在 **Secrets and variables → Actions → Variables** 中添加仓库变量 `ENABLE_PAGES=true`。完成后重新运行工作流即可。未设置此变量时，源码检查照常执行，Pages 构建与部署跳过。GitHub Pages 的可用性取决于账户及仓库可见性；以 GitHub 设置页为准。

网站地址通常为 `https://<用户名>.github.io/<仓库名>/`，以部署结果为准。应用内部地址包含 `#/`，例如 `#/student/report/1`。

## 展示与完整运行的区别

| 能力 | Pages 展示 | 完整服务 |
| --- | --- | --- |
| 现有页面、角色导航、课程和图谱 | 保留 | 保留 |
| 预置讲义、报告、任务轨迹 | 浏览已有演示快照 | 读取当前业务数据 |
| 样例报告下载 | 下载静态样例 | 按业务数据导出 |
| 上传、生成、审核、修改、测评提交 | 明确提示需要完整服务 | 原功能正常执行 |
| 数据存储与鉴权 | 公开样例、浏览器角色会话 | FastAPI、数据库与 JWT |
| 模型调用 | 无 | 按本地服务配置调用 |

GitHub Pages 只托管静态文件，不执行 Python。后续如需在线执行完整业务，可单独部署原有后端，再使用默认生产构建；不要向静态网页写入模型密钥。

## 常见问题

- **找不到 Pages site**：先在仓库设置启用 Pages，并选择 GitHub Actions。
- **访问后出现 404**：使用部署结果中的完整地址，确认 `.github` 已上传，仓库根目录没有多套一层目录。
- **深层页面刷新**：使用本项目生成的 `#/...` 地址，不手工改成服务器路径。
- **生成或保存没有执行**：Pages 是只读展示。使用 `scripts/start_dev.sh` 或 Windows 启动脚本运行完整服务。
- **需要上传安装包**：使用 Releases 附件；原有 Windows 手动工作流可以生成待验证的安装包 artifact。

官方依据：[GitHub Pages 简介](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[配置发布源](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)、[Vite 静态部署](https://vite.dev/guide/static-deploy)。
