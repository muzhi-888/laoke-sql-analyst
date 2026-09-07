# 03 · 窗口函数与 CTE：进阶但超常用

> 窗口函数（Window Function）和 CTE 是现代 SQL 的两把利器，能替代大量子查询，可读性高、性能好。本文件给最常用套路。

## 一、CTE（WITH）：把复杂查询拆成步骤

```sql
WITH cleaned AS (
  SELECT user_id, amount FROM orders WHERE status = 'paid'
),
agg AS (
  SELECT user_id, SUM(amount) AS total FROM cleaned GROUP BY user_id
)
SELECT * FROM agg ORDER BY total DESC LIMIT 10;
```
- 好处：像写临时表但不落库，逻辑分层清晰。
- 可递归 `WITH RECURSIVE`（树形结构、层级展开）。

## 二、窗口函数：分组内计算，不合并行

语法：`函数() OVER (PARTITION BY 分组 ORDER BY 排序 窗口)`

### 排名类
```sql
SELECT name, dept, salary,
       RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rk
FROM emp;
```
- `RANK()`：并列占名次（1,1,3）
- `DENSE_RANK()`：并列不跳（1,1,2）
- `ROW_NUMBER()`：严格不重复（1,2,3），常用来「每组取第一条」

### 聚合类（窗口内求和/均值）
```sql
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month) AS running_total,
       AVG(revenue) OVER (PARTITION BY year) AS year_avg
FROM sales;
```

### 偏移类
```sql
LAG(amount) OVER (ORDER BY month)   -- 上一行
LEAD(amount) OVER (ORDER BY month)  -- 下一行
```
常用于「环比」「差值」。

## 三、经典套路

### 套路 1：每组取 Top N
```sql
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn FROM emp
) t WHERE rn <= 3;
```

### 套路 2：去重保留最新一条
```sql
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC) AS rn FROM logs
) t WHERE rn = 1;
```

### 套路 3：累计与同比
```sql
SELECT month,
       SUM(amt) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS ma3
FROM t;
```

### 套路 4：环比增长率
```sql
SELECT month, amt,
       (amt - LAG(amt) OVER (ORDER BY month)) * 1.0 / LAG(amt) OVER (ORDER BY month) AS mom
FROM t;
```

## 四、注意

- 窗口函数不减少行数（与 GROUP BY 本质区别），结果行数 = 原行数。
- `ORDER BY` 在窗口里决定「累计/排名顺序」，漏写会全组当一排序。
- 主流库（MySQL 8+/PG/SQL Server/BigQuery）都支持；老 MySQL 5.7 不支持窗口函数，需升级或改子查询。
- 性能：窗口函数通常比「自连接 + 聚合」的子查询快，且好读。
