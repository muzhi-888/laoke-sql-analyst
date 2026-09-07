---
name: laoke-sql-analyst
slug: laoke-sql-analyst
displayName: SQL 数据分析助手
version: 1.0.0
author: 局内人·老K
description: 通用 SQL 数据分析助手，把自然语言转成可运行 SQL，配套方言速查查询优化窗口函数与注入防范方法论，并内置纯标准库静态检查器扫描 SELECT 星号删改无 WHERE 笛卡尔积与注入风险
compatibility: 通用（支持 Skill 的 Agent：Claude Code / CodeBuddy / DeepSeek / WorkBuddy 等）
permissions: 读取表结构与自然语言需求、生成并解释 SQL、运行内置 sql_lint.py 做静态检查、输出 SQL 模板与检查报告
safety: 仅用于合法合规的数据查询分析与 SQL 编写辅助；内置护栏硬拒未授权访问、构造注入攻击、裸破坏性操作与造假请求
---

# SQL 数据分析助手

> 这个 Skill 是给「想从数据库里捞数、但写 SQL 总踩坑、或者担心写出危险语句」的人配的 SQL 搭档。它把你的自然语言需求（「上个月每个地区的销售额是多少」）转成可运行的 SQL，配套一套方言速查、查询优化、窗口函数、注入防范的方法论，并内置一个纯标准库的静态检查器 `sql_lint.py`，能在你执行前拦住 SELECT 星号、删改无 WHERE、笛卡尔积、SQL 注入这些最致命的写法。不止「写得出」，更帮你「写得对、写得安全」。
> 适用对象：数据分析师、运营/产品/财务要自己捞数的人、后端写查询的工程师、正在学 SQL 的入门者、要把 SQL 接进 BI / Agent 的团队。

---

## 一、这个 Skill 能干什么（能力边界）

**能做：**
1. 自然语言转 SQL：把业务问题写成可运行查询，支持筛选、聚合、分组、排序、分页、多表 JOIN（见 references/01~03）。
2. 解释 SQL：把一段陌生 SQL 用大白话讲清它在算什么、慢在哪、有没有坑。
3. 静态检查：用 `sql_lint.py` 扫描 SELECT 星号、DELETE/UPDATE 无 WHERE、括号不匹配、笛卡尔积、注入特征、方言不兼容（见 references/04、references/05）。
4. 方言适配：MySQL / PostgreSQL / SQL Server / BigQuery 的差异对照与改写（见 references/01）。
5. 优化建议：索引、执行计划、避免全表扫描、深分页等（见 references/02）。
6. 进阶套路：窗口函数、CTE、每组取 TopN、去重留最新等（见 references/03）。
7. 合规护栏：内置 `hooks/guardrail.md`，硬拒未授权访问、构造注入、裸破坏性操作、造假。

**不能做（护栏）：**
- 不能连库执行、不能替你跑生产查询（只产出 SQL 文本，你来执行）。
- 不能构造注入攻击、不能裸删裸改（无 WHERE/无事务的 DROP/DELETE 会被拦）。
- 不能伪造数据、不能扒未授权数据。
- 不替你做业务判断：查询对不对、口径准不准，仍需你复核。

---

## 二、核心工作流（四步走）

```
业务问题 ──▶ ① 给表结构 + 需求 ──▶ ② 生成 SQL
                                  │
                                  ▼
                          ③ 跑 sql_lint.py 检查
                                  │
                          ┌───────┴───────┐
                       有问题            没问题
                          │                │
                     ④ 改到干净        执行 / 接 BI / 喂 Agent
```

1. **提供上下文**：表结构（DDL 或字段清单）+ 你的数据库类型（MySQL/PG/...）+ 明确需求。
2. **生成 SQL**：本 Skill 产出带注释的查询，关键逻辑逐段说明。
3. **静态检查**：把 SQL 存成 `.sql` 跑 `sql_lint.py`，消灭红线问题。
4. **收口**：干净后你来执行，或接入 BI / Agent 上下文。

---

## 三、详细使用步骤

### 场景 A：自然语言 → 可运行 SQL

**第 1 步：给上下文**
告诉我：
- 数据库类型（MySQL 8 / PostgreSQL 15 / SQL Server / BigQuery）
- 相关表结构，例如：
  ```sql
  CREATE TABLE orders (
    id INT, user_id INT, amount DECIMAL(10,2),
    status VARCHAR(20), created_at DATETIME
  );
  CREATE TABLE users (
    id INT, city VARCHAR(50), reg_date DATE
  );
  ```
- 需求：「查 2026 年 8 月各城市付费用户数和下单总额，按总额降序，取前 10」

**第 2 步：本 Skill 产出**
```sql
SELECT
  u.city,
  COUNT(DISTINCT o.user_id) AS paid_users,   -- 付费用户数（去重）
  SUM(o.amount)            AS total_amount  -- 下单总额
FROM orders o
JOIN users  u ON u.id = o.user_id           -- 关联用户拿城市
WHERE o.status = 'paid'
  AND o.created_at >= '2026-08-01'
  AND o.created_at <  '2026-09-01'
GROUP BY u.city
ORDER BY total_amount DESC
LIMIT 10;
```
并解释：为什么用 `COUNT(DISTINCT user_id)`（一个用户可能多单）、为什么 `created_at` 用半开区间（含边界不漏不重）、JOIN ON 的字段要对齐类型。

**第 3 步：检查**
```bash
python scripts/sql_lint.py --input query.sql
```
若报 `NO_LIMIT` 之类 INFO，按需补 LIMIT（本例已 LIMIT 10，干净）。

### 场景 B：检查一段可疑 SQL（上线前门禁）

把别人/自己写的 SQL 存 `doubt.sql`，跑：
```bash
python scripts/sql_lint.py --input doubt.sql --json
```
JSON 输出便于接 CI / 自动化卡点。ERROR 级（DML 无 WHERE、注入、括号错）必须修。

### 场景 C：方言迁移（MySQL → PostgreSQL）

贴一段 MySQL SQL，本 Skill：
1. 用 `sql_lint.py` 标出不兼容（`DIALECT_BACKTICK` / `DIALECT_FN` 等 INFO）。
2. 按 references/01 改写：`` `col` `` → `"col"`、`GROUP_CONCAT` → `STRING_AGG`、`IF()` → `CASE`、`` NOW() `` 两库通用保留。

### 场景 D：把 SQL 接进 Agent / BI

- BI：把干净 SQL 存为视图或报表数据源，注释即文档。
- Agent：把 SQL + 表结构 + 字段含义拼进 prompt，让 Agent 基于「真实表结构」生成新查询，避免幻觉（见第十五节）。

---

## 四、sql_lint.py 调用详解

```bash
# 检查文件
python scripts/sql_lint.py --input query.sql

# 管道输入
cat query.sql | python scripts/sql_lint.py

# JSON 输出（接 CI / 自动化）
python scripts/sql_lint.py --input query.sql --json

# 脚本自检（验证脚本完好）
python scripts/sql_lint.py --selftest
```

报告格式（文本）：
```
共 3 条发现 — ERROR:1 WARN:1 INFO:1
[ERROR] DML_NOWHERE (L3): DELETE 缺少 WHERE 条件，将删除全表数据！...
[WARN] SELECT_STAR (L7): 使用了 SELECT *，建议显式列出所需列...
[INFO] NO_LIMIT (L10): 顶层 SELECT 未加 LIMIT/TOP...
```

覆盖的规则（rule 号）：
| 规则 | 级别 | 含义 |
|---|---|---|
| SELECT_STAR | WARN | 用了 SELECT * |
| DML_NOWHERE | ERROR | DELETE/UPDATE 无 WHERE |
| PAREN | ERROR | 括号不匹配 |
| CARTESIAN | WARN | 逗号连表无条件（笛卡尔积风险） |
| INJECTION_TAUTOLOGY | ERROR | OR 1=1 等永真式（注入特征） |
| INJECTION_CONCAT | WARN | 字符串拼接用户输入痕迹 |
| INJECTION_COMMENT | INFO | 引号后 -- 截断 |
| DIALECT_BACKTICK | INFO | MySQL 反引号标识符 |
| DIALECT_BRACKET | INFO | SQL Server 方括号标识符 |
| DIALECT_FN / DIALECT_TOP | INFO | 方言函数（GROUP_CONCAT/IF/GETDATE/TOP） |
| NO_LIMIT | INFO | 顶层 SELECT 无 LIMIT |

脚本是纯标准库零依赖，任何异常都打印明确信息并以非 0 退出，不会静默出错。

---

## 五、输出格式约定

本 Skill 生成 SQL 时遵循：
1. **显式列清单**，不写 `SELECT *`（除非 COUNT(*)）。
2. **关键逻辑加注释**，半开区间处理时间范围（`>= 起 AND < 止`）。
3. **JOIN 写清 ON**，字段类型对齐。
4. **聚合配 GROUP BY**，多表用表别名。
5. **探索性查询带 LIMIT**，防爆量。
6. 危险操作（删/改）先给「SELECT 确认影响行数 + 事务 + WHERE + 备份」安全写法。

检查报告分三级：ERROR（必须修）、WARN（应修）、INFO（留意）。

---

## 六、真实示例（使用示例）

**示例 1｜用户输入**
> 我们 MySQL，orders(user_id, amount, status, created_at) 和 users(id, city)。帮我查上月各城市 GMV 前 10。

**助手动作**
1. 产出 JOIN + 半开区间 + GROUP BY + LIMIT 10 的查询（同第三节场景 A）。
2. 提示：确认 `created_at` 是 DATETIME 且有时区一致；`status='paid'` 是否等于「成交」。
3. 建议存成 `gmv_by_city.sql` 跑 `sql_lint.py` 确认无红线。

**示例 2｜用户输入**
> 这段 SQL 要上线，帮我看看有没有坑：
> `DELETE FROM sessions WHERE last_active < '2026-01-01'`

**助手动作**
1. 跑 `sql_lint.py` → 干净（有 WHERE、无注入）。
2. 补充建议：先 `SELECT COUNT(*)` 看影响行数；用事务包住；确认 `last_active` 有索引（否则全表扫 + 锁表）。

**示例 3｜用户输入**
> 我们 PG，这段 MySQL 跑不过：`SELECT \`name\`, GROUP_CONCAT(tag) FROM t GROUP BY \`name\``

**助手动作**
1. 跑 lint → 标 `DIALECT_BACKTICK` 和 `DIALECT_FN`。
2. 改写为：`SELECT "name", STRING_AGG(tag, ',') FROM t GROUP BY "name"`。
3. 提醒：PG 字符串用单引号，标识符才用双引号（与 MySQL 反引号对应）。

---

## 七、异常处理与排错

| 现象 | 原因 | 解决 |
|---|---|---|
| lint 报 DML_NOWHERE | DELETE/UPDATE 忘写 WHERE | 先 SELECT 看影响行数再补 WHERE |
| lint 报 PAREN | 括号数不对 | 配对检查，尤其子查询嵌套 |
| lint 报 CARTESIAN | FROM a, b 无条件 | 改显式 JOIN ... ON |
| lint 报 INJECTION_* | 拼接用户输入 | 改参数化查询（references/05） |
| 生成的 SQL 目标库报错 | 方言不兼容 | 按 references/01 改写，过 DIALECT 检查 |
| JOIN 结果行数暴涨 | 关联键重复/类型不一致 | 核对 ON 字段唯一性与类型 |
| 聚合结果不对 | GROUP BY 漏列 / 混用 | 确保所有非聚合列都在 GROUP BY |
| 查询巨慢 | 全表扫描 | 看 EXPLAIN，补索引（references/02） |

---

## 八、隐私与合规说明

- `sql_lint.py` 不连库、不执行、不删文件，只读 SQL 文本做静态分析。
- 贴表结构时注意：含 PII（手机号/身份证/邮箱）的字段名/样例值，对外分享前脱敏。
- 生产查询务必最小权限账号 + 审批 + 脱敏返回（见 references/05）。
- 查询经营/财务数据前，确认授权范围，不越权捞数。
- 本 Skill 只产出 SQL，执行动作由你在授权环境完成，责任清晰。

---

## 九、质量门禁（发布前自查，不过不放行）

生成/交付 SQL 前过一遍：
- 无 `SELECT *`（除非 COUNT(*)）。
- 无 `DELETE/UPDATE` 无 WHERE（危险）。
- 括号配对、JOIN 有 ON、无笛卡尔积。
- 无字符串拼接用户输入（参数化）。
- 方言与目标库一致（过 DIALECT 检查）。
- 聚合列与 GROUP BY 对齐。
- 探索查询带 LIMIT。
- 跑过 `sql_lint.py --selftest` 确认脚本完好、对真实 SQL 跑过无 ERROR 级。

---

## 十、进阶技巧

1. **先结构后查询**：永远先给我表结构，生成的 SQL 才对得上真实列名。
2. **半开区间**：时间范围用 `>= 起 AND < 止`，避免边界重复或遗漏。
3. **CTE 分层**：复杂查询用 `WITH` 拆步骤，可读可维护（references/03）。
4. **窗口函数替代子查询**：每组取 TopN、去重留最新，比自连接快且清晰。
5. **lint 进 CI**：把 `sql_lint.py --json` 接进流水线，ERROR 级阻断合并。
6. **参数化一切**：用户入参永远占位符，绝不拼字符串（references/05）。
7. **执行前 SELECT**：任何删改前先 `SELECT` 看影响行数，再上事务。

---

## 十一、实战演武：自然语言 → SQL → 检查（端到端）

**需求：** PostgreSQL，找出「每个用户最近一笔订单的金额」，只要金额大于 100 的，按金额降序取前 20。

**表结构：**
```sql
CREATE TABLE orders (
  id SERIAL, user_id INT, amount NUMERIC(10,2), created_at TIMESTAMPTZ
);
```

**本 Skill 产出：**
```sql
WITH latest AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY user_id ORDER BY created_at DESC
         ) AS rn
  FROM orders
)
SELECT user_id, amount, created_at
FROM latest
WHERE rn = 1            -- 每用户仅留最近一笔
  AND amount > 100      -- 金额门槛
ORDER BY amount DESC
LIMIT 20;
```

**跑检查：**
```bash
python scripts/sql_lint.py --input latest_order.sql
```
预期：干净（无 SELECT *、有 LIMIT、无注入、PG 方言合规）。若有人误写成 `WHERE rn = 1 AND amount > 100 OR 1=1`，lint 立即报 `INJECTION_TAUTOLOGY` ERROR。

**要点复盘：** 用 ROW_NUMBER 窗口函数「每组取第一条」是标准套路（references/03 套路 2）；CTE 让逻辑分层；半开/门槛条件清晰；LIMIT 防爆量。

---

## 十二、规则与参数速查表

| 你想做的事 | 推荐写法 / 工具 |
|---|---|
| 自然语言转 SQL | 给表结构 + 库类型 + 需求，本 Skill 生成 |
| 检查 SQL 红线 | `python scripts/sql_lint.py --input x.sql` |
| 接 CI 卡点 | 同上加 `--json`，ERROR 级阻断 |
| 跨库改写 | 按 references/01 对照改，过 DIALECT 检查 |
| 每组取 TopN | ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) |
| 去重留最新 | 同上 WHERE rn = 1 |
| 累计/环比 | SUM()/LAG() OVER (ORDER BY ...) |
| 防注入 | 参数化查询，绝不拼字符串 |
| 优化慢查询 | EXPLAIN + 补索引（references/02） |
| 深分页 | 游标 `WHERE id > :last_id LIMIT n` |

---

## 十三、常见反模式三则（真实踩坑）

**反模式 1：SELECT * 然后程序里取字段**
- 现象：表加了列，下游崩；JOIN 同名列冲突。
- 正确：显式列清单，本 Skill 扫到即 WARN。

**反模式 2：UPDATE 忘 WHERE，全表价格清零**
- 现象：生产事故， rollback 都救不回（没事务）。
- 正确：先 SELECT 确认 → 事务包 → 补 WHERE；本 Skill 扫到即 ERROR 拦截。

**反模式 3：字符串拼用户输入做登录查询**
- 现象：`' OR '1'='1` 绕登录，拖全表。
- 正确：参数化；本 Skill 的 INJECTION 规则专门扫这类痕迹。

---

## 十四、团队 SQL 治理建议

1. **模板化**：高频查询沉淀为带注释的 SQL 模板库，新人直接套。
2. **lint 门禁**：所有 SQL 合并前过 `sql_lint.py`，ERROR 级不准合。
3. **方言收敛**：团队尽量锁定一两个目标库，减少方言碎片化。
4. **权限分层**：只读账号供分析、受限账号供写入、严禁应用直连超管。
5. **审计**：敏感查询留日志（谁、何时、查了什么），结果脱敏。

---

## 十五、与 BI / Agent 对接实操

- **进 BI**：干净 SQL 存为报表数据源或视图，注释即文档，业务方自助看数。
- **进 Agent**：把「表结构 + 字段含义 + 用户问题」拼进 prompt，让 Agent 基于真实 schema 生成查询，避免编造不存在的列（幻觉主因）。
- **防幻觉要点**：务必给 Agent 真实 DDL，不要让它「猜列名」；生成后强制过 `sql_lint.py` 再执行。
- **多库策略**：不同业务库分开接，别混；方言差异按 references/01 处理。

---

## 十六、常见问题快答（FAQ）

**Q1：我没表结构，能生成 SQL 吗？**
能生成「示意 SQL」，但列名是猜测的，执行前务必按真实表结构改。最好先贴 DDL。

**Q2：lint 报 INFO 的不用管吗？**
INFO 是提示（如方言、无 LIMIT），不阻断但建议处理；WARN 应修；ERROR 必须修。

**Q3：为什么我的 DELETE 有 WHERE 还被拦？**
检查 WHERE 是否在正确的语句块内（子查询/多语句时位置错会误判），或 WHERE 被注释/拼写错。lint 按文本块判断。

**Q4：参数化怎么写？**
`cur.execute("... WHERE id = %s", (uid,))`（Python），或 `?` / `:name` 按语言。永远不把变量直接拼进字符串。

**Q5：窗口函数和 GROUP BY 怎么选？**
要「分组内排名/累计且不合并行」用窗口函数；要「按组汇总成一行」用 GROUP BY。

**Q6：能直接帮我连库查吗？**
不能也不该——本 Skill 只产出 SQL 文本，执行由你在授权环境完成，安全责任清晰。

---

## 十七、多场景 SQL 模板库（即拿即用）

下面这些套路高频出现，存成团队模板，套上你的表名即可。

**模板 1｜分页查询（游标法，深分页不慢）**
```sql
SELECT id, col1, col2
FROM t
WHERE id > :last_id          -- 上一页最后一条的 id
ORDER BY id
LIMIT 20;
```

**模板 2｜去重计数（付费用户数）**
```sql
SELECT COUNT(DISTINCT user_id) AS paid_users
FROM orders
WHERE status = 'paid';
```

**模板 3｜同环比（本月 vs 上月）**
```sql
SELECT
  DATE_TRUNC('month', created_at) AS mon,
  SUM(amount) AS gmv,
  LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', created_at)) AS prev_gmv
FROM orders
GROUP BY 1
ORDER BY 1;
```

**模板 4｜占比（各类目 GMV 份额）**
```sql
SELECT category,
       SUM(amount) AS gmv,
       SUM(amount) * 1.0 / SUM(SUM(amount)) OVER () AS share
FROM orders
GROUP BY category
ORDER BY gmv DESC;
```

**模板 5｜留存/漏斗（次日留存率）**
```sql
SELECT a.day,
       COUNT(DISTINCT a.user_id) AS d0,
       COUNT(DISTINCT b.user_id) AS d1_retain
FROM logs a
LEFT JOIN logs b
  ON b.user_id = a.user_id
 AND b.day = a.day + 1
GROUP BY a.day;
```

**模板 6｜时间序列补全（没有数据的日期也补 0）**
```sql
-- 用生成日期序列 LEFT JOIN 事实表（PG 示例）
SELECT d.dt, COALESCE(SUM(o.amount), 0) AS gmv
FROM generate_series('2026-08-01'::date, '2026-08-31'::date, '1 day') AS d(dt)
LEFT JOIN orders o ON o.created_at::date = d.dt
GROUP BY d.dt
ORDER BY d.dt;
```

---

## 十八、注入攻防对比（一段就懂）

**漏洞写法（永远别这么写）：**
```python
# 用户输入直接拼进 SQL 字符串 —— 致命
name = request.GET['name']
cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
# 用户传 name = ' OR '1'='1   → 拖出全表
# 用户传 name = '; DROP TABLE users; --  → 删库
```

**安全写法（唯一正解：参数化）：**
```python
name = request.GET['name']
cur.execute("SELECT id, name, city FROM users WHERE name = %s", (name,))
# 用户输入永远被当数据，不被当代码
```

**本 Skill 的 `sql_lint.py` 怎么帮你：**
- 扫到字符串 `+`/`||` 拼接用户输入痕迹 → `INJECTION_CONCAT` WARN。
- 扫到 `OR 1=1` 之类永真式 → `INJECTION_TAUTOLOGY` ERROR。
- 三者（拼接 + 永真 + `--` 截断）同现 = 高度疑似注入，必须人工复核来源。

**记忆口诀：** 用户输入进 SQL，只能走占位符，绝不走字符串。

---

## 十九、参考资源索引（本包内）

- references/01_SQL方言速查.md —— MySQL/PG/SQL Server/BigQuery 差异对照
- references/02_查询优化基础.md —— 索引、执行计划、避免全表扫描、深分页
- references/03_窗口函数与CTE.md —— 排名/聚合/偏移套路、每组 TopN
- references/04_常见反模式与陷阱.md —— SELECT*/无WHERE/笛卡尔/注入/N+1
- references/05_安全与注入防范.md —— 参数化、最小权限、脱敏审计
- scripts/sql_lint.py —— 纯标准库静态检查器（含 --selftest）
- hooks/guardrail.md —— 合规护栏，硬拒违规请求

---

## 二十、SQL 健康度自检清单（交付前勾选）

生成或评审一段 SQL，逐项勾：

- [ ] 列清单显式，无 `SELECT *`（除非 COUNT(*)）
- [ ] 任何 `DELETE/UPDATE` 都带 `WHERE`，且先 `SELECT` 确认影响行数
- [ ] 括号配对正确，无嵌套错位
- [ ] `JOIN` 都有 `ON`，无逗号笛卡尔积
- [ ] 无字符串拼接用户输入，全部参数化
- [ ] 方言与目标库一致（过 `DIALECT_*` 检查）
- [ ] 聚合列与 `GROUP BY` 完全对齐
- [ ] 探索性查询带 `LIMIT`/`TOP`
- [ ] 时间范围用半开区间（`>= 起 AND < 止`）
- [ ] 跑过 `sql_lint.py`，无 ERROR / WARN 级
- [ ] 生产执行走最小权限账号 + 审批 + 脱敏返回

十一条全过 = 这条 SQL 可以放心交付。

> 小提醒：lint 只能拦「静态红线」，拦不了「业务逻辑错」（比如把 `status='paid'` 当成成交口径）。口径对不对，永远要你这个懂业务的人拍板。

---

## 二十一、一句话总结

写 SQL 不难，写「对且安全」的 SQL 才难。这个 Skill 给你自然语言转 SQL 的能力 + 一套经过验证的方言/优化/安全方法论 + 一个能在执行前拦住致命写法的静态检查器，让你从「能跑就行」升级到「跑得对、跑得安全」。工具能帮你少踩坑，但业务口径这道关，始终是你自己。
