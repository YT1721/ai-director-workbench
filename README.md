# AI导演工作台 · AI Director Workbench

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Backend: FastAPI](https://img.shields.io/badge/backend-FastAPI%20%2B%20SQLModel-009688.svg)](./apps/api)
[![Frontend: React](https://img.shields.io/badge/frontend-React%20%2B%20Vite%20%2B%20TS-61dafb.svg)](./apps/web)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](./apps/api/requirements.txt)
[![Repo size](https://img.shields.io/github/repo-size/YT1721/ai-director-workbench.svg)](https://github.com/YT1721/ai-director-workbench)
[![Issues](https://img.shields.io/github/issues/YT1721/ai-director-workbench.svg)](https://github.com/YT1721/ai-director-workbench/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

**把「一段剧本」变成「可交付的多镜头 AI 短片生产线」，全程在本地跑，每一步都得你点头。**

A locally-run AI film pre-production workbench that turns a script into a ready-to-shoot multi-shot AI video pipeline — no cloud lock-in, every expensive call waits for your confirmation.

</div>

---

> **Screenshots** — 界面截图待补充，见 [`docs/screenshots/`](./docs/screenshots/)。有图才能让路过的人停留三秒，这是 TODO 里优先级最高的一项。

---

## 它解决什么问题

多镜头 AI 视频最容易崩的地方不是「生成一张好看的图」，而是**一致性**：同一个角色在第三镜里换了张脸、服装颜色变了、越过轴线后空间关系全乱。

这个项目把影视工业的流程约束搬进工具链，让每一次 AI 调用都落在可控结构里：

- **连续性锁** — 每段的起止状态被记录，续接只允许从已验收且有真实结束状态的 Take 出发
- **视频单元 15 秒硬上限** — 超过就必须拆，不做「一条长提示词蒙眼唐朝三百年」
- **人工闸门** — 文本分析、生图、视频提交全部逐次确认，系统绝不伪造 AI 结果

---

## 核心能力

| 模块                             | 做什么                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------ |
| **剧本导入**                     | 粘贴文本，或上传 TXT / MD / DOCX / XLSX；自动提取正文、字符数、行数                        |
| **导演分析**                     | 题材判断、人物关系、世界观规则、冲突与视觉方向                                             |
| **分镜规划**                     | 生成可编辑的 `EP01 / SC01 / SH001` 三层结构表                                              |
| **VP-PRECISION-18 提示词编译器** | 每个镜头输出完整 18 项导演级结构 + 秒级时间轴 + 可复制的自然语言版本                       |
| **故事板**                       | 白底高信息密度导演说明板，画面为黑白灰铅笔草稿；自动选择 3/4/6/9/12 格；可导出 HTML 与 PNG |
| **资产管理**                     | 人物母版、服装派生、场景设定板的版本管理、锁定与回滚；场次绑定与一致性检查                 |
| **批量视频包**                   | 慧梦 API / 即梦 CLI / 火山方舟 Seedance 2.5 三条通道；导出即梦逐镜生产包 ZIP               |
| **检查与修正**                   | 场级结构化检查报告，逐个问题独立生成修正记录，不用本地规则假装自动修好                     |
| **成本与预算**                   | 手工单价与按次 / 按秒预算计算，提交前强制确认                                              |

完整的功能清单、逐模块验收步骤与全部 API 端点见 **[使用与验收手册](./docs/使用与验收手册.md)**。

---

## 快速开始

**推荐方式（macOS）：** 双击项目根目录的

```text
启动AI导演工作台.command
```

它会自动创建 `.venv`、装好前后端依赖、从 `.env.example` 生成 `.env`（**不会**覆盖你已填好的密钥），随后启动服务并打开浏览器：

- 后端 <http://127.0.0.1:8000>
- 前端 <http://127.0.0.1:6001>

喜欢命令行就执行 `scripts/start-local.sh`。

**手动准备环境：**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web install
cp .env.example .env
```

**分别启动：**

```bash
# 终端 1：后端
source .venv/bin/activate
uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000

# 终端 2：前端
npm --prefix apps/web run dev -- --host 127.0.0.1 --port 6001
```

验证后端活着：

```bash
curl http://localhost:8000/health
```

> **只支持桌面端。** 建议浏览器窗口宽度 ≥ 1440px，没有移动端布局。

---

## 技术栈

| 层             | 选型                                                                               |
| -------------- | ---------------------------------------------------------------------------------- |
| 前端           | React + Vite + TypeScript + Tailwind CSS，9 个页面 / 24 个组件                     |
| 后端           | FastAPI + SQLModel + SQLite，60+ REST 端点                                         |
| AI 通道        | 慧梦（文本 / image-2 / Seedance 2.0 Fast）、OpenAI Responses API、本机即梦官方 CLI |
| 第三方知识模块 | 固定版本的 Seedance 2.0 Skill OS（MIT），见下方[第三方声明](#第三方声明)           |

```
AI- Director-Workbench/
├── apps/api/            FastAPI 后端（app/ + tests/ + migrations/）
├── apps/web/            React + Vite 前端
├── docs/                使用与验收手册、截图
├── scripts/             本地启动与 Skill OS 同步脚本
├── system-prompts/      V7 主系统提示词（业务规则的唯一来源）
├── third_party/         第三方许可证副本
└── vendor/seedance-20/  固定的第三方只读副本
```

---

## 第一次使用的最小闭环

不需要先配齐所有 AI 服务，系统允许空配置启动：**没有 API Key 也能建项目、导资料、搭结构**，只有真正要调模型时才要求配置。

1. 在「成本与设置 → AI 服务配置中心」填入慧梦或 OpenAI 配置（密钥只写进本机 `.env`）
2. 首页粘贴或上传剧本，创建项目
3. 「开始 / 规划」页只看顶部那张卡——**现在只做一件事**
4. 「用真实 AI 做导演分析」→「生成分镜规划」→「确认方案」→「确认分镜规划」
5. 进「分镜提示词」生成每镜的导演提示词
6. 进「故事板」生成黑白草稿
7. 要出片：进「资产」补人物/场景图 →「批量视频」建单镜队列 → 确认预算 → 提交

想先验收整条链路，首页点了「一键准备真实验收项目」会建一个短片示例——**它只创建项目和保存剧本，不伪造任何 AI 产出。**

---

## 安全边界

这是本项目最较真的地方，不是营销话术：

- **不谎报结果** — 不能用 API 时不会用占位数据冒充真实分析；PDF 与图片当前只保存不解析，页面会明确标注「已保存，暂未解析正文」
- **密钥只落本机** — 只读写本地 `.env`，页面只显示「是否已配置」，不显示密钥正文
- **逐次确认** — 真实文本、生图、视频提交每步都要手动点确认；默认不开放批量真实提交
- **即梦 CLI 通道** — 不保存账号、密码、Cookie、Token，不自动操作网页；登录态由官方 CLI 与系统钥匙串管理

---

## 测试

```bash
source .venv/bin/activate
pytest apps/api/tests
npm --prefix apps/web test
npm --prefix apps/web run build
```

提交前请通过 prettier 检查（仓库已配置 pre-commit 钩子）。

---

## 路线图

以下尚未实现，欢迎认领讨论：

- [ ] 真实批量视频提交
- [ ] Atlas Cloud `uploadMedia / generateVideo / prediction` 真实接入
- [ ] 其他聚合平台的专属 Adapter
- [ ] 批量故事板真实生图
- [ ] 截图与演示视频（**最缺这个，欢迎提 PR**）
- [ ] README 英文版

明确不做的：即梦网页自动操作。

---

## 第三方声明

本仓库在 `vendor/seedance-20/` 中固定集成第三方项目 [Seedance 2.0](https://github.com/Emily2040/seedance-2.0)（MIT License），固定提交 `57d01dc66f93ecb03c2475be5f22dc416d9b701d`，许可证副本见 [`third_party/seedance-20/LICENSE`](./third_party/seedance-20/LICENSE)，完整说明见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)。

该模块只作为按需加载的知识模块，**不会**覆盖 V7 主系统规则。其中的价格、模型 ID、接口字段不会自动成为生产配置——真实调用一律以你在应用内确认的配置为准。

---

## License

[MIT](./LICENSE) © 2026 Yang Tao
