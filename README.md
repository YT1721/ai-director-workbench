# AI导演工作台

本项目是本地运行的 AI 影视前期制作工作台。当前已同步升级为 **V7.0 Plus R1｜Seedance Skill OS 融合增强版**。V7 主系统仍是唯一业务规则来源；固定版本的 Seedance 2.0 Skill OS 只提供按需加载的导演知识、提示词编译、连续性和审片能力，不会整体塞入系统提示词，也不会覆盖 UCODE-9、FLOW-NAV、VP-PRECISION-18、DIRECTOR-TECH PLUS、UNIFIED-SB 或图片风格锁。所有真实请求都必须由用户明确确认。

## 当前已完成

- Seedance 2.0 Skill OS 固定在提交 `57d01dc66f93ecb03c2475be5f22dc416d9b701d`
- 第三方只读副本位于 `vendor/seedance-20/`，`.agents/skills/seedance-20` 指向该固定副本
- `SeedanceSkillAdapter` 按任务读取所需知识模块，不把整个第三方仓库注入 V7 系统提示词
- Directing Engine 保存场级导演意图、Canon、连续性锁和不可转移约束
- Prompt Compiler 保留 VP-PRECISION-18 全部 18 项，并分别生成可审计的 `vp_prompt_full` 与自然语言 `vp_prompt_copy`
- Project State 记录已完成、当前与后续保留的 Video Unit，三组 ID 互不重叠
- Reference Role Map 明确每张参考图承担的人物、服装、场景、首帧或连续性职责
- Event Density 与 Allocation Model 记录本单元主要投入、次要投入、省略项与拆分建议
- Continuation Handoff 只允许从已验收且有真实结束状态的 Take 续接；被拒绝 Take 不得成为下一单元来源
- 首尾帧提取、Take Review 和 Surface Profile 已进入服务层与数据库；单个 Video Unit 硬限制不超过 15 秒
- 设置页显示 Skill OS 固定版本、模块数与许可证状态，不显示第三方全文或把上游价格当生产配置

- React + Vite + TypeScript + Tailwind CSS 前端
- FastAPI + SQLModel + SQLite 后端
- `GET /health` 健康检查
- `GET /api/system-prompt/status` 系统规则载入状态
- 首页 9 个 UCODE-9 动作入口
- 首页资料优先创作向导：粘贴剧本 / 上传 TXT、MD、PDF、DOCX、XLSX 或分镜图片
- 首页与全部项目页面共用 FLOW-NAV 状态看板：当前状态、完整调用目录和下一步建议
- 开始 / 规划页升级为“下一步操作台”：第一屏只显示当前最该做的一件事
- FLOW-NAV 顶部看板默认折叠为轻量提示，可展开查看完整调用目录
- 左侧导航作为流程状态导航：已完成、当前建议、阻塞 / 缺失、待进行、可选辅助使用不同颜色提示
- 项目树、素材清单和 UCODE 命令记录收纳到“高级区”，避免新手一进入页面就被工程结构干扰
- TXT / MD / DOCX / XLSX / 粘贴文本正文提取：保存提取正文、字符数、行数和预览
- 真实文本大脑启动分析：根据可解析文本生成题材判断、人物关系、世界观规则、冲突与视觉方向
- 真实文本大脑分镜规划表：生成可编辑的 `EP01 / SC / SH` 分镜表
- 分镜规划人工确认：只有用户点击“确认分镜规划”才写入项目结构
- 人工导演方案确认闸门：不伪造 AI 导演方案
- 左侧简化导航
- 服务通道 Adapter 目录预留
- 项目创建、打开、编辑、归档与恢复
- 自动生成 `EP01 / SC01 / SH001`
- 集、场、镜头新增、重命名、归档与恢复
- 项目本地目录自动建立
- 剧本与参考图片上传保存
- UCODE-9 高级手动记录区、历史记录与待确认检查点
- 人物母版、服装派生和场景设定板版本管理；正式资产使用慧梦 image-2 逐次确认生图，旧调试备用图默认隐藏
- 资产版本确认、锁定与回滚
- 场次人物绑定和一致性检查记录
- 正式故事板统一风格锁：白底/浅灰底高信息密度导演故事板说明板风格，镜头画面保持黑白灰铅笔草稿，功能标注使用统一色彩规则
- 场级 Axis 计划：主轴线、安全机位侧、人物站位、视线、运动方向和跨轴过渡
- 统一故事板版本：正式画面使用慧梦 image-2 逐次确认生图，自动选择 `3 / 4 / 6 / 9 / 12` 格
- 故事板保存格数原因、对应分镜提示词时间段、功能标注层和 UNIFIED-SB 元数据
- 程序动态合成 Storyboard Execution Page HTML 预览
- 页级故事板 PNG 导出
- 双阶段视频提示词：故事板参考提示词 → 绑定故事板 → 最终视频提示词
- 分镜提示词：保留完整导演级 18 项结构、秒级时间轴、可复制提示词，以及 DIRECTOR-TECH PLUS 的特写进连接器、细节插入、蒙太奇、物体隐喻和镜头意义链
- 统一视频请求和服务能力校验
- 慧梦真实单镜队列、预算确认、提交 / 查询 / 下载；旧开发状态演练已从正式流程停用
- 通用聚合服务通道配置保存与本地验证
- 即梦逐镜生产包 ZIP 导出和 MP4 / MOV 结果导入；导出包包含 `vp_precision_18.json`、`director_technique.json`、`meaning_chain.json`、`storyboard_grid.json` 和 `unified_sb_meta.json`
- 场级结构化检查报告：资产、人物一致性、故事板、轴线、视频包、服务通道与预算闸门
- 多选问题修正：每个问题独立创建修正记录和处理指引，不自动用本地规则生成正式版本
- 本地一键推进：按资产、故事板、视频包和批量队列顺序检查，遇到人工闸门立即暂停
- OpenAI Responses API 最小接入：仅允许逐次确认的检查报告中文摘要
- 受控文本大模型分析：文字主流程使用慧梦 GPT-5.5 或 OpenAI 官方文本通道
- 开始、规划、资产、故事板和检查摘要均可生成真实文本结果；视频包可由真实文本大脑生成并落库 VP-PRECISION-18 的 18 项结构版本；真实文本请求必须逐次确认
- 慧梦 image-2 受控故事板生图：仅当前镜头、页面逐次确认、提交 / 查询 / 下载分步执行，下载后保存为新的故事板版本，不覆盖旧版本
- 摘要缓存与成本记录
- 第三方视频服务通道的官方文档、价格来源、模型 ID 和字段映射登记（开发工具默认隐藏）
- 服务通道本地接入预检：只检查配置与环境变量是否存在，不读取密钥（开发工具默认隐藏）
- Canonical Video Request 脱敏映射预览和预览快照
- 服务响应样例本地演练：支持点路径字段、状态归一化和缺失映射提示，样例不保存（开发工具默认隐藏）
- 手工单价预算计算：支持按次和按秒配置
- 待提交队列本地重映射：切换服务通道后重新检查能力和预算，不修改资产、故事板或视频提示词历史版本
- Atlas Cloud 禁用状态模板：登记当前文档中的任务 Endpoint、Bearer 鉴权、Seedance 2.0 Fast Reference 模型、响应字段和按秒预算（开发工具默认隐藏）
- 慧梦 API 受控真实单镜测试：只允许 1 个任务、1-15 秒、720p、页面逐次确认；建议先用 5 秒小样，不开放真实批量提交
- Milestone 6A 真实单镜验收向导：设置页显示配置步骤，批量视频页展示每个提交闸门
- AI 服务配置中心：支持一个供应商账号下分别配置文本主脑、图像生成和视频生成模型；密钥仍只写入本机 `.env`
- 即梦 CLI 账号积分通道：检测本机 `dreamina` 是否安装和登录，受控提交 / 查询 / 下载单镜视频并绑定 Shot ID；不登录网页、不保存账号密码或 Token

当前默认体验是“真实 AI 生成，逐次确认”。系统不会生成占位分析来冒充正式结果；文本分析需要同时满足：`ENABLE_REAL_TEXT_ANALYSIS=true`、`TEXT_PROVIDER_MODE=huimeng_chat` 或 `openai_responses`、对应 API Key 与文本模型已配置、并在任务页点击确认。真实文本分析只生成导演分析、分镜规划、资产文字设定、故事板文字拆解、分镜提示词和检查摘要，不提交视频。

首页提供“真实跑通检查”看板，会按阶段检查文本大脑、真实生图、真实视频和当前项目步骤。系统不会一开始就要求你配齐所有服务：先跑文本大脑；进入资产或故事板时再检查 image-2；进入批量视频时再检查 Seedance。

如果只是想验收整套链路，首页提供“一键准备真实验收项目”。它只会创建一个短片项目、保存一段示例剧本并提取正文，不会伪造导演分析、分镜规划、故事板、分镜提示词或视频结果。准备完成后，请从“用真实 AI 分析”开始逐步确认。

正式创作必须先到“成本与设置”配置真实文本 AI，之后每次文字生成都会在任务页逐次确认。故事板允许先生成黑白草稿；真实故事板生图只开放慧梦 image-2 的单镜头受控链路，并且必须开启 `IMAGE_REAL_SUBMIT_ENABLED=true`、配置 Key、在故事板页逐次确认。即梦网页自动操作仍未开放；即梦只通过本机官方 CLI 账号积分通道提交受控单镜任务。真实视频网络提交继续受硬闸门限制。旧视频状态演练接口已停用，不再作为正式或开发流程入口。

慧梦/绘梦配置按三种能力分开：文本主脑 `HUIMENGI_TEXT_MODEL=gpt-5.5`，生图 `HUIMENGI_IMAGE_MODEL=image-2`，视频 `HUIMENGI_VIDEO_MODEL=seedance-2.0-fast`。同一个 `HUIMENGI_API_KEY` 可以共用，但模型名必须分别填写。真实视频测试必须同时满足：本地 `.env` 或设置页中 `SEEDANCE_REAL_SUBMIT_ENABLED=true`、`VIDEO_PROVIDER_MODE=huimeng_live`、`HUIMENGI_API_KEY` 已配置、页面点击确认、队列只有 1 个镜头、任务为 `5s / 720p`、预算已确认。否则后端拒绝发送网络请求。

文本解析说明：当前解析粘贴文本、TXT、MD、DOCX 和 XLSX。PDF、图片和分镜表图片会保存到本地，但页面会标注“已保存，暂未解析正文”，不会伪造解析结果。

Atlas Cloud 和通用聚合平台配置属于开发接入工具，默认不显示在正式界面；只有设置 `VITE_SHOW_DEV_TOOLS=true` 后才会出现。正式用户当前只需要在“成本与设置 → AI 大脑与服务配置中心”配置慧梦或 OpenAI。

## 页面尺寸

当前工作台只面向桌面端使用，不提供移动端布局。

- 建议浏览器窗口宽度：`1440px` 或更大
- 左侧导航固定宽度：`236px`
- 所有页面使用统一内容画布、内边距和桌面栅格
- 窗口小于 `1440px` 时保留桌面布局，可横向滚动查看

## 第一次安装

如果你想手动准备环境，可以在项目根目录依次执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web install
cp .env.example .env
```

## 日常一键启动

推荐方式：直接双击项目根目录里的：

```text
启动AI导演工作台.command
```

它会自动检查并准备本地环境：

- 第一次运行会自动创建 `.venv`
- 自动安装后端 Python 依赖
- 自动安装前端 npm 依赖
- 如果没有 `.env`，会从 `.env.example` 创建一份
- 不会覆盖你已经填写过的 `.env` 密钥

准备完成后会自动启动：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:6001`

并自动打开浏览器。保持弹出的终端窗口打开即可使用；关闭窗口会停止本地服务。日志保存在 `.local-run/logs/`。

如果提示端口 `8000` 或 `6001` 已被占用，通常说明应用已经启动过，直接打开 `http://127.0.0.1:6001` 即可；如果打不开，再关闭占用端口的程序后重新双击启动。

如果你更喜欢命令行，也可以执行：

```bash
scripts/start-local.sh
```

## 手动启动后端

打开一个终端，在项目根目录执行：

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

验证后端：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/system-prompt/status
```

## 手动启动前端

再打开一个终端，在项目根目录执行：

```bash
npm --prefix apps/web run dev -- --host 127.0.0.1 --port 6001
```

浏览器打开：

```text
http://localhost:6001
```

## 新手第一步怎么用

现在的推荐流程不是先理解项目树，而是按创作向导走：

1. 打开 `http://localhost:6001`。
2. 如果只是想快速验收，点击首页“真实跑通检查”里的“一键准备真实验收项目”；它只创建项目、保存示例剧本并提取正文，不会伪造 AI 产出。
3. 如果要用自己的内容，在首页填写项目名称，粘贴剧本 / 分镜文本，或上传 TXT / MD / DOCX / XLSX。
4. 点击“创建项目并保存资料”；如果使用了“一键准备真实验收项目”，系统会自动进入下一步。
5. 进入“开始 / 规划”后，只看页面顶部的“现在只做一件事”。
6. 如果页面提示“用 AI 做导演分析”，确认本次文字请求后生成导演启动分析。
7. 如果页面提示“生成分镜规划”，确认后生成可编辑的 `EP / SC / SH` 分镜表。
8. 如果页面提示“选择导演方案”，先看完所有方案全文和 AI 推荐结论，再选择本集采用的方向。
9. 如果页面提示“确认分镜规划”，检查表格后点击确认。
10. 下一步先进入“分镜提示词”，为故事板生成每个镜头的导演提示词。
11. 再进入“故事板”，根据分镜提示词生成黑白故事板草稿。
12. 如果这次要继续做完整视频，再进入“资产”补人物、场景、道具图，最后进入“批量视频”。

补充说明：

- PDF 和图片当前只保存，不解析正文；页面会提示补充粘贴文本、TXT、MD、DOCX 或 XLSX。
- FLOW-NAV 顶部条只告诉你下一步，完整目录默认收起来，需要时再展开。
- 项目树、素材列表和 UCODE 命令区是高级记录区，不是新手第一步必须操作的地方。

## 运行测试

```bash
source .venv/bin/activate
pytest apps/api/tests
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Seedance Skill OS 固定版本维护

当前固定提交：

```text
57d01dc66f93ecb03c2475be5f22dc416d9b701d
```

需要从上游重新同步时，只允许执行固定提交：

```bash
.venv/bin/python scripts/sync_seedance_skill.py \
  --commit 57d01dc66f93ecb03c2475be5f22dc416d9b701d
```

同步脚本会校验实际提交、去除上游 `.git`、保留 MIT License，并更新 `vendor/seedance-20/`。第三方声明位于 `third_party/seedance-20/THIRD_PARTY_NOTICE.md`。

重要边界：

- Skill OS 不能替代 V7 主系统，只能由 `SeedanceSkillAdapter` 按任务加载。
- Surface Profile 是带验证日期的本地能力快照，不是永久事实；上游 Markdown 中的价格、模型 ID 和接口字段不会自动进入生产配置。
- `vp_prompt_copy` 是面向具体 Surface Profile 编译后的自然语言提示词，不是 18 项字段的机械拼接。
- Video Unit 最长 15 秒。续接必须有已接受 Take 的真实 `observed_end_state`；延展深度超过 2 时必须重新锚定。
- 数据库迁移说明位于 `apps/api/migrations/20260718_seedance_skill_os.sql`。启动时由兼容迁移补字段，再由 SQLModel 创建新表。

## 使用流程手动验收

打开首页后应该看到：

- 页面顶部显示“系统规则已载入”
- 状态栏显示 `V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + DIRECTOR-TECH PLUS + UNIFIED-SB`
- 状态栏显示当前系统版本、真实模型配置状态和逐次确认闸门
- 首页展示“上传剧本 / 分镜表开始”创作向导和 9 个流程动作入口
- 左侧导航展示：项目首页、开始 / 规划、资产、故事板、视频包、批量视频、检查 / 修正、成本与设置

1. 打开首页。
2. 在“上传剧本 / 分镜表开始”中填写项目名称。
3. 粘贴一段剧本，或上传 TXT / MD / DOCX / XLSX 文件。
4. 点击“创建项目并保存资料”，系统会先保存资料并提取文字。
5. 确认系统自动创建 `EP01 / SC01 / SH001` 并保存资料。
6. 在“开始 / 规划”页面确认第一屏显示“现在只做一件事”。
7. 点击“用真实 AI 做导演分析”，确认弹窗后生成启动分析；没有 API 时先到“成本与设置”配置慧梦或 OpenAI。
8. 按主任务卡提示填写导演方案名称，点击“确认方案”。
9. 点击“生成分镜规划”，确认后检查建议 `EP / SC / SH` 行。
10. 点击“确认分镜规划”，确认项目结构出现对应场和镜头。
11. 确认左侧导航状态颜色随流程推进变化。

如果上传 PDF、图片或分镜表图片，系统只保存文件，不解析正文；请补充粘贴文本、TXT、MD、DOCX 或 XLSX 以生成分镜规划。

## 剧本资产闭环手动验收

1. 点击左侧“资产”，再点击“从剧本识别资产”。
2. 确认本次真实文字分析后，检查系统列出的人物、服装、场景、关键道具、原文依据和出现的场次。
3. 识别结果不准确时，点击对应资产的“修改识别结果”；正常情况下不需要手动填写工程表单。
4. 每项资产可选择“生成新图”或“上传已有图”：
   - “生成新图”会在确认后提交一次真实图片任务，完成后下载为新的资产版本。
   - “上传已有图”会把本地 PNG / JPG / JPEG / WEBP 保存为新的资产版本。
5. 在资产版本列表中点击“确认为当前”。旧版本和锁定版本不会被覆盖。
6. 所需资产均有当前确认版本后，点击“按剧情自动绑定全部资产”。系统会按剧本识别结果绑定人物、服装、场景和道具到对应场次。
7. 检查绑定摘要；全部完成后点击“生成成片提示词”。

安全说明：系统不会因为识别出多项资产就自动批量生图。真实文字识别和每一张真实图片都需要用户明确确认，已有图片可以直接上传，不产生生图费用。

开发调试说明：

- 手动登记人物、服装、场景和绑定表单只作为识别错误时的修正入口，默认收在高级区。
- 旧的 SVG 占位图正式入口已经停用；页面不会把占位图作为资产成果提供。
- `VITE_SHOW_DEV_TOOLS=true` 只用于开发人员查看历史兼容工具，不属于正式创作流程。

说明：

- 素材单文件最大为 `25 MB`。
- 同名文件会自动添加唯一前缀，不覆盖原文件。
- 归档项目、集、场或镜头不会删除本地文件，可以恢复。
- 双击集、场或镜头名称可以重命名。

## V7 FLOW-NAV + VP-PRECISION-18 手动验收

1. 在“开始 / 规划”用真实文本大脑生成导演启动分析，并填写方案名称，点击“确认导演方案”。
2. 用真实文本大脑生成分镜规划，确认后按流程建议进入分镜提示词和故事板。
3. 打开“视频提示词”，为镜头点击“用真实 AI 生成故事板参考提示词”；展开后确认显示完整 18 项导演结构。
4. 打开“故事板”，保存 Axis 计划，为镜头生成故事板。
5. 确认故事板显示 `Storyboard Grid`、`Grid Reason`、`Prompt Match` 和轴线校验状态。
6. 确认故事板后，返回“视频提示词”，点击“用真实 AI 生成最终视频提示词”并确认当前版本。
7. 打开“批量视频”创建队列，确认只有已确认的正式执行包可以进入预算闸门。
8. 导出即梦 ZIP，检查逐镜生产包文件清单。

说明：

- 故事板图、HTML 和 PNG 都保存在当前项目的 `04_storyboards/` 目录。
- 旧版固定 3 格故事板和短视频提示词继续保存在 SQLite 中，但新版页面默认隐藏。
- 未登记跨轴过渡时，如果镜头越过安全侧，轴线校验会失败并阻止确认。
- 故事板先生成可版本化的结构与时间段绑定；如已在设置页开启真实生图，可在故事板页对单个镜头点击“真实生图 → 查询结果 → 下载成新版本”。旧故事板版本不会被覆盖。

## 慧梦 image-2 故事板真实生图验收

这条链路只生成当前镜头的一张故事板图，不生成视频，也不会批量提交：

1. 打开“成本与设置”。
2. 填写 `HUIMENGI_API_KEY`、`HUIMENGI_IMAGE_BASE_URL=https://api.huimengi.com`、`HUIMENGI_IMAGE_MODEL=image-2`。
3. 勾选“启用真实生图逐次确认”，点击“写入本地 .env 并刷新状态”。
4. 打开“故事板”，先为某个镜头生成故事板结构。
5. 点击该镜头的“真实生图”，确认弹窗。
6. 任务进入处理中后点击“查询结果”。
7. 任务完成后点击“下载成新版本”。
8. 确认同一镜头出现新的故事板版本，图片保存到项目目录 `04_storyboards/frames/` 下。

如果按钮提示还有条件没满足，请先看卡片里的红色缺项；常见原因是未开启真实生图、未配置慧梦 Key、或没有先生成新版故事板草稿。

## 灵活创作目标

工作台不强制每个项目都走完整生产流程。首页和“开始 / 规划”页可以选择“本次创作目标”，并按项目保存：

- `完整生产流程`：按“剧本 → 导演分析 / 规划 → 导演方案 → 分镜提示词 → 黑白故事板 → 资产图 → 批量视频”继续推进。
- `只要提示词和故事板`：完成导演分析、规划、导演方案、分镜提示词和黑白故事板草稿后即可停下；不强制先做正式资产图。
- `只做资产图`：完成导演分析和规划后，进入资产页生成或上传人物、场景、道具图。
- `只要导演分析和分镜规划`：确认分镜规划后即可停下，不进入故事板、资产图或视频生成。

说明：

- 灵活目标只决定“这次做到哪里停”，不跳过剧本理解、导演方案、镜头拆分和视觉连续性判断。
- 黑白故事板草稿以分镜提示词为依据，不需要先准备正式资产图；正式视频提示词和批量视频才需要补齐资产图一致性。
- “故事板”页提供“导出提示词 + 故事板包”，会在本地生成 ZIP。
- ZIP 内按镜头包含 `storyboard_frame.png`、`storyboard_page.png`、`video_prompt_copy.txt`、`video_prompt_full.txt`、`vp_precision_18.json`、`director_technique.json`、`meaning_chain.json`、`storyboard_grid.json`、`unified_sb_meta.json` 和 `copy_card.md`。
- 该导出不会调用 OpenAI、慧梦、Atlas Cloud、Seedance 或即梦网页，不产生费用。

## 火山方舟 Seedance 2.5（首期 Mock）

批量视频页现提供“慧梦 API、即梦 CLI、火山方舟 Seedance 2.5”三条独立通道。Seedance 2.5 首期严格使用 Mock Provider，只验收参数、参考绑定、批量派发、后台恢复和结果状态，不会向火山方舟发送请求，也不会生成可播放视频或产生费用。

- 模型：`doubao-seedance-2-5-260628`
- 分辨率：`480p`、`720p`，默认 `720p`
- 时长：智能时长，或指定 `4-30` 秒
- 参考上限：图片 30、视频 10、音频 10，合计不超过 50 项
- 提示词会保留 `@图片N`、`@视频N`、`@音频N`，并记录每个素材的用途和禁止迁移内容
- Seedance 2.5 默认启用后台提示词优化：按“主体、动作/事件、场景与环境、视觉风格、运镜/切镜、声音”整理执行结构，同时完整保留导演原始提示词
- 优化器是项目内置的确定性规则实现，不调用外部 AI，也不冒充已安装官方 `sd25-pe` 包；发送前预览会同时展示优化前后文本、规则版本和警告
- 用户可在批量参考检查区关闭自动优化；开关变化会撤销对应镜头的绑定确认，必须重新核对后才能启动
- 模型、时长、分辨率、提示词、资产版本、素材顺序或用途变化后，当前镜头的绑定确认会自动失效
- Mock 完成后只保存带有 `outbound_request_sent=false` 的本地 `.json` 验收记录，不创建伪造 MP4 或视频结果版本

预留的本地环境配置如下。API Key 只允许写入 `.env`；首期即使配置 Key，也不会因而开放真实提交：

```text
VOLCENGINE_ARK_API_KEY=
VOLCENGINE_ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE25_MODEL_ID=doubao-seedance-2-5-260628
SEEDANCE25_LIVE_ENABLED=false
```

验收步骤：在批量视频页选择 Seedance 2.5，逐镜核对结构化参考及 Provider Request Preview，确认全部有效绑定和费用未知风险，再启动整批 Mock。离开页面或重启后端后，监督器会从 SQLite 中恢复未完成任务；页面只显示真实本地阶段，不伪造服务商任务 ID 或百分比。

## 当前未完成

以下内容需要等待用户确认后，按后续 Milestone 逐步开发：

- 真实批量视频提交
- Atlas Cloud `uploadMedia / generateVideo / prediction` 真实接入
- 基于其他目标聚合平台官方 API 文档实现的专属 Adapter
- 批量故事板真实生图
- 即梦网页自动操作（V0.1 明确不实现）

## 真实主流程手动验收

1. 在“成本与设置 → AI 服务配置中心”填写慧梦或 OpenAI 文本配置。
2. 打开首页，粘贴或上传剧本 / 分镜资料。
3. 在“开始 / 规划”点击“用真实 AI 做导演分析”，确认弹窗后生成导演启动分析。
4. 点击“生成分镜规划”，审阅后点击“确认分镜规划”。
5. 在所有导演方案中选择本集采用的方向；页面会保留全部备选方案和 AI 推荐结论。
6. 打开“分镜提示词”，一次性补齐当前场缺失的故事板参考提示词。
7. 打开“故事板”，根据分镜提示词生成黑白故事板草稿；这一步不要求先有正式人物图或场景图。
8. 如只需要提示词和故事板，可在“故事板”导出提示词 + 故事板 ZIP 后结束。
9. 如要继续完整视频流程，再打开“资产”，逐项生成或上传人物、服装、场景、道具图。
10. 回到“分镜提示词”，点击“用真实 AI 生成最终视频提示词”，确认逐镜视频提示词的完整导演结构。
11. 如要验收单镜视频，进入“批量视频”，创建只含 1 个镜头的慧梦单镜队列，确认预算后逐次点击真实提交、查询、下载；如果已安装并登录即梦 CLI，也可以选择“即梦 CLI 提交 / 查询 / 下载”。

说明：即梦通道不会自动操作网页。视频导入单文件最大 `500 MB`。

## 检查 / 修正 / 一键定位

1. 点击左侧“检查 / 修正”，选择当前场。
2. 在“检查”页点击“检查当前场是否可继续”，查看阻塞项和是否可进入下一步。
3. 点击“用真实 AI 生成摘要”，确认弹窗后生成中文摘要。
4. 切换至“修正”，勾选问题，点击“确认修正并生成处理记录”。
5. 确认每个问题分别生成修正记录和处理入口；资产、故事板和视频提示词不会由本地规则自动伪造成正式新版本。
6. 切换至“一键推进”，点击“检查并定位下一步”，确认流程在首个未满足闸门暂停。
7. 打开“成本与设置”，确认页面只显示 API Key 是否已配置，不显示密钥正文。

如需手动验收一次真实 OpenAI 摘要，可以在“成本与设置 → AI 服务配置中心”填写，也可以手工编辑本地 `.env`。OpenAI 官方通常一个 API Key 可用于同一账号下的文本和图像能力，但模型名需要分开填写：

```text
TEXT_PROVIDER_MODE=openai_responses
ENABLE_REAL_TEXT_ANALYSIS=true
OPENAI_API_KEY=你的本地密钥
OPENAI_MODEL_DIRECTOR=你选择的官方导演分析 model id
OPENAI_MODEL_ROUTINE=你选择的官方文本 model id
OPENAI_IMAGE_MODEL_PRODUCTION=你选择的官方正式图像 model id
OPENAI_IMAGE_MODEL_DRAFT=你选择的官方草稿图像 model id
OPENAI_MAX_OUTPUT_TOKENS=4000
```

通过设置页保存会自动刷新后端状态；如果手工编辑 `.env`，请重启后端。然后在检查页点击“生成中文摘要”。页面会要求逐次确认。本功能不提供批量真实调用。

## 慧梦 API 单镜真实测试

先在“成本与设置 → AI 服务配置中心”填写，或手工编辑本地 `.env`。不要把密钥发到聊天或提交到代码仓库：

```text
SEEDANCE_REAL_SUBMIT_ENABLED=true
VIDEO_PROVIDER_MODE=huimeng_live
HUIMENGI_API_KEY=你的本地慧梦密钥
HUIMENGI_TEXT_BASE_URL=https://api.huimengi.com/v1
HUIMENGI_TEXT_MODEL=gpt-5.5
HUIMENGI_IMAGE_BASE_URL=https://api.huimengi.com
HUIMENGI_IMAGE_MODEL=image-2
HUIMENGI_VIDEO_BASE_URL=https://api.huimengi.com
HUIMENGI_VIDEO_MODEL=seedance-2.0-fast
HUIMENGI_BASE_URL=https://api.huimengi.com
HUIMENGI_MODEL_ID=seedance-2.0-fast
```

通过设置页保存会自动刷新后端状态；如果手工编辑 `.env`，请重启后端。手动验收：

1. 打开“成本与设置”，确认“慧梦 Seedance 单镜真实测试”显示密钥已配置。
2. 在“真实单镜验收向导”查看 4 步提示。
3. 打开“批量视频”，选择“慧梦 API｜Seedance 2.0 Fast Value 单镜实测”。
4. 创建只含 1 个镜头的队列，确认准备闸门逐项显示。
5. 确认任务规格为 `1-15 秒 / 720p`，首次建议用 `5 秒 / 720p` 小样。
6. 点击预算确认。
7. 点击“慧梦真实提交”，在浏览器弹窗中确认。
8. 任务进入 `submitted` 或 `processing` 后，点击“查询状态”，直到任务变为 `completed`。
9. 点击“下载结果”，确认视频保存到 `07_results/generated_videos/` 并绑定当前 Shot ID。

保护规则：

- 不开放真实批量提交。
- 不上传参考素材，这次只提交文本提示词。
- 非 1 个任务、超过 15 秒、非 720p、未确认预算、未点击页面确认都会被后端拒绝。

## 即梦 CLI 账号积分通道

这条通道使用你电脑上已经登录的官方 `dreamina` CLI，不接 ChatGPT Pro 网页账号，也不自动操作即梦网页。

1. 按即梦官方流程在本机安装 `dreamina`。
2. 在终端执行 `dreamina login`，登录态由官方 CLI 或 macOS 钥匙串管理。
3. 打开“成本与设置”，确认“即梦 CLI 视频通道”显示已安装、已登录和积分摘要。
4. 在“分镜提示词”生成当前镜头的分镜提示词。
5. 在“批量视频”创建单镜队列并确认预算。
6. 点击“即梦 CLI 提交”，在弹窗中确认本次积分风险。
7. 任务提交后点击“即梦查询”；完成后点击“即梦下载”。
8. 下载后视频会保存到当前项目 `07_results/generated_videos/`，并绑定当前 Shot ID。

保护规则：

- 应用不会保存账号、密码、Cookie、Token 或完整 CLI 登录信息。
- 首版只做受控单镜，不做无人值守批量扣积分。
- 素材是可选参考；没有素材时也可以用分镜提示词提交。
- 查询和下载都需要页面确认，不会后台自动轮询或自动下载。

## 开发工具：服务通道接入准备

以下能力默认隐藏，不属于正式使用流程。只有设置 `VITE_SHOW_DEV_TOOLS=true` 后，才会在“成本与设置”中显示“视频服务通道管理”。

1. 打开“成本与设置”，找到“视频服务通道管理”。
2. 根据目标聚合平台官方文档填写 Base URL、创建 / 查询 / 取消 Endpoint、鉴权 Header、模型 ID、文档 URL、价格来源、字段映射和能力配置。
3. 点击“保存本地 Profile”，确认页面提示“未发送网络请求”。
4. 点击“本地接入预检”，确认检查密钥环境变量、文档、价格和映射完整度。
5. 打开“批量视频”，选择新服务通道创建本地队列。
6. 点击某个任务的“预览映射”，确认显示脱敏请求映射和“未发送网络请求”。
7. 对尚未提交的队列切换服务通道，点击“重映射当前待提交队列”，确认预算重新进入人工确认状态。
8. 在“成本与设置”点击通用服务通道的“演练响应映射”，粘贴脱敏响应样例，确认显示归一化结果和“未发送网络请求”。
9. 点击“载入 Atlas Cloud 禁用模板”，确认表单自动填入 `https://api.atlascloud.ai`、`ATLASCLOUD_API_KEY` 和 `USD` 按秒单价；保存后仍然只允许本地预检与映射演练。

已保存的通用 Profile 可以点击“编辑”继续补充，不需要重复新增。
已经提交、完成或导入结果文件的队列禁止重映射服务通道，避免历史记录被篡改。
响应样例演练不会保存样例正文，也不会下载视频；真实响应快照只在后续正式 Adapter 中保存。

说明：Atlas Cloud 官方资料已经登记。当前只保存 `uploadMedia / generateVideo / prediction` 的本地映射说明。完整 Atlas Cloud 真实接入仍未开放；后续需要单独实现素材上传映射，再经过用户确认才可讨论一次低预算真实验收。

## 当前接口

```text
GET    /health
GET    /api/system-prompt/status
GET    /api/projects
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
PATCH  /api/projects/{project_id}/creative-goal
DELETE /api/projects/{project_id}
POST   /api/projects/{project_id}/restore
POST   /api/projects/{project_id}/episodes
POST   /api/episodes/{episode_id}/scenes
POST   /api/scenes/{scene_id}/shots
POST   /api/projects/{project_id}/source-files
POST   /api/projects/{project_id}/source-files/text
GET    /api/projects/{project_id}/source-files
POST   /api/source-files/{source_file_id}/extract-text
GET    /api/projects/{project_id}/source-text-extractions
GET    /api/projects/{project_id}/planning-drafts
POST   /api/projects/{project_id}/planning-drafts/ai
POST   /api/planning-drafts/{draft_id}/apply
POST   /api/projects/{project_id}/ucode-runs
GET    /api/projects/{project_id}/ucode-runs
GET    /api/projects/{project_id}/flow-nav
POST   /api/episodes/{episode_id}/director-option-confirmations
GET    /api/projects/{project_id}/assets
POST   /api/projects/{project_id}/characters
POST   /api/characters/{character_id}/master-versions
POST   /api/characters/{character_id}/costumes
POST   /api/costumes/{costume_id}/versions
POST   /api/scenes/{scene_id}/assets
POST   /api/scene-assets/{scene_asset_id}/versions
POST   /api/scenes/{scene_id}/bindings
POST   /api/asset-versions/{kind}/{version_id}/{action}
GET    /api/projects/{project_id}/storyboards
PATCH  /api/scenes/{scene_id}/axis-plan
POST   /api/shots/{shot_id}/storyboard-versions
POST   /api/storyboard-versions/{version_id}/{action}
POST   /api/scenes/{scene_id}/storyboard-pages
POST   /api/scenes/{scene_id}/prompt-storyboard-export
GET    /api/projects/{project_id}/video-packages
POST   /api/shots/{shot_id}/vp-blocks/ai-version
POST   /api/vp-blocks/{version_id}/{action}
GET    /api/projects/{project_id}/batch-video
POST   /api/scenes/{scene_id}/batch-video-jobs
POST   /api/batch-video-jobs/{job_id}/remap-provider
POST   /api/batch-video-jobs/{job_id}/confirm-budget
POST   /api/batch-video-jobs/{job_id}/jimeng-export
POST   /api/batch-video-tasks/{task_id}/import-video
GET    /api/video-provider-profiles
GET    /api/video-provider-templates/atlas-cloud
GET    /api/video-provider-templates/huimeng
GET    /api/video-provider-live-status
POST   /api/video-provider-profiles
PATCH  /api/video-provider-profiles/{profile_id}
POST   /api/video-provider-profiles/{profile_id}/validate
POST   /api/video-provider-profiles/{profile_id}/set-default
POST   /api/video-provider-profiles/{profile_id}/preflight
POST   /api/video-provider-profiles/{profile_id}/response-preview
POST   /api/batch-video-tasks/{task_id}/provider-request-preview
GET    /api/batch-video-tasks/{task_id}/live-readiness
POST   /api/batch-video-tasks/{task_id}/live-submit
POST   /api/batch-video-tasks/{task_id}/live-poll
POST   /api/batch-video-tasks/{task_id}/live-download
GET    /api/projects/{project_id}/workflow-review
POST   /api/scenes/{scene_id}/workflow-check-reports
POST   /api/workflow-check-reports/{report_id}/summarize
POST   /api/workflow-issues/fix-batch
POST   /api/scenes/{scene_id}/one-click-runs
POST   /api/one-click-runs/{run_id}/advance
GET    /api/ai-provider/status
GET    /api/local-env/status
PATCH  /api/local-env
```

说明：旧的 `POST /api/projects/{project_id}/planning-drafts` 本地规则草案入口已停用，仅保留 410 响应用于兼容旧客户端；正式规划只能走真实文本模型接口。早期开发用的状态演练接口只为历史数据兼容保留，不属于正式用户路径；正式视频只走慧梦真实单镜闸门。
