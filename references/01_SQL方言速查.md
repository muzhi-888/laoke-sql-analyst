# 01 · SQL 方言速查：四大主流库差异

> 写 SQL 最容易踩的坑就是「在我机器上能跑，换库就报错」。本文件列最常用的方言差异，写跨库查询前先对表。

## 一、分页（最常用，必记）

| 需求 | MySQL | PostgreSQL | SQL Server | BigQuery |
|---|---|---|---|---|
| 取前 10 | `LIMIT 10` | `LIMIT 10` | `TOP 10` / `OFFSET 0 ROWS FETCH NEXT 10` | `LIMIT 10` |
| 分页 | `LIMIT 20 OFFSET 10` | 同 MySQL | `OFFSET 10 ROWS FETCH NEXT 20` | `LIMIT 20 OFFSET 10` |

## 二、字符串拼接与函数

| 功能 | MySQL | PostgreSQL | SQL Server | 备注 |
|---|---|---|---|---|
| 拼接 | `CONCAT(a,b)` / `a||b` | `a||b` | `a+b` / `CONCAT` | `||` 在 SQL Server 默认是逻辑或 |
| 当前时间 | `NOW()` | `NOW()` | `GETDATE()` | |
| 空值处理 | `IFNULL(x,0)` | `COALESCE(x,0)` | `ISNULL(x,0)` | 通用 `COALESCE` |
| 条件 | `IF(c,a,b)` | `CASE WHEN c THEN a ELSE b END` | `IIF(c,a,b)` | 通用 `CASE` |
| 分组拼接 | `GROUP_CONCAT(x)` | `STRING_AGG(x,',')` | `STRING_AGG(x,',')` | 跨库别写 GROUP_CONCAT |
| 正则 | `REGEXP` | `~` | `LIKE`/`PATINDEX` | |

## 三、标识符引号（本 Skill 的 DIALECT 检查会扫到）

- MySQL：反引号 `` `col` ``
- SQL Server：方括号 `[col]`
- PostgreSQL / 标准：双引号 `"col"`
- **通用写法**：尽量不用保留字做列名；非要保留字就按目标库选对应引号，别混用。

## 四、自增主键

| 库 | 写法 |
|---|---|
| MySQL | `id INT AUTO_INCREMENT PRIMARY KEY` |
| PostgreSQL | `id SERIAL PRIMARY KEY` 或 `GENERATED ALWAYS AS IDENTITY` |
| SQL Server | `id INT IDENTITY(1,1) PRIMARY KEY` |
| BigQuery | 无自增，用 `GENERATE_UUID()` 或 `ROW_NUMBER()` |

## 五、日期处理

- MySQL：`DATE_FORMAT(d,'%Y-%m-%d')`、`DATEDIFF(a,b)`
- PostgreSQL：`TO_CHAR(d,'YYYY-MM-DD')`、`a - b`（间隔类型）
- SQL Server：`CONVERT(varchar,d,23)`、`DATEDIFF(day,a,b)`
- 通用：ISO 字面量 `'2026-09-08'`

## 六、类型与布尔

- MySQL：`BOOL` 是 `TINYINT(1)` 别名，`TRUE=1`
- PostgreSQL：`BOOLEAN` 真类型
- SQL Server：无 BOOL，用 `BIT`（1/0）
- BigQuery：`BOOL`

## 七、实战建议

1. 确定目标库再动笔，写完用本 Skill 的 `sql_lint.py` 跑一遍方言检查。
2. 优先写 ANSI 标准 SQL（CASE/COALESCE/LIMIT 在标准库近年都支持），减少方言函数。
3. 必须跨库时，做一张「函数映射表」放团队 wiki，别每次现查。
4. 用 CTE（`WITH`）提升可读性，主流库都支持。
