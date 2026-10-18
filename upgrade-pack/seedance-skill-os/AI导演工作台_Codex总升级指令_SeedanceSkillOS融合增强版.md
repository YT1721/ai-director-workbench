# Codex 总升级指令｜AI导演工作台接入 Seedance 2.0 Skill OS 融合增强版

你现在直接升级本地项目「AI导演工作台」。不要再要求我做 A/B 测试或手工验证。请完成代码集成、自动校验和迁移报告。

## 0. 本轮目标

将最新系统主文件：

```text
剧本视觉化创作系统_V7.0_Plus_R1_SeedanceSkillOS融合增强版.txt
```

替换为项目当前主版本，并把 `Emily2040/seedance-2.0` 作为 Seedance 专项后台能力接入。

架构必须保持：

```text
V7 Orchestrator
= 上层导演总控、UCODE-9、FLOW-NAV、资产、故事板、VP-PRECISION-18、Video Unit

Seedance Skill Adapter
= Seedance专项路由、导演推导、提示词编译、连续状态、成片复盘

Provider Adapter
= 真实生成API、任务状态、成本和结果下载
```

第三方 Skill 不得覆盖 V7 主系统。

---

## 1. 系统主文件

将新文件复制并覆盖：

```text
system-prompts/剧本视觉化创作系统_V7.0_Plus_R1_当前主版本.txt
```

将旧主文件归档：

```text
system-prompts/archive/
```

系统设置页显示：

```text
V7.0 Plus R1｜Seedance Skill OS 融合增强版
```

只展示文件名、版本、更新时间、字符数和校验状态，不展示完整系统正文。

---

## 2. 固定并引入上游 Skill 源码

上游仓库：

```text
https://github.com/Emily2040/seedance-2.0
```

固定到已审核提交：

```text
57d01dc66f93ecb03c2475be5f22dc416d9b701d
```

导入到：

```text
vendor/seedance-20/
```

同时让 Codex 开发环境能够发现：

```text
.agents/skills/seedance-20/
```

优先使用软链接或同步脚本，避免维护两份漂移副本。

新增：

```text
vendor/seedance-20/VENDOR_VERSION.md
third_party/seedance-20/LICENSE
THIRD_PARTY_NOTICES.md
scripts/sync_seedance_skill.py
```

`VENDOR_VERSION.md` 记录：

```text
upstream_repo
upstream_commit
upstream_version
import_date
local_patch_status
license
```

不得自动追踪 main。更新必须显式执行同步命令并生成差异报告。

---

## 3. 不得改变的现有核心功能

完整保留：

```text
UCODE-9
FLOW-NAV
DIRECTOR-TECH PLUS
VP-PRECISION-18
UNIFIED-SB
IMAGE-STYLE-LOCK
故事板图1、图2唯一默认风格
人物角色卡图3、图4唯一默认风格
Seedance 15秒 Video Unit
Video Unit 1:1绑定
Shot层导演意图保护
AXIS-CONTINUITY-LOCK
即梦编排器辅助模式
真实Provider确认机制
取消Mock
```

不得重新引入旧版黑底故事板、深色UI故事板或其他人物卡风格。

---

## 4. 新增 SeedanceSkillAdapter

新增服务：

```text
app/services/seedance_skill_adapter.py
```

职责：

```text
1. 按当前任务读取 vendor/seedance-20 中必要的 Skill / Reference。
2. 实施渐进加载，不得一次加载整个仓库。
3. 输出结构化能力结果给 V7 Orchestrator。
4. 不允许第三方 Skill 修改 UCODE 流程、图片风格和内部数据。
5. 不把 Skill 原文直接返回前端。
6. 平台价格、模型ID、时长和API字段只能作为参考，不写入运行时真相。
```

建议提供：

```python
resolve_modules(context) -> list[SkillModule]
load_module_content(module_ids) -> SkillBundle
build_seedance_guidance(context) -> SeedanceGuidance
```

---

## 5. UCODE 到 Skill / Reference 路由

### V7｜开始

加载：

```text
directing-engine
seedance-interview-short
seedance-interview
pro-filmmaking-standards（商业片、客户项目时）
```

输出并保存：

```text
scene_function
scene_turn
pov_character
power_shift
subtext
felt_intent
directorial_voice
```

### V7｜规划

加载：

```text
seedance-sequence
sequence-project-state
event-density
allocation-model
shot-list-continuity
```

输出并保存：

```text
scene_map
story_spine
arc_position
beats
already_happened
this_unit_only
reserved_for_later
primary_spend
secondary_spend
```

### V7｜资产

加载：

```text
seedance-characters
reference-workflow
reference-transfer-contract
```

输出：

```text
reference_role_map
canonical_state
transient_state
must_transfer
must_not_transfer
```

### V7｜故事板

加载：

```text
dense-storyboard-mode
multishot-grammar
cinematography-shot-language
```

注意：

```text
这些模块只决定镜头结构和事件密度。
故事板视觉仍严格由 UNIFIED-SB + IMAGE-STYLE-LOCK 控制。
```

### V7｜视频包

加载：

```text
seedance-prompt
seedance-prompt-short
seedance-camera
seedance-motion
seedance-lighting
seedance-characters
seedance-style
seedance-vfx
seedance-audio
seedance-vocab-zh
seedance-antislop
prompt-compiler
surface-prompt-profiles
```

### V7｜检查

加载：

```text
retake-protocol
continuity-qc
project_state_check
continuity_chain_check
delivery-qc（进入交付阶段时）
```

### V7｜修正

加载：

```text
seedance-troubleshoot
failure-atlas
model-mechanics
retake-protocol
```

### 版权 / 品牌 / 真人 / 声音风险

加载：

```text
seedance-copyright
seedance-filter
```

### 类型方案和示例

按需加载：

```text
seedance-recipes
genre-guides
examples-by-mode
seedance-examples-zh
directing-engine-genre-library
```

### API / Provider / 工作流

加载：

```text
seedance-pipeline
api-workflow
model-name-map
platform-surface-matrix
```

### 后期和商业交付

按项目阶段加载：

```text
aspect-ratio-delivery
color-pipeline-aces
audio-post-delivery
subtitles-localization
delivery-qc
```

不要把上述模块做成用户必须逐项选择的菜单。后台自动路由，前端只展示结果和关键原因。

---

## 6. 新增 Directing Engine 数据

新增模型或字段：

```text
scene_function
scene_turn
pov_character
audience_position
power_map
power_shift
subtext
felt_intent
directorial_voice
arc_position
is_pattern_break
```

`felt_intent` 只能作为内部导演目标，不允许直接以抽象情绪词提交给模型。Prompt Compiler 必须将其转译成：

```text
可见行为
镜头距离和运动
物理光源
声音密度
动作终点
```

---

## 7. 保留 VP-PRECISION-18，新增 Prompt Compiler

不得删减 VP-PRECISION-18。

新增：

```text
app/services/seedance_prompt_compiler.py
```

输入：

```text
vp_precision_18
video_unit
project_state
reference_role_map
continuity_bridge
surface_profile
director_intent
```

输出：

```text
vp_prompt_full
vp_prompt_copy
reference_tag_map
preserved_constraints
removed_redundancy
prompt_budget_report
compile_warnings
```

规则：

```text
vp_prompt_full = 内部完整导演生产规格
vp_prompt_copy = 实际提交当前Provider的紧凑自然语言提示词
```

编译顺序：

```text
Provider模式
→ 参考标签与职责
→ 实际开场状态
→ 本Unit动作
→ 导演意图的可见化表达
→ 镜头/光线/声音
→ 连续性锁定
→ 禁止重演与禁止提前
→ 终点和尾帧
→ Anti-Slop压缩
```

若参考图或视频已携带状态，不在文字中重复重绘。

---

## 8. 新增项目事实状态

建立或扩展：

```text
app/models/project_state.*
app/schemas/director_project_state.schema.json
```

项目层：

```text
schema_version
state_revision
canon_revision
project_id
surface_profile
story
world_bible
reference_registry
scenes
beats
video_units
take_history
current_video_unit_id
updated_at
```

Scene：

```text
scene_id
scene_index
narrative_function
arc_position
location
time_of_day
anchor_source
max_chain_depth
audio_plan
assigned_unit_ids
transition_out
status
```

Video Unit：

```text
video_unit_id
previous_unit_id
scene_id
sequence_index
unit_goal
felt_intent
generation_mode
shot_structure
already_happened
this_unit_only
reserved_for_later
planned_start_state
planned_end_state
observed_start_state
observed_end_state
continuity_locks
allowed_changes
continuity_breaks
accepted_deviations
transition_in
transition_out
open_motion_vectors
extension_depth
status
```

状态优先级：

```text
accepted observed state
> 用户确认修正
> planned state
```

状态更新必须增加：

```text
state_revision
canon_revision
```

---

## 9. Reference Role Map

每个资产新增：

```text
asset_id
provider_tag
primary_role
canonical_or_transient
must_transfer
must_not_transfer
authorization_status
version
```

角色枚举：

```text
identity
product
costume
environment
first_frame
last_frame
motion
camera
timing
audio
style
continuation_source
```

内部标签与Provider标签分离：

```text
asset_123
→ 即梦 @图片1
→ 国际表面 @Image1
```

由 Provider Adapter 按当前 Surface Profile 编译。

---

## 10. Video Unit 结构类型

新增：

```text
compact_single_take
phased_single_take
dense_multishot
first_last_frame_transition
video_edit_contract
```

规则：

```text
连续镜头使用 Beginning / Then / Finally，不使用 Shot N 硬切。
只有Provider明确支持一次生成内剪辑时才使用 dense_multishot。
15秒 dense_multishot 默认不超过2–3个镜头，每镜一个动作和一个终点。
能力未知时默认单镜头或分阶段连续镜头。
```

Video Unit 继续保持：

```text
≤15秒
1页故事板
1张参考图
1份VP-PRECISION-18
1份vp_prompt_copy
1次生成任务
1个资料包
```

---

## 11. Event Density 与 Allocation Model

新增服务或规则：

```text
app/services/event_density_service.py
app/services/fidelity_allocation_service.py
```

每个 Unit 必须产生：

```text
already_happened
this_unit_only
reserved_for_later
primary_spend
secondary_spend
economized_elements
split_recommendation
```

primary_spend：

```text
identity_fidelity
motion_boldness
scene_density
```

若三项同时高，必须拆分，不允许靠堆叠提示词解决。

---

## 12. Continuation Handoff

新增：

```text
app/services/continuation_service.py
app/services/take_observation_service.py
```

导入成片后流程：

```text
1. 保存视频。
2. 提取首帧和尾帧。
3. 读取画面可见状态。
4. 完整视频可读取动作、运镜和声音阶段。
5. 尾帧只询问静帧无法判断的信息。
6. 用户确认成片裁决。
7. accepted / accepted_with_deviation 更新 canon。
8. 编译下一 Unit。
```

允许类型：

```text
seamless_continuation
intentional_next_shot
bridge_between_known_states
repair_tail
reanchor_after_drift
```

跨场景默认 intentional_next_shot，并从原始母版重新锚定。

默认连续输出衍生深度：

```text
2
```

硬上限：

```text
3
```

出现身份、产品、空间或动作漂移时提前 reanchor。

---

## 13. 适配上游脚本

可以复用或重构：

```text
scripts/extract_last_frame.py
scripts/continuity_chain_check.py
scripts/project_state_check.py
schemas/project-state.schema.json
```

要求：

```text
保留MIT版权与许可证。
优先提取核心函数到应用服务层。
不得在业务代码中拼接不安全shell命令。
ffmpeg路径可配置。
所有文件路径做白名单和存在性校验。
```

不进入产品运行时：

```text
validate_skills.py
content_audit.py
design_audit.py
source_registry_check.py
vocab_schema_check.py
eval_schema_check.py
```

这些可以保留在 vendor 中，但不接业务接口。

---

## 14. Take Review 与重拍经济

新增：

```text
app/services/take_review_service.py
```

裁决：

```text
keep
fix_in_post
edit
reroll
rewrite
```

记录：

```text
take_id
video_unit_id
changed_variable
seed
provider
model
cost
verdict
evidence
accepted_deviations
next_action
```

规则：

```text
每次只改一个主要变量。
同类问题连续两次必须rewrite或拆分。
rejected不得成为下一Unit来源。
fix_in_post不得浪费生成次数。
生成前保存attempt_budget和good_enough标准。
```

---

## 15. Surface Profile

新增：

```text
app/models/surface_profile.*
app/services/surface_profile_service.py
```

字段：

```text
provider
surface_name
model_id
verification_date
duration_range
prompt_budget
reference_tag_convention
supported_modes
reference_limits
first_last_frame_support
edit_support
extend_support
audio_behavior
resolution
aspect_ratios
region
pricing
authorization_requirements
known_constraints
```

运行时真相只能来自：

```text
用户Provider配置
当前官方文档
连接测试
真实API响应
```

vendor Skill 中的价格、模型ID和接口信息不得自动写入生产配置。

---

## 16. Provider 与真实生成安全

继续取消 Mock。

提交真实生成前必须展示：

```text
Provider
Surface Profile验证日期
模型
模式
Unit数量
时长
分辨率
比例
参考资产与角色
预计成本
attempt_budget
失败处理策略
```

只有用户点击真实提交确认后才能调用 Provider。

默认：

```text
MAX_VIDEO_TASKS_PER_BATCH=1
```

连续单元也逐个接受后再生成下一条，除非用户明确关闭该安全门。

---

## 17. 前端最小必要升级

不要重构整个UI，只增加有实际价值的区域。

### Video Unit 详情

新增标签页或折叠区：

```text
导演读取
生成预算
参考角色
完整视频包
编译提示词
连续状态
Take Review
```

### 编译提示词区

显示：

```text
vp_prompt_copy
字符数 / 预算
被删除的重复信息
保留的关键约束
参考标签映射
警告
```

### 成片导入区

支持：

```text
上传生成视频
提取首尾帧
显示 observed_end_state
选择裁决
确认接受偏差
生成下一Unit
```

### 状态看板

新增：

```text
state_revision
canon_revision
current_video_unit
parent_unit
extension_depth
next_unit_readiness
```

---

## 18. 导出包升级

每个 Video Unit 导出：

```text
storyboard_frame.png
storyboard_page.png
vp_prompt_full.txt
vp_prompt_copy.txt
vp_precision_18.json
video_unit_meta.json
continuity_bridge.json
director_technique.json
meaning_chain.json
storyboard_grid.json
unified_sb_meta.json
reference_role_map.json
project_state_snapshot.json
surface_profile_snapshot.json
prompt_compile_report.json
take_review_template.json
copy_card.md
import_result_here/
```

---

## 19. 自动校验与测试

用户不做手工测试，但代码必须自检。

新增自动测试：

```text
VP-PRECISION-18仍为18项
Video Unit时长不超过15秒
故事板与提示词ID和时间范围一致
completed/current/reserved互不重叠
rejected不能成为parent
accepted必须有observed_end_state
continuation没有来源时被阻止
extension_depth超过上限被阻止
Provider标签按Surface Profile编译
参考资产must_not_transfer被保留
vp_prompt_copy不是JSON，不是18项机械拼接
IMAGE-STYLE-LOCK未被第三方Skill覆盖
Mock入口不存在
```

运行项目现有测试、类型检查、Lint和构建。修复本轮引入的问题，不把历史无关警告伪装成本轮失败。

---

## 20. 完成后必须回复

```text
1. 系统主文件替换结果
2. 固定的上游版本和提交
3. vendor与.agents安装位置
4. 新增和修改的文件
5. UCODE到Skill的实际路由
6. Directing Engine数据如何落库
7. VP-PRECISION-18如何编译成vp_prompt_copy
8. Project State和Canon如何更新
9. Reference Role Map如何工作
10. Continuation Handoff如何工作
11. Take Review如何工作
12. Surface Profile如何避免过时数据
13. 旧版风格是否仍彻底停用
14. Mock是否仍彻底停用
15. 自动测试、Lint和构建结果
16. 数据迁移与回滚方式
17. 当前仍需用户提供的真实Provider配置
```

不要仅回复“已完成”。必须给出具体文件、数据库迁移、测试结果和未完成项。

---

## 21. 严格禁止

```text
不要用Seedance Skill OS替换V7
不要删除VP-PRECISION-18
不要改变故事板和人物卡统一风格
不要一次加载整个vendor仓库到模型上下文
不要把上游价格和模型ID当成运行时真相
不要自动跟随main更新
不要恢复Mock
不要虚构API成功
不要自动登录即梦
不要未经确认批量消耗积分
不要在上一Unit未接受时最终化下一连续Unit
```
