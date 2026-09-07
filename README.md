# laoke-sql-analyst · SQL 数据分析助手

> 局内人·老K · 专注实体老板 AI 落地实战

把自然语言需求转成可运行的 SQL，配套方言速查、查询优化、窗口函数与注入防范方法论，并内置一个纯标准库的静态检查器 `sql_lint.py`，在执行前拦住 SELECT 星号、删改无 WHERE、笛卡尔积、SQL 注入这些最致命的写法。

## 这个 Skill 能做什么

- **自然语言转 SQL**：业务问题 → 带注释的可运行查询（筛选/聚合/JOIN/分页）。
- **解释与优化**：讲清 SQL 在算什么、慢在哪、怎么改。
- **静态检查**：`scripts/sql_lint.py` 扫描 SELECT 星号、DELETE/UPDATE 无 WHERE、括号不匹配、笛卡尔积、注入特征、方言不兼容。
- **方言适配**：MySQL / PostgreSQL / SQL Server / BigQuery 差异对照与改写。
- **进阶套路**：窗口函数、CTE、每组取 TopN、去重留最新。

## 快速开始

```bash
# 检查一段 SQL
python scripts/sql_lint.py --input query.sql

# JSON 输出（接 CI）
python scripts/sql_lint.py --input query.sql --json

# 脚本自检
python scripts/sql_lint.py --selftest
```

## 目录结构

- `SKILL.md` —— 完整使用说明与方法论
- `references/` —— SQL 方言速查 / 查询优化 / 窗口函数与 CTE / 常见反模式 / 安全与注入防范（5 篇）
- `scripts/sql_lint.py` —— 纯标准库静态检查器
- `hooks/guardrail.md` —— 合规护栏

## 相关资源

- ima 知识库《局内人·老K · AI 落地实战库》：收录 WorkBuddy 实战案例 200+，大量「自然语言转工具/脚本」实战思路
- 作者落地页：https://muzhi-888.github.io/ju-nei-ren-lao-k/
- SkillHub 作者主页：搜索「局内人·老K」

## License

MIT —— 可自由使用、修改、再分发，请保留作者署名。

## 免责声明

本工具仅供学习与研究使用，只产出 SQL 文本，执行动作由你在授权环境完成。生成内容不构成任何投资、法律或商业建议；查询生产数据请遵守最小权限、审批与脱敏规范，严禁用于未授权访问或注入攻击。
