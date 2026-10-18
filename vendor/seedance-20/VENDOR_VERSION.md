# Seedance 2.0 Skill OS 固定版本

- 上游仓库：`https://github.com/Emily2040/seedance-2.0`
- 固定提交：`57d01dc66f93ecb03c2475be5f22dc416d9b701d`
- 集成用途：为 AI导演工作台提供按需加载的导演、提示词编译、连续性和审片知识模块
- 集成方式：作为第三方只读能力库，由 `SeedanceSkillAdapter` 按任务加载，不整体注入系统提示词
- 运行时约束：上游文档中的模型名、价格与接口字段仅作知识参考，不作为生产 Provider 配置

更新本目录时必须使用 `scripts/sync_seedance_skill.py`，并显式传入提交哈希。禁止跟踪上游默认分支。
