# 贡献指南

感谢你想让这个项目更好。

## 开发环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web install
cp .env.example .env
```

启动方式见 [README](./README.md) 的「快速开始」。

## 提交前必做

仓库配置了 pre-commit 钩子，会用 prettier 校验格式。提交被拦截时执行：

```bash
git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(js|jsx|ts|tsx|json|css|scss|md|html|yaml|yml)$' | xargs prettier --write
```

**请不要用 `--no-verify` 跳过钩子。**

以下三项检查必须全绿：

```bash
pytest apps/api/tests
npm --prefix apps/web test
npm --prefix apps/web run build
```

## 提交信息

使用 Conventional Commits：

```text
feat: 新增 xxx
fix: 修复 xxx
docs: 更新 xxx
chore: 调整 xxx
```

## 绝对不要做的事

- **不要提交密钥**。任何时候不要把 `.env`、API Key、Token 提交进来。`.env` 已在 `.gitignore` 中，提交前请自查 `git status`。
- **不要伪造 AI 结果**。本项目的一条底线是不用占位数据冒充真实模型产出，请勿引入破坏这条原则的代码。
- **不要直接改 `vendor/seedance-20/`**。它是固定版本的第三方只读副本，需要同步时用 `scripts/sync_seedance_skill.py`。

## 提 Issue

请说明：操作系统、Python 与 Node 版本、复现步骤、期望与实际结果。

欢迎提交的缺失项：**界面截图与演示视频**（`docs/screenshots/`）、**README 英文版**、任何你实际用起来别扭的地方。

## License

贡献即表示你同意本项目以 [MIT](./LICENSE) 许可发布。
