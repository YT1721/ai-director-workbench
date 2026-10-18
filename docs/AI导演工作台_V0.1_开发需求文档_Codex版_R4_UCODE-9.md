# AI导演工作台｜本地应用 V0.1 开发需求文档（Codex 开发版 R4）
## 基于当前主版本：V7.0 Plus R1｜CH-Asset Pro + SB-STYLE-LOCK 故事板统一风格版
### 当前主线：UCODE-9 极简交互 + 批量视频编排 + Cost Router + Seedance 聚合 API 兼容层

---

## 0. 本文档用途

本文档用于直接交给 **Codex** 开发一个本地运行的 AI 视频前期制作与批量生成工作台。

### 当前必须加载的系统母文件

开发时，应用中的系统规则库必须以以下文件为当前正式主版本：

```text
剧本视觉化创作系统_V7.0_Plus_R1_UCODE-9_FLOW-NAV_VP-PRECISION-18固定视频包模板版_完整主版本.txt
```

该主版本已经包含：

```text
原始《漫剧视觉化创作系统 V6.9.1 Plus R2》完整历史工作流
UCODE-9｜用户只需使用 9 个统一动作码
角色母版 / 服装派生 / 场次绑定 / 一致性锁定能力
黑白灰写实铅笔草稿故事板统一风格
空间轴线与镜头机位连续性锁定，防止故事板跳轴
页级故事板 / 单镜头故事板直接出图能力
资产—故事板—视频执行包自动串联
版本确认、锁定、回滚与同步更新
逐镜视频执行包与批量视频编排能力
```

### 本应用要解决的问题

当前系统已经完成调用方式简化：用户层只使用 UCODE-9，不再面对大量技术调用码。本应用要把 9 个统一动作变成可视化入口、命令输入框和可追踪工作流；原有角色、故事板、轴线、版本与视频能力作为后台执行模块保留。

---

# 1. 产品定位与目标

## 1.1 产品名称

暂定名称：

```text
AI导演工作台 / AI Director Workbench
```

后续可归入你的项目品牌：

```text
智影工坊 StoryForge.AI
```

## 1.2 一句话定位

一个在电脑本地运行的 AI 影视创作工作台：用户通过 9 个易懂动作完成从剧本到批量视频任务的全过程；后台自动处理角色一致性、黑白故事板、轴线连续、资产版本与视频 Provider 适配。

## 1.3 V0.1 的成功标准

用户能在应用中完成以下流程：

```text
新建项目并上传剧本与参考素材
→ `V7｜开始｜EP01`：形成导演方案
→ `V7｜规划｜EP01`：形成镜头规划与资产需求
→ `V7｜资产｜EP01SC01`：生成 / 登记人物、服装与场景资产
→ `V7｜故事板｜EP01SC01｜SH001-SH003`：生成统一黑白草稿且无跳轴的故事板
→ `V7｜视频包｜EP01SC01｜SH001`：生成逐镜视频资料
→ `V7｜批量视频｜EP01SC01`：构建批量视频队列
→ 用 Mock 模式验证队列与 Provider 兼容流程
→ 导出即梦手动积分使用包
```

V0.1 结束时，**不要求真实消耗 API 费用**。真实 OpenAI 与 Seedance 接入应在流程和数据保存都验证稳定后再启用。

---

# 2. 技术与模型路线：固定方案

## 2.1 模型职责

| 制作环节 | 技术方案 | V0.1 实施方式 |
|---|---|---|
| 剧本解析、导演方案、分镜结构、资产绑定、VP-Block | OpenAI API 文本模型 | 先 Mock，后接真实 API；模型名由配置文件设置 |
| 人物母版、服装派生、场景资产、单镜头故事板图 | OpenAI GPT Image API | 先用占位图 / Mock；真实阶段默认可配置为 `gpt-image-2` |
| 页级导演故事板执行页 | 本地程序排版合成 | V0.1 必须实现，不依赖模型生成文字排版 |
| 最终视频生成 | Seedance 2.0 可配置 Provider | 主用第三方聚合平台 API，保留火山方舟官方适配能力；V0.1 先做 Mock 与通用适配层 |
| 使用即梦订阅积分生成视频 | 辅助人工编排通道 | 导出资产包与提示词，用户手动在即梦使用积分，再导回结果 |

## 2.2 关于“ChatGPT 作为模型”的落地说明

应用不能使用网页端 ChatGPT Plus 的对话额度作为后端接口。正式开发落地应采用：

```text
OpenAI API：文本分析与图像资产生成
Seedance 2.0 可配置 Provider：正式自动视频生成（第三方聚合平台为主，可切换官方或其他兼容平台）
```

## 2.3 即梦积分模式边界

首版不开发下列功能：

```text
模拟登录即梦网页
自动点击生成
自动消耗订阅积分
绕过官方方式抓取结果
```

V0.1 的即梦通道仅实现：

```text
应用自动匹配资产与提示词
→ 导出每镜可投喂的编排资料包
→ 用户手动在即梦中生成
→ 将结果视频拖回应用
→ 应用自动绑定 Shot ID 与版本
```

若未来获得官方支持订阅积分的开发接口或明确授权，再另行接入自动提交。

---

# 3. 应用形态与技术栈

## 3.1 第一阶段形态

开发为本地 Web 应用：

```text
前端：http://localhost:3000
后端：http://localhost:8000
本地数据库：SQLite
本地项目资产：保存在 data/projects/
```

第一阶段不要直接打包桌面安装包；运行稳定后再考虑用 Tauri 封装。

## 3.2 固定技术栈

| 层级 | 选择 |
|---|---|
| 前端 | React + Vite + TypeScript |
| 页面样式 | Tailwind CSS |
| 路由 | React Router |
| 前端状态 | Zustand |
| 后端 | Python FastAPI |
| 数据库 ORM | SQLModel |
| 数据库 | SQLite |
| 数据校验 | Pydantic |
| 图片 / PDF 页面导出 | Playwright 截取 HTML/CSS 页面 |
| API Provider | 独立 Adapter / Provider 层；视频侧支持第三方 Seedance 聚合 API / 官方 API / Mock / 即梦辅助通道 |
| 后端测试 | Pytest |
| 前端测试 | Vitest |
| 环境变量 | `.env`，仓库只提交 `.env.example` |

## 3.3 推荐项目目录

```text
ai-director-workbench/
├── AGENTS.md
├── README.md
├── .env.example
├── docs/
│   └── AI导演工作台_V0.1_开发需求文档_Codex版_R2.md
├── system-prompts/
│   └── 剧本视觉化创作系统_V7.0_Plus_R1_UCODE-9_FLOW-NAV_VP-PRECISION-18固定视频包模板版_完整主版本.txt
├── apps/
│   ├── web/
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   ├── components/
│   │   │   ├── features/
│   │   │   ├── services/
│   │   │   └── stores/
│   │   └── package.json
│   └── api/
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── routers/
│       │   ├── services/
│       │   ├── providers/
│       │   │   ├── openai_text_mock.py
│       │   │   ├── openai_image_mock.py
│       │   │   ├── seedance_mock.py
│       │   │   ├── openai_text.py
│       │   │   ├── openai_image.py
│       │   │   ├── video_provider_base.py
│       │   │   ├── seedance_aggregator_generic.py
│       │   │   ├── seedance_volcengine.py
│       │   │   └── jimeng_credit_assist.py
│       │   ├── workflows/
│       │   └── utils/
│       └── tests/
└── data/
    ├── app.db
    └── projects/
```

---

# 4. 功能范围总览

## 4.1 V0.1 必须实现

| 模块 | 必做内容 |
|---|---|
| 项目管理 | 项目、集、场、镜头、上传素材、本地目录 |
| 系统规则库 | 加载当前 V7.0 TXT；可显示版本号与启用状态 |
| 导演分析 | 先使用 Mock 结果保存导演方案、G-Block、S-Block 与镜头表 |
| CH-Asset Pro | 人物母版、服装资产、场次绑定、一致性锁定数据结构与界面 |
| SC-Asset | 场景资产结构、版本与绑定 |
| VM-Block | 资产确认、锁定、回滚与版本历史 |
| SB-STYLE-LOCK | 故事板全局风格状态、黑白草稿版式约束 |
| SB-Shot | 保存 / 展示单镜头故事板图；V0.1 可先用占位图 |
| SB-Block | 用程序合成正式页级 Storyboard Execution Page |
| VP-Block | 保存逐镜视频执行包及绑定资产 |
| BV-Block | 批量视频队列、资产检查、Mock 生成、第三方 Seedance 聚合 API 通道适配与即梦资料包导出 |
| Cost Router | 缓存、模型职责配置、预算闸门与成本日志字段 |
| 设置页 | Provider 模式、环境变量状态、项目存储位置 |

## 4.2 V0.1 不做

```text
真实付费 OpenAI 调用
真实付费 Seedance 批量提交（但必须完成多 Provider 配置与 Mock 验证结构）
自动操作即梦客户端 / 网页
视频自动剪辑、自动成片、配音、配乐
多用户与云端协作
商业计费、订阅、API 分销
本地 ComfyUI
```

---

# 5. 关键业务原则

## 5.1 用户只面对 UCODE-9

产品界面不得要求用户记忆内部能力名称。用户的主操作入口只有：

```text
V7｜开始      V7｜规划      V7｜资产
V7｜故事板    V7｜视频包    V7｜批量视频
V7｜一键      V7｜检查      V7｜修正
```

后台仍可保存人物母版、服装、风格锁、轴线锁、版本、视频包等专业数据，但界面默认使用通俗表达。

## 5.2 四个正式生产闸门

| 闸门 | 检查内容 | 未通过时禁止 |
|---|---|---|
| 资产闸门 | 正式人物、服装、场景版本与绑定状态 | 禁止正式故事板 / 正式视频队列 |
| 故事板闸门 | 黑白草稿风格、页级执行页、单镜故事板 | 禁止正式视频提交 |
| 轴线闸门 | 人物屏幕位置、运动方向、机位侧、跨轴计划 | 禁止以跳轴故事板生成视频 |
| 费用 / Provider 闸门 | Provider 能力、生成数量、时长、预计费用 | 禁止真实视频 API 提交 |

## 5.3 所有资产必须版本化

```text
任何新生成、重新生成、局部修改的资产，都必须产生新版本。
confirmed_current / locked 版本不得覆盖。
```

## 5.4 正式故事板必须程序合成

**禁止**将整张 Storyboard Execution Page 的小字、编号、结构化信息直接交由图像模型一次生成。

```text
AI / Mock 生成或导入黑白镜头图
→ 后端提供准确镜头数据、资产编号、Axis 数据和场次信息
→ 前端 HTML/CSS 模板排版
→ Playwright 导出 PNG / PDF
```

## 5.5 正式故事板必须同时满足两种锁定

```text
风格锁定：统一为黑白灰写实铅笔草稿导演故事板风格。
轴线锁定：同一场戏 / 连续剧情中的人物位置、屏幕方向、运动方向与机位侧不得无理由跳变。
```


# 6. UCODE-9 用户交互与后台能力映射

## 6.1 用户可见的 9 个统一入口

| UCODE-9 调用 | 应用按钮名 | 用户得到什么 |
|---|---|---|
| `V7｜开始｜EP01` | 开始项目 / 导演分析 | 剧情分析、导演方案、方案选择 |
| `V7｜规划｜EP01` | 生成制作规划 | 场次、镜头、资产需求、视频提示词 |
| `V7｜资产｜EP01SC01` | 生成本场资产 | 人物、服装、场景、绑定与版本管理 |
| `V7｜故事板｜EP01SC01｜SH001-SH003` | 生成故事板 | 黑白草稿页级执行页及所需单镜图 |
| `V7｜视频包｜EP01SC01｜SH001` | 生成视频资料 | 镜头提示词与参考资产清单 |
| `V7｜批量视频｜EP01SC01` | 批量视频编排 | 任务队列、Provider 检查、导出包 |
| `V7｜一键｜EP01SC01` | 一键推进本场 | 分阶段自动推进，在闸门处暂停 |
| `V7｜检查｜EP01SC01` | 检查本场 | 错误列表与是否可进入下一步 |
| `V7｜修正｜EP01SC01` | 修正问题 | 只修正用户指定问题并产生新版本 |

## 6.2 附加要求输入方式

用户不需要新的技术码，只需在主动作后补充文字：

```text
V7｜资产｜EP01SC01
要求：生成朱元璋人物母版、C01-C04 服装，以及坤宁宫寝殿场景。
```

```text
V7｜故事板｜EP01SC01｜SH001
输出类型：单镜头故事板图
```

```text
V7｜修正｜EP01SC01｜SH004-SH006
问题：人物位置跳轴。
要求：保持剧情、人物、服装和黑白草稿风格不变，只修正屏幕方向与机位。
```

## 6.3 后台能力映射｜不作为用户主操作入口

| UCODE-9 动作 | 后台按需执行的专业能力 |
|---|---|
| `V7｜规划` | 原三阶段流程、G/S 记忆块、场次和镜头规划 |
| `V7｜资产` | 人物母版、服装派生、场次绑定、人物一致性、场景资产、资产串联、版本确认/锁定/回滚 |
| `V7｜故事板` | 故事板黑白风格锁定、轴线连续性锁定、页级执行页、单镜图、镜头对齐 |
| `V7｜视频包` | 资产匹配、逐镜视频执行包、连续性约束 |
| `V7｜批量视频` | 批量任务、Provider Capability 检查、任务导出 / 提交 |
| `V7｜一键` | 资产 → 故事板 → 视频包的阶段式总控 |
| `V7｜检查` / `V7｜修正` | 版本、一致性、风格、跳轴、资产引用与问题修复 |

## 6.4 旧码兼容规则

旧系统中出现过的技术码仍可被解析为兼容别名，但：

```text
- 用户界面不展示旧码菜单；
- 新建项目不引导用户使用旧码；
- 导入旧项目时，可将旧码运行记录映射至对应 UCODE-9 动作；
- 系统回复与 README 始终优先使用 UCODE-9。
```


# 7. 页面信息架构

## 7.1 左侧主导航

```text
项目首页
开始 / 规划
资产
故事板
视频包
批量视频
检查 / 修正
成本与设置
```

说明：内部数据仍按角色、场景、版本、Provider 等组织，但用户主导航应围绕 UCODE-9 工作顺序，而不是暴露技术模块名称。

## 7.2 首页快捷动作卡

项目工作台首页固定提供 9 个入口按钮：

```text
[开始] [规划] [资产] [故事板] [视频包]
[批量视频] [一键推进] [检查] [修正]
```

每个按钮自动带入当前项目、集、场或已选择镜头范围。

## 7.3 UCODE 命令输入框

界面保留一个可输入自然语言补充要求的命令区：

```text
动作：V7｜故事板
范围：EP01SC01｜SH001-SH003
补充要求：保持人物站位不变，输出正式页级故事板。
[执行]
```

## 7.4 页面功能摘要

| 页面 | 页面内容 |
|---|---|
| 项目首页 | 创建 / 打开项目；当前集场；待确认事项；9 个快捷入口 |
| 开始 / 规划 | 上传剧本、导演方案、规划结果、镜头表 |
| 资产 | 人物、服装、场景、绑定、版本确认 / 回滚 |
| 故事板 | 黑白风格锁定状态、轴线状态、镜头图、正式执行页 |
| 视频包 | 单镜资料、引用资产、提示词与目标 Provider |
| 批量视频 | 任务队列、Provider、预算、结果导入 / 下载 |
| 检查 / 修正 | 资产、风格、跳轴、版本问题列表与纠正操作 |
| 成本与设置 | OpenAI / 视频 Provider 配置、缓存与费用记录 |


# 8. 资产后台能力｜由 `V7｜资产` 驱动

## 8.1 人物母版

### 页面功能

```text
选择角色
上传人物参考图（可选）
编辑人物基础信息
点击“生成母版”（V0.1 使用 Mock 占位）
查看版本
确认为当前版 / 锁定 / 回滚
```

### 必须保存的数据

```text
Character ID
角色名
人物母版文件路径
脸型 / 五官 / 年龄 / 身高 / 体型 / 发型 / 身份气质说明
版本号
状态：draft / confirmed_current / confirmed_history / locked / rejected
```

## 8.2 服装派生

### 必须遵守

```text
服装改变，不得改变人物母版中的脸、年龄、骨相、体型、身高与身份气质。
```

### 页面功能

```text
显示当前确认的人物母版
新增服装编号 C01 / C02 / C03...
填写使用场合与服装说明
生成服装版本
确认 / 锁定 / 回滚
```

## 8.3 场次人物绑定

每一场出现的角色必须绑定：

```text
人物母版版本 + 服装版本 + 场次状态（如病态、战损、湿发、污渍）
```

未绑定完成的带人物镜头不可进入正式批量视频队列。

## 8.4 人物一致性锁定

应用必须展示一致性检查结果：

```text
✓ 人物母版已确认
✓ 本场服装已确认
✓ 年龄 / 体型 / 身高锁定
✓ 发型未改变，或已填写变化原因
✓ 故事板与 VP-Block 已关联资产 ID
```

若不通过，显示错误项并阻止正式提交。

---

# 9. 场景资产后台能力｜由 `V7｜资产` 驱动

## 9.1 场景资产数据

每个场景保存：

```text
Scene ID
场景名称
场景说明
空间布局说明
时间 / 天气 / 光线
关键道具
主色 / 辅色 / 氛围
场景资产图版本
状态
```

## 9.2 场景资产图目标形式

正式生图阶段需参考系统约定的场景设定板风格：

```text
主场景大图
front / side / top-down / low-angle 多视角
daytime / dusk / night 等按需时段状态
材质细节区
色彩方案区
```

V0.1 可以用占位图与结构数据验证页面和版本流程。

---

# 10. 故事板工作流｜由 `V7｜故事板` 驱动

## 10.1 黑白草稿风格锁定是强制规则

应用中必须有一个全局启用状态：

```text
故事板统一风格：已启用（正式项目不可关闭）
```

所有故事板画面必须统一为：

```text
黑白灰写实铅笔草稿导演故事板风格
```

## 10.2 故事板图像禁止项

任何正式故事板镜头中禁止：

```text
彩色电影剧照
彩色关键帧
厚涂插画
漫画上色
3D 彩色渲染
海报化美术画面
同项目内风格漂移
```

## 10.3 单镜头故事板

每个 Shot 保存：

```text
镜头编号
绑定人物母版
绑定服装版本
绑定场景
景别
机位
运镜
动作起点
情绪状态
黑白故事板图路径
风格校验状态：passed / failed
版本状态
```

### UI 要求

- 每张图旁显示 `风格校验 ✓ / 轴线校验 ✓`；
- 支持重新生成、版本查看、确认为当前；
- 只有校验通过且 confirmed 的图可进入视频队列。

## 10.4 页级导演故事板执行页

### 固定页面视觉规范

```text
整页：16:9 横向
背景：深黑 / 炭黑
分隔线：白色 / 灰白色细线
强调色：橙色，仅用于栏目名、镜头编号与功能性箭头
左上：TOP-DOWN BLOCKING DIAGRAM
右上：结构化场次信息栏
中部：默认 3 个连续镜头卡
底部：CAMERA / ACTION / SOUND & LIGHT 三栏
镜头画面：全部为黑白灰写实铅笔草稿
```

### 正式执行页的程序合成方式

```text
输入：
- 3 张确认通过的 SB-Shot 黑白图
- 镜头数据 JSON
- 场次信息 JSON
- 人物 / 服装 / 场景绑定
- 调度信息 JSON

程序输出：
- HTML/CSS 页面预览
- PNG 导出
- PDF 导出
```

### V0.1 验收必须做到

至少使用三张占位黑白镜头图，成功排版并导出一张接近参考图版式的执行页；所有文字由程序准确写入，不能是生图模型伪造的小字。


## 10.5 空间轴线与机位连续性锁定

正式故事板必须自动执行空间连续性检查：

```text
同一场戏 / 连续剧情段落中，人物屏幕左右位置不得无理由翻转；
运动方向不得无理由反转；
正反打视线必须正确；
机位不得未经规划跨越 180 度轴线；
确需跨轴时，必须设计可理解的过渡镜头或重新建立空间关系。
```

页级执行页中的 `TOP-DOWN BLOCKING DIAGRAM` 必须显示：

```text
主轴线 AXIS LINE
允许机位侧 CAMERA SAFE SIDE
机位点 CAM 01 / CAM 02 / CAM 03
人物站位、视线和运动方向
跨轴过渡（如有）
```

单镜头故事板即使单独生成，也必须继承其所在镜头组的轴线数据。未通过轴线校验的镜头不得进入正式视频任务队列。

---

# 11. 视频执行资料｜由 `V7｜视频包` 驱动

## 11.1 每镜视频资料必须包含

```text
Shot ID
人物母版版本
服装资产版本
场次状态版本（如有）
场景资产版本
单镜故事板版本
SB-STYLE-LOCK 校验通过标记
景别 / 机位 / 运镜
时间轴动作说明
负面约束
目标比例与时长
目标视频 Provider
```

## 11.2 Seedance 使用资料组合

正式视频任务的输入资产清单应组织为：

```text
人物母版图
服装资产图
场景资产图
单镜头黑白故事板图
VP-Block 视频动作提示词
```

实际 Seedance API 接口可接收哪些素材类型、数量和字段，接入真实 Provider 时必须依据当时官方文档执行；业务数据库先完整保留所有资料与引用关系。

---

# 12. 批量视频编排｜由 `V7｜批量视频` 驱动

## 12.1 目标

把一整场或多个镜头的 VP-Block 与资产自动组装成视频生成队列，让用户不用逐镜复制提示词和寻找素材。

## 12.2 调用方式

```text
V7｜批量视频｜EP01SC01
V7｜批量视频｜EP01SC01｜SH001-SH006
V7｜批量视频｜EP01SC01
范围：全部已确认镜头
```

## 12.3 两种执行通道

### 通道 A｜Seedance 2.0 Provider 正式自动通道（第三方聚合 API 优先）

```text
选择镜头
→ 检查资产与版本
→ 选择已配置并测试通过的 Seedance Provider
→ 按 Provider 能力检查可提交参数
→ 显示预算确认
→ 将统一任务结构转换成该 Provider 请求格式后提交任务
→ 轮询状态或接收回调（取决于 Provider 能力）
→ 成功后下载本地
→ 登记视频版本与 Provider 提交快照
```

### 通道 B｜即梦订阅积分辅助通道

```text
选择镜头
→ 自动导出素材包与提示词
→ 用户在即梦手动使用订阅积分生成
→ 用户拖入视频结果
→ 应用绑定到镜头与版本
```

## 12.4 正式提交前的资格检查

镜头进入 `ready` 状态必须满足：

```text
若含人物：已绑定 confirmed_current / locked 的 CH-Master
若含人物：已绑定 confirmed_current / locked 的 Costume-Asset
已绑定 confirmed_current / locked 的 SC-Asset
已存在 confirmed 且 SB-STYLE-LOCK passed 的 SB-Shot
已生成 VP-Block
无未解决的人物一致性错误
预算已确认
```

否则状态为：

```text
blocked
```

并列出具体缺失项。

此外，正式提交前还必须经过 **Provider 能力检查**：

```text
目标 Provider 是否支持当前任务的生成模式（文生视频 / 首帧图生视频 / 首尾帧 / 多参考素材）
目标 Provider 是否支持当前时长、分辨率、画幅与音频设置
目标 Provider 是否支持当前需要提交的参考图片 / 视频 / 音频数量
若能力不支持，任务必须 blocked，并提示改用兼容 Provider 或简化输入资料
```

## 12.5 任务状态

```text
draft
blocked
ready
awaiting_budget_confirm
submitted
processing
completed
failed
imported
confirmed
rejected
```

## 12.6 批量编排页面布局

```text
顶部工具栏：
- 场次选择
- 生成范围：当前页面 / 当前场 / 指定镜头 / 全部
- 通道：Seedance 聚合 API / 火山方舟官方（可选）/ 即梦积分辅助 / Mock
- 预算卡片
- [检查任务] [提交生成] [导出即梦包]

左侧筛选：
- 全部
- blocked
- ready
- processing
- completed
- failed
- imported

中部任务列表：
- 镜头编号
- 故事板缩略图
- 绑定人物 / 服装 / 场景
- 时长
- Provider
- 状态
- 操作

右侧详情：
- 引用资产
- VP-Block 预览
- 版本状态
- 缺失项 / 错误
- 重试 / 重新绑定 / 导入视频
```

## 12.7 即梦导出包目录

```text
data/projects/{PROJECT_ID}/06_batch_video/jimeng_credit_exports/EP01_SC01/
├── manifest.json
├── SH001/
│   ├── storyboard_frame.png
│   ├── character_master.png
│   ├── costume_asset.png
│   ├── scene_asset.png
│   ├── vp_prompt.txt
│   └── import_result_here/
├── SH002/
└── SH003/
```

---

# 13. Cost Router｜成本路由器

## 13.1 目的

成本优化优先级必须正确：

```text
避免无效返工 > 避免重复请求 > 低价值任务使用低成本模型 > 批处理与缓存 > 减少画质或跳过关键判断
```

不要为了省少量文本费用，让角色和镜头判断失真，导致更昂贵的视频返工。

## 13.2 文本模型分工

不要在页面业务逻辑中写死具体文本模型名；模型通过设置页或 `.env` 配置：

```env
OPENAI_MODEL_DIRECTOR=
OPENAI_MODEL_ROUTINE=
```

| 任务 | 路由 |
|---|---|
| 剧本深度分析、导演方案、复杂镜头设计、角色一致性难题 | DIRECTOR |
| 文件命名、JSON 格式化、清单生成、状态摘要、批量任务校验 | ROUTINE |

## 13.3 图像模型配置

图像模型同样由配置管理：

```env
OPENAI_IMAGE_MODEL_PRODUCTION=gpt-image-2
OPENAI_IMAGE_MODEL_DRAFT=
```

应用需支持：

```text
草稿预览：少量、较低资源级别、快速验证构图
正式资产：用户确认后再调用高质量输出
```

## 13.4 Prompt Caching 设计

固定前缀保持稳定：

```text
固定部分：
- 模块规则子集
- SB-STYLE-LOCK 规则
- CH-Consistency-Lock 规则
- 输出 JSON Schema
- 固定禁止项

动态部分：
- 当前剧本片段
- 当前镜头信息
- 当前绑定资产版本
- 本次修改要求
```

实施要求：

```text
相同模块的固定前缀顺序不随请求变化；
不在每个小任务重复注入全部系统正文；
日志记录 cached input tokens（真实接 API 后启用）；
本地缓存与服务端提示词缓存是两层不同能力，都要预留。
```

## 13.5 Batch 批处理策略

适合未来 OpenAI Batch 的任务：

```text
一整场的 AM-Block 表格
多个 VP-Block 的结构化整理
批量资产命名和校验
批量镜头缺失项检测
```

不适合批处理：

```text
需要用户马上判断的导演方案
关键角色母版调整
用户正在精修的关键镜头
```

## 13.6 本地缓存与去重

对模型请求保存 `cache_key`：

```text
cache_key = hash(
  provider
  + model
  + module_type
  + system_prompt_version
  + input_asset_version_ids
  + dynamic_input
  + output_quality
)
```

规则：

```text
已存在 confirmed 且 cache_key 相同的结果 → 默认复用
用户明确要求重新生成 → 创建新版本
输入资产版本改变 → 生成新 cache_key
```

## 13.7 视频预算闸门

提交真实视频前必须展示：

```text
待生成镜头数
每镜时长与总秒数
通道
预计失败重试策略
已确认资产数量
预计费用（有可靠价格配置时）
或预计积分消耗（仅有可靠规则时）
```

必须点击：

```text
确认费用并提交
```

才允许调用真实 Provider。

---

# 14. Seedance 2.0 聚合 API 兼容设计

## 14.1 设计结论

应用的视频生成能力不能写死为某一个平台接口，而必须设计为：

```text
统一视频任务结构（业务层）
↓
Provider Adapter 转换层
↓
用户选定的第三方 Seedance 聚合平台 API / 官方 Seedance API / Mock / 即梦辅助通道
```

这样以后你更换更便宜的平台时，不需要重做角色资产、故事板、VP-Block 或批量编排逻辑，只需要增加或调整一个 Provider Adapter。

## 14.2 为什么必须兼容多 Provider

不同 Seedance 接入平台可能存在这些差异：

```text
鉴权方式不同：Bearer Token / x-api-key / 自定义 Header
Base URL 与任务创建路径不同
模型标识不同：Seedance 2.0 / Seedance 2.0 Fast / 平台自定义 model_id
任务模式不同：同步返回视频 / 异步 task_id 查询 / callback 回调
素材字段不同：first_frame_url / reference_images / reference_image_urls / 上传文件 ID
支持能力不同：首尾帧、多参考图、参考视频、参考音频、生成音频、分辨率、时长
计费方式不同：按次 / 按秒 / 按分辨率 / 按模型档位 / 平台积分
结果有效期、失败重试和并发限制不同
```

因此不能让 `BV-Block` 直接拼第三方平台原始请求字段；必须先形成统一任务，再由 Provider 负责翻译。

## 14.3 Provider 类型

V0.1 需要预留以下 Provider 类型：

```text
SeedanceMockProvider                默认测试通道，不产生费用
SeedanceAggregatorGenericProvider   通用第三方聚合 API 配置通道
SeedanceVolcengineProvider          火山方舟官方备用通道，后续按需启用
JimengCreditAssistProvider          即梦积分手动辅助资料包通道
```

未来选定某个聚合平台后，可新增：

```text
Seedance_{ProviderName}Provider
```

例如某个平台在鉴权、上传素材或轮询状态方面与通用通道差异较大时，单独实现适配器，不影响上层业务。

## 14.4 统一视频任务结构 Canonical Video Request

应用内部所有视频任务必须先整理成统一结构，禁止页面直接保存某个平台特有请求体：

```json
{
  "job_id": "EP01_SC01_SH001_VID_v001",
  "model_family": "seedance-2.0",
  "model_variant": "standard_or_fast",
  "generation_mode": "text_to_video | first_frame | first_last_frame | multimodal_reference",
  "prompt": "",
  "negative_prompt": "",
  "duration_seconds": 5,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "generate_audio": false,
  "seed": 42,
  "assets": {
    "character_master_images": [],
    "costume_images": [],
    "scene_images": [],
    "storyboard_frame_images": [],
    "first_frame_image": null,
    "last_frame_image": null,
    "reference_videos": [],
    "reference_audios": []
  },
  "callback_url": null,
  "provider_profile_id": "",
  "provider_options": {}
}
```

说明：

```text
- 本结构服务于应用业务、资产绑定和版本追溯。
- Provider 接到统一结构后，根据自身能力映射请求字段。
- 对不支持的字段，Provider 必须返回明确 capability error，不能静默丢弃关键参考资产。
```

## 14.5 Provider 能力声明 Capability Profile

每个已配置 Provider 必须保存能力声明，供 BV-Block 在提交前检查：

```json
{
  "provider_profile_id": "provider_seedance_main",
  "display_name": "我的 Seedance 聚合平台",
  "provider_type": "seedance_aggregator_generic",
  "enabled": true,
  "supported_models": ["seedance-2.0", "seedance-2.0-fast"],
  "generation_modes": ["text_to_video", "first_frame", "multimodal_reference"],
  "supported_durations": [5, 10],
  "supported_resolutions": ["720p"],
  "supported_aspect_ratios": ["16:9", "9:16"],
  "supports_audio_generation": false,
  "supports_callback": false,
  "supports_reference_images": true,
  "max_reference_images": 1,
  "supports_reference_videos": false,
  "supports_reference_audios": false,
  "result_delivery": "async_polling",
  "result_url_expires_hours": null,
  "pricing_mode": "manual_config",
  "currency": "CNY",
  "unit_price": null
}
```

### 重要规则

```text
Capabilities 由用户根据选定聚合平台官方文档配置，或由专属 Provider Adapter 预设。
在信息未确认前，应用不得假设聚合平台支持多参考图、参考视频、音频、首尾帧或特定时长。
```

## 14.6 Provider 配置页

设置页增加“视频 Provider 管理”区，至少包含：

```text
Provider 名称
Provider 类型
是否启用
Base URL
任务创建 Endpoint
任务查询 Endpoint
任务取消 Endpoint（可选）
回调 Endpoint 支持状态（可选）
鉴权类型
API Key 环境变量名
Header 名称 / Bearer 前缀
模型 ID 映射
字段映射模板
Capability Profile
价格配置
测试连接按钮
设为默认 Provider
```

### 鉴权类型选择项

```text
Bearer Token
x-api-key
Custom Header
Query Parameter（仅平台明确要求时允许）
```

### 重要安全要求

```text
设置页不得显示完整 API Key；
数据库只保存环境变量名或加密后的本地凭证引用；
任何导出包、日志、截图、错误信息不得包含完整密钥。
```

## 14.7 通用聚合 Provider 配置结构

```json
{
  "id": "provider_seedance_main",
  "name": "Seedance 聚合平台主通道",
  "provider_type": "seedance_aggregator_generic",
  "base_url": "",
  "create_task_path": "",
  "get_task_path_template": "",
  "cancel_task_path_template": "",
  "auth": {
    "type": "bearer | x-api-key | custom_header",
    "header_name": "Authorization",
    "prefix": "Bearer ",
    "env_key_name": "SEEDANCE_AGGREGATOR_API_KEY"
  },
  "model_mapping": {
    "seedance-2.0": "",
    "seedance-2.0-fast": ""
  },
  "request_field_mapping": {
    "prompt": "prompt",
    "duration_seconds": "duration",
    "resolution": "resolution",
    "aspect_ratio": "aspect_ratio",
    "first_frame_image": "",
    "last_frame_image": "",
    "reference_images": "",
    "reference_videos": "",
    "reference_audios": "",
    "generate_audio": "",
    "seed": ""
  },
  "response_field_mapping": {
    "task_id": "",
    "status": "",
    "video_url": "",
    "error_message": ""
  }
}
```

## 14.8 Provider 标准接口

```python
class VideoProvider:
    def validate_config(self) -> ProviderValidationResult: ...
    def get_capabilities(self) -> ProviderCapabilities: ...
    def estimate_cost(self, request: CanonicalVideoRequest) -> CostEstimate: ...
    def validate_request(self, request: CanonicalVideoRequest) -> ValidationResult: ...
    def create_task(self, request: CanonicalVideoRequest) -> ProviderTaskResult: ...
    def get_task_status(self, external_task_id: str) -> ProviderTaskStatus: ...
    def download_result(self, external_task_id: str, destination: str) -> str: ...
    def cancel_task(self, external_task_id: str) -> bool: ...
```

## 14.9 请求映射与素材适配原则

### 图片资产

应用中的输入资产可能包括：

```text
人物母版图
服装资产图
场景资产图
SB-Shot 单镜头故事板图
首帧图 / 尾帧图
```

Provider 层必须按平台支持能力处理：

```text
支持多参考图 → 依据 VP-Block 优先级提交必要参考图
只支持首帧图 → 优先以已确认的 SB-Shot 或正式首帧关键帧提交，并将人物/场景约束写入 prompt
不支持上传本地文件、只接 URL → 由素材上传服务先获取可访问 URL，再提交 Provider
不支持某种输入 → 明确 blocked，不得悄悄删掉关键约束继续烧费用
```

### 参考图优先级建议

```text
1. SB-Shot / 正式关键帧：锁定构图、站位和动作起点
2. CH-Master + Costume-Asset：锁定人物身份与本场服装
3. SC-Asset：锁定环境与空间
```

实际可提交数量由目标 Provider Capability 决定。

## 14.10 视频任务状态归一化

不同聚合平台返回状态字段可能不同，Provider 必须统一映射为应用内部状态：

```text
draft
blocked
ready
awaiting_budget_confirm
submitted
processing
completed
failed
cancelled
imported
confirmed
rejected
```

必须保存原始 Provider 响应快照，以便出现问题时排查。

## 14.11 成本配置与路由

第三方平台的价格可能随时变化，成本不能写死在程序业务代码中。

设置页需支持手动维护：

```text
Provider
模型档位
分辨率
时长
生成模式
单次价格 / 每秒价格 / 积分价格
币种
价格来源备注
最后更新时间
```

Cost Router 只能根据用户已填写并确认的价格配置进行预算计算；无可靠价格时显示：

```text
当前 Provider 未配置可靠单价，提交前请手动核对平台费用。
```

## 14.12 切换聚合平台时的数据不受影响

更换 Provider 时，以下资产与数据必须保持不变：

```text
CH-Master
Costume-Asset
SC-Asset
SB-Shot
Storyboard Execution Page
VP-Block
版本管理与资产绑定
```

只需：

```text
新建 / 修改 Provider 配置
→ 对待提交任务重新执行 capability check
→ 重新生成 provider request payload
```

---

# 15. Provider 架构


## 14.1 Provider 原则

所有真实模型调用必须封装在 Provider 中，不得直接写入页面组件或业务页面。

## 14.2 Provider 类型

```text
OpenAITextMockProvider
OpenAIImageMockProvider
SeedanceMockProvider
SeedanceAggregatorGenericProvider
JimengCreditAssistProvider

OpenAITextProvider            后续启用
OpenAIImageProvider           后续启用
SeedanceAggregatorProvider    用户选定第三方平台后启用
SeedanceVolcengineProvider    官方备用通道，按需启用
```

## 14.3 需要预留的服务方法

### 文本 Provider

```python
analyze_script()
generate_director_options()
generate_shot_plan()
generate_character_scene_bind()
generate_consistency_check()
generate_vp_block()
validate_batch_video_tasks()
```

### 图像 Provider

```python
generate_character_master()
generate_costume_asset()
generate_scene_asset()
generate_storyboard_frame()
edit_asset_from_reference()
```

### 视频 Provider

```python
create_task()
get_task_status()
download_result()
cancel_task()
```

### 即梦辅助 Provider

```python
export_jimeng_package()
import_generated_video()
```

---

# 15. 数据库结构

## 15.1 表清单

```text
projects
episodes
scenes
shots
source_files

ucode_commands
ucode_execution_runs
workflow_checkpoints

characters
character_masters
costume_assets
character_scene_bindings
consistency_locks

scene_assets
prop_assets

storyboard_style_locks
axis_continuity_locks
axis_camera_positions
axis_cross_plans
storyboard_frames
storyboard_pages

vp_blocks
asset_bindings
version_records

batch_video_jobs
batch_video_tasks
video_provider_profiles
video_provider_capabilities
video_provider_model_mappings
video_provider_price_configs
provider_runs
cost_usage_logs
request_cache_records
```

## 15.2 重要字段

### `ucode_execution_runs`

```text
id
project_id
ucode_action          # start / plan / assets / storyboard / video_package / batch_video / one_click / check / fix
scope_code            # EP01 / EP01SC01 / EP01SC01_SH001_SH003
additional_request
status
result_summary
checkpoint_required
created_at
updated_at
```

### `axis_continuity_locks`

```text
id
project_id
scene_id nullable
sequence_id nullable
axis_type
axis_definition
screen_direction_json
camera_safe_side
movement_direction
validation_status
created_at
updated_at
```

### `axis_camera_positions`

```text
id
axis_lock_id
shot_id
camera_code
camera_position_note
screen_direction_note
is_axis_safe
```

### `storyboard_style_locks`

```text
id
project_id
scene_id nullable
style_name = "black_white_realistic_pencil_sketch"
is_enabled = true
reference_note
created_at
```

### `storyboard_frames`

```text
id
shot_id
asset_version
image_path
style_lock_id
style_validation_status
character_binding_id
scene_asset_version_id
status
created_at
```

### `storyboard_pages`

```text
id
scene_id
page_code
shot_ids
html_path
png_path
pdf_path
style_lock_id
status
created_at
```

### `batch_video_tasks`

```text
id
job_id
shot_id
provider_channel
status
character_master_version_id
costume_asset_version_id
scene_asset_version_id
storyboard_frame_version_id
vp_block_id
input_manifest_path
external_task_id
result_video_path
estimated_cost
actual_cost
retry_count
error_message
created_at
updated_at
```

### `video_provider_profiles`

```text
id
display_name
provider_type
is_enabled
is_default
base_url
create_task_path
get_task_path_template
cancel_task_path_template
auth_type
auth_header_name
auth_prefix
auth_env_key_name
config_json
created_at
updated_at
```

### `video_provider_capabilities`

```text
id
provider_profile_id
supported_models_json
generation_modes_json
supported_durations_json
supported_resolutions_json
supported_aspect_ratios_json
supports_audio_generation
supports_callback
supports_reference_images
max_reference_images
supports_reference_videos
supports_reference_audios
result_delivery
capability_source_note
verified_at
```

### `video_provider_price_configs`

```text
id
provider_profile_id
model_key
resolution
duration_seconds
generation_mode
price_value
price_unit
currency
source_note
verified_at
```

### `cost_usage_logs`

```text
id
provider
model_name
module_type
input_tokens
cached_input_tokens
output_tokens
image_quality
estimated_cost
task_id
created_at
```

---

# 16. 本地文件目录

```text
data/projects/{PROJECT_ID}/
├── 00_source/
│   ├── scripts/
│   └── references/
│       ├── storyboard_style/
│       ├── character_style/
│       └── scene_style/
├── 01_analysis/
│   ├── director_options/
│   ├── g_blocks/
│   └── s_blocks/
├── 02_characters/
│   ├── masters/
│   ├── costumes/
│   ├── state_assets/
│   └── bindings/
├── 03_scenes/
├── 04_storyboards/
│   ├── style_locks/
│   ├── frames/
│   └── pages/
├── 05_video_prompts/
├── 06_batch_video/
│   ├── seedance_api/
│   └── jimeng_credit_exports/
├── 07_results/
│   ├── generated_videos/
│   └── confirmed_clips/
└── 99_logs/
```

---

# 17. 环境变量文件

`.env.example`：

```env
# Application
APP_ENV=development
DATABASE_URL=sqlite:///./data/app.db
PROJECTS_ROOT=./data/projects
SYSTEM_PROMPT_FILE=./system-prompts/剧本视觉化创作系统_V7.0_Plus_R1_UCODE-9_FLOW-NAV_VP-PRECISION-18固定视频包模板版_完整主版本.txt

# Feature flags
ENABLE_REAL_OPENAI=false
ENABLE_REAL_SEEDANCE=false
ENABLE_JIMENG_CREDIT_ASSIST=true
ENABLE_UCODE_9=true
ENABLE_STORYBOARD_STYLE_LOCK=true
ENABLE_AXIS_CONTINUITY_LOCK=true

# OpenAI - do not commit real key
OPENAI_API_KEY=
OPENAI_MODEL_DIRECTOR=
OPENAI_MODEL_ROUTINE=
OPENAI_IMAGE_MODEL_PRODUCTION=gpt-image-2
OPENAI_IMAGE_MODEL_DRAFT=

# Seedance Video Provider
VIDEO_PROVIDER_MODE=mock
DEFAULT_VIDEO_PROVIDER_ID=seedance_mock

# Third-party Seedance Aggregator - configure only after choosing a provider
SEEDANCE_AGGREGATOR_API_KEY=
SEEDANCE_AGGREGATOR_BASE_URL=
SEEDANCE_AGGREGATOR_CREATE_TASK_PATH=
SEEDANCE_AGGREGATOR_GET_TASK_PATH_TEMPLATE=
SEEDANCE_AGGREGATOR_AUTH_TYPE=bearer
SEEDANCE_AGGREGATOR_AUTH_HEADER=Authorization
SEEDANCE_AGGREGATOR_AUTH_PREFIX=Bearer
SEEDANCE_AGGREGATOR_MODEL_ID=

# Optional official Volcengine fallback - fields must be verified against official docs
VOLCENGINE_API_KEY=
VOLCENGINE_BASE_URL=
VOLCENGINE_SEEDANCE_MODEL_ID=

# Cost controls
REQUIRE_VIDEO_BUDGET_CONFIRM=true
MAX_VIDEO_TASKS_PER_BATCH=3
```

---

# 18. V0.1 验收标准

## 18.1 Milestone 0 验收

```text
前端 localhost:3000 能打开
后端 localhost:8000/health 返回健康状态
SQLite 成功初始化
应用能显示 UCODE-9 当前系统主版本文件已载入
首页显示 9 个统一动作入口
左侧导航按“开始/规划、资产、故事板、视频包、批量视频、检查/修正、设置”显示
```

## 18.2 项目与资产验收

```text
能新建项目 / Episode / Scene / Shot
能上传剧本与参考图并保存本地
能创建 CH-Master / Costume-Asset / SC-Asset Mock 记录
能做版本确认 / 锁定 / 回滚
能保存 CH-Scene-Bind 与一致性检查状态
```

## 18.3 故事板验收

```text
故事板统一黑白草稿风格默认开启并显示启用状态
轴线连续性锁定默认开启，能保存 Axis ID 与三镜机位关系
能保存至少 3 张 Mock 黑白草稿镜头图
能程序合成 1 张正式 Storyboard Execution Page
执行页具备：黑底、白线、橙色功能重点、带 AXIS LINE / CAMERA SAFE SIDE 的俯视调度区域、信息栏、三镜头卡、底部三栏
能导出 PNG，PDF 可作为增强项
```

## 18.4 批量编排验收

```text
能通过 `V7｜批量视频` 创建视频任务队列
缺少资产或风格校验失败的镜头会 blocked
Mock Seedance 能模拟 submitted → processing → completed / failed
能创建至少一个“第三方 Seedance 聚合 API”Provider Profile，并填写能力声明、字段映射和价格配置（不发真实请求）
批量任务提交前能基于 Provider Capability 判断 ready / blocked
切换默认 Provider 后，既有资产和故事板数据不丢失，只重新生成待提交请求映射
即梦辅助通道能导出每镜资料包
导回视频时能关联正确 Shot ID
```

## 18.5 成本控制验收

```text
设置页显示 Provider 与 Mock 状态
存在视频预算确认按钮
未确认预算时禁止真实视频提交
请求缓存表、成本日志表已建立
真实 API 未开启时绝不产生费用
```

---

# 19. Codex 开发里程碑

## Milestone 0｜脚手架、系统规则载入与 UCODE-9 首页

```text
前后端脚手架
/health
SQLite 初始化
system-prompts 中 UCODE-9 主文件载入状态
首页 9 个统一动作卡
左侧简化导航
.env.example
AGENTS.md
中文 README
```

不接真实 API，不做复杂生成。

## Milestone 1｜项目、场次、镜头与 UCODE 执行记录

```text
项目 CRUD
Episode / Scene / Shot 数据
素材上传保存
项目目录自动建立
UCODE 命令输入框
ucode_execution_runs 与 workflow_checkpoints
```

## Milestone 2｜`V7｜资产` 后台能力与版本管理

```text
人物母版 Mock 数据与占位图
服装派生 Mock 数据与占位图
场景资产 Mock 数据与占位图
场次绑定与人物一致性记录
版本确认 / 锁定 / 回滚
```

## Milestone 3｜`V7｜故事板`、风格锁定与轴线连续性

```text
黑白草稿故事板风格状态
Axis ID、允许机位侧、运动方向和镜头机位数据
单镜头 Mock 黑白故事板图
Storyboard Execution Page HTML/CSS 模板
带轴线信息的 TOP-DOWN BLOCKING DIAGRAM 区域
PNG 导出
```

## Milestone 4｜`V7｜视频包`、`V7｜批量视频` 与 Provider 兼容层 Mock

```text
逐镜视频资料数据
自动资产与轴线校验
批量任务列表
统一 Canonical Video Request
SeedanceMockProvider
SeedanceAggregatorGenericProvider 配置结构（只保存 / 验证，不发真实请求）
Provider Capability Profile 与字段映射界面
即梦积分辅助资料包导出 / 视频导入
```

## Milestone 5｜`V7｜检查`、`V7｜修正`、`V7｜一键` 与 OpenAI 最小接入

```text
统一检查报告
指定问题修正并新建版本的流程
一键推进与人工确认闸门
只接一个低风险、可控的小任务
文本 Provider 与图像 Provider
缓存键与成本日志
禁止批量真实调用
```

## Milestone 6｜第三方 Seedance 2.0 聚合 API 最小接入

```text
由用户确定目标第三方聚合平台并提供其官方 API 文档
基于通用 Provider 或新增专属 Adapter 接入
验证鉴权、模型 ID、任务创建、查询状态、结果下载、失败处理和单价配置
Provider 能力检查与预算确认闸门
仅测试 1 个短镜头
本地保存结果视频与原始响应快照
```

---


# 20. 写入 AGENTS.md 的 Codex 规则

```text
1. 产品依据是 docs/ 下的本需求文档与 system-prompts/ 下的 UCODE-9 当前主版本 TXT。
2. 用户交互层只展示 UCODE-9 的 9 个主动作，不把旧技术码重新暴露为主入口。
3. 旧模块名称可作为后台能力和数据结构使用，但 README 与用户界面优先使用通俗名称。
4. 开发必须按 Milestone 顺序推进；未经用户确认，不启动下一里程碑。
5. V0.1 默认使用 Mock Provider；不得擅自调用真实付费 API。
6. 任何密钥不得写进代码、日志、截图或提交记录。
7. 所有资产必须版本化，禁止覆盖 confirmed_current 或 locked 资产。
8. 人物换装不得改变已确认人物的脸、年龄、骨相、体型、身高与身份气质。
9. 所有正式故事板必须为黑白灰写实铅笔草稿风格，禁止彩色故事板混入。
10. 同一场戏 / 连续剧情中的正式故事板必须通过轴线连续性校验，禁止无计划跳轴。
11. Storyboard Execution Page 的文字、编号、框线、Axis 信息与栏目由程序准确排版，不交给图像模型生成最终文字。
12. 正式视频提交前必须经过资产、故事板、轴线、Provider 能力、预算确认检查。
13. Seedance 必须使用 Provider Adapter 架构，不得把任一聚合平台字段硬编码进业务页面。
14. 即梦订阅积分通道只实现资料包导出和结果导入；无官方授权不开发自动网页提交。
15. 每次交付列出：完成内容、修改文件、启动命令、测试方法和未完成内容。
16. README 与用户可见界面使用中文，保证初学者能操作。
```

---


# 21. 第一轮直接发给 Codex 的任务指令

```text
你现在帮助我开发一个本地运行的“AI导演工作台”Web 应用。我是不懂代码的初学者，请用清楚、分步骤、能直接测试的方式工作。

请先完整阅读：
1. docs/AI导演工作台_V0.1_开发需求文档_Codex版_R4_UCODE-9.md
2. system-prompts/剧本视觉化创作系统_V7.0_Plus_R1_UCODE-9_FLOW-NAV_VP-PRECISION-18固定视频包模板版_完整主版本.txt
3. AGENTS.md

本轮只执行 Milestone 0：脚手架、系统规则载入与 UCODE-9 首页。

硬性要求：
- 不连接真实 OpenAI API。
- 不连接真实 Seedance API 或任何第三方聚合平台 API。
- 不实现即梦网页自动操作。
- 不产生任何付费调用。
- 技术栈固定为 React + Vite + TypeScript + Tailwind CSS 前端，Python FastAPI + SQLModel + SQLite 后端。
- 首页创建 9 个动作入口：开始、规划、资产、故事板、视频包、批量视频、一键、检查、修正。
- 左侧导航创建：项目首页、开始/规划、资产、故事板、视频包、批量视频、检查/修正、成本与设置。
- 后端提供 /health 接口。
- 后端能读取并返回 system-prompts/ 中 UCODE-9 主版本 TXT 的文件名和加载状态，但不返回系统全文。
- 创建 .env.example，不写入真实密钥。
- 创建中文 README，说明如何安装依赖、启动前端、启动后端、打开页面和验证 /health。
- 创建 AGENTS.md 约束后续开发行为。
- 预留后续可配置 Provider Adapter 目录；本轮不实现真实调用。

完成后请：
1. 列出创建或修改的文件。
2. 给出我在终端依次复制运行的命令。
3. 告诉我浏览器打开哪个地址。
4. 告诉我应该看到哪些内容表示 Milestone 0 成功。
5. 运行最基本的测试或启动验证。
6. 在我确认前，不要继续 Milestone 1。
```

---


# 22. 接入真实 API 时的核对事项

## 22.1 OpenAI

接入时只依据官方文档核查：

```text
当前可用文本模型名称与价格
Responses API 的结构化输出方式
GPT Image 的图像输入 / 输出与编辑方式
Prompt Caching 的实际日志字段
Batch 是否适用于准备批处理的任务
```

## 22.2 Seedance 2.0 第三方聚合 Provider

接入真实视频生成前，用户需先选择目标聚合平台，并提供该平台当时有效的 API 文档与价格页。开发时必须逐项核查：

```text
平台名称与服务可用性
模型 ID / Fast 或标准档位
鉴权方式与 Base URL
任务创建路径
异步查询 / Callback 回调方式
素材输入限制：首帧、首尾帧、多参考图、参考视频、参考音频
生成音频、分辨率、时长、画幅与 seed 支持情况
视频结果 URL 有效期与本地下载要求
价格、币种、计费单位与失败是否扣费
并发、限流、失败重试和退款规则
内容审核及商用使用条款
```

规则：

```text
任何第三方平台配置都只存在 Provider 层；
Provider 不支持的功能必须在批量队列中标记 blocked；
不得静默删除关键资产后继续提交生成。
```

## 22.3 火山方舟官方 Provider（可选备用）

若后续启用官方通道，则严格依据火山方舟当时的官方文档核查创建任务、查询任务、结果下载、素材能力、价格与限流规则，不与第三方 Provider 字段混用。

---

# 23. 最终原则

这不是一个“把提示词塞进聊天框”的小工具，而是一个可持续生产的导演资产工作台。

必须坚持：

```text
用户只面对 UCODE-9 的九个清晰动作
OpenAI 负责理解、规划与视觉资产生成
本地应用负责数据、版本、准确排版、轴线连续与批量队列
可配置的 Seedance 2.0 Provider 负责正式视频生成（第三方聚合平台为主，官方 Provider 可选备用）
即梦积分模式先作为手动辅助通道
所有故事板严格保持统一黑白草稿导演风格，并禁止无计划跳轴
关键资产与视频任务必须可追溯、可确认、可回滚
```
