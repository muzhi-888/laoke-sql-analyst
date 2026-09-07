# -*- coding: utf-8 -*-
"""
sql_lint.py —— SQL 静态检查器（纯标准库，零依赖）

功能：
  对一段 SQL（文件或 stdin）做静态红线检查，输出带严重级别、规则号、行号的报告。
  覆盖：SELECT *、DELETE/UPDATE 无 WHERE、括号不匹配、笛卡尔积风险、
        可能的 SQL 注入（拼接/永真式）、方言不兼容（反引号/[括号]/IF/GROUP_CONCAT 等）。
  不执行 SQL、不连库、不发网络——纯文本静态分析。

用法：
  python sql_lint.py --input query.sql
  cat query.sql | python sql_lint.py
  python sql_lint.py --input query.sql --json
  python sql_lint.py --selftest        # 内置自检，exit 0 即通过

退出码：0 = 检查完成（无论有没有问题）；2 = 参数/IO 错误。
"""
import argparse
import json
import re
import sys


# ---------------------------------------------------------------------------
# 行号工具
# ---------------------------------------------------------------------------

def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------

def check_select_star(sql):
    findings = []
    for m in re.finditer(r"SELECT\s+\*", sql, re.IGNORECASE):
        # 排除 COUNT(*) / COUNT( DISTINCT * )
        ctx = sql[m.start():m.start() + 40]
        if re.search(r"COUNT\s*\(\s*(DISTINCT\s+)?\*", ctx, re.IGNORECASE):
            continue
        findings.append(("SELECT_STAR", "WARN", line_of(sql, m.start()),
                         "使用了 SELECT *，建议显式列出所需列，避免多表 join 时列冲突、减少不必要 IO"))
    return findings


def check_dml_no_where(sql):
    findings = []
    # DELETE FROM ... [no WHERE before ; or end]
    for m in re.finditer(r"DELETE\s+FROM\s+([^\n;]*?)(;|\Z)", sql, re.IGNORECASE | re.DOTALL):
        body = m.group(1)
        if not re.search(r"\bWHERE\b", body, re.IGNORECASE):
            findings.append(("DML_NOWHERE", "ERROR", line_of(sql, m.start()),
                             "DELETE 缺少 WHERE 条件，将删除全表数据！务必加 WHERE 或先 SELECT 确认影响行数"))
    # UPDATE ... SET ... [no WHERE]
    for m in re.finditer(r"UPDATE\s+[^\n;]*?SET\s+([^\n;]*?)(;|\Z)", sql, re.IGNORECASE | re.DOTALL):
        body = m.group(1)
        if not re.search(r"\bWHERE\b", body, re.IGNORECASE):
            findings.append(("DML_NOWHERE", "ERROR", line_of(sql, m.start()),
                             "UPDATE 缺少 WHERE 条件，将更新全表！务必加 WHERE 限定范围"))
    return findings


def check_paren(sql):
    findings = []
    depth = 0
    line = 1
    for i, ch in enumerate(sql):
        if ch == "\n":
            line += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                findings.append(("PAREN", "ERROR", line,
                                 "右括号多于左括号，存在多余的 ')'"))
                depth = 0
    if depth > 0:
        findings.append(("PAREN", "ERROR", line_of(sql, len(sql)),
                         f"左括号多于右括号，缺少 {depth} 个 ')'"))
    return findings


def check_cartesian(sql):
    findings = []
    # 逗号 join：FROM a, b 且整句无 JOIN/ON 也无 WHERE
    for m in re.finditer(r"FROM\s+([^\n;]*?)(;|\Z)", sql, re.IGNORECASE | re.DOTALL):
        body = m.group(1)
        # 含逗号分隔多表
        if "," in body and not re.search(r"\bJOIN\b", body, re.IGNORECASE) and not re.search(r"\bWHERE\b", body, re.IGNORECASE):
            findings.append(("CARTESIAN", "WARN", line_of(sql, m.start()),
                             "检测到逗号连接多表且无条件（FROM a, b）：易产生笛卡尔积，建议改用显式 JOIN ... ON"))
    return findings


def check_injection(sql):
    findings = []
    # 永真式：OR 1=1 / OR '1'='1' / OR 1 = 1
    for m in re.finditer(r"\bOR\b\s+('?1'?|'[^']*')\s*=\s*('?1'?|'[^']*')", sql, re.IGNORECASE):
        findings.append(("INJECTION_TAUTOLOGY", "ERROR", line_of(sql, m.start()),
                         "检测到永真条件（OR 1=1 之类），这是典型 SQL 注入特征，禁止拼接用户输入；改用参数化查询"))
    # 字符串拼接用户输入： ' + var / var + ' / || '
    for pat in [r"'[^']*\'\s*\+", r"\+\s*\'[^\']*\'", r"\'\s*\|\|\s*", r"\|\|\s*\'"]:
        for m in re.finditer(pat, sql):
            findings.append(("INJECTION_CONCAT", "WARN", line_of(sql, m.start()),
                             "检测到字符串拼接，若拼接的是用户输入则存在注入风险；请改用占位符/参数化（? 或 %(name)s）"))
            break
    # 注释截断：' -- 
    for m in re.finditer(r"'\s*--", sql):
        findings.append(("INJECTION_COMMENT", "INFO", line_of(sql, m.start()),
                         "检测到引号后跟 -- 注释，可能是注入截断手法，请确认来源可信"))
    return findings


def check_dialect(sql):
    findings = []
    # MySQL 反引号标识符
    if "`" in sql:
        findings.append(("DIALECT_BACKTICK", "INFO", line_of(sql, sql.index("`")),
                         "检测到反引号 ` 标识符（MySQL 风格），PostgreSQL/SQL Server 不兼容，换库需改引号"))
    # SQL Server [方括号]
    if re.search(r"\[[^\]]+\]", sql):
        findings.append(("DIALECT_BRACKET", "INFO", line_of(sql, re.search(r"\[[^\]]+\]", sql).start()),
                         "检测到 [方括号] 标识符（SQL Server 风格），其他库不兼容"))
    # MySQL 特有函数
    for fn in ["GROUP_CONCAT", "IFNULL", "IF("]:
        for m in re.finditer(re.escape(fn), sql, re.IGNORECASE):
            findings.append(("DIALECT_FN", "INFO", line_of(sql, m.start()),
                             f"函数 {fn} 为方言特有（多为 MySQL），跨库请换等价写法（如 GROUP_CONCAT→STRING_AGG，IF→CASE）"))
            break
    # SQL Server 特有
    for m in re.finditer(r"\bTOP\s+\d+", sql, re.IGNORECASE):
        findings.append(("DIALECT_TOP", "INFO", line_of(sql, m.start()),
                         "TOP n 为 SQL Server 语法，MySQL/PostgreSQL 用 LIMIT"))
        break
    if re.search(r"GETDATE\s*\(", sql, re.IGNORECASE):
        findings.append(("DIALECT_FN", "INFO", line_of(sql, re.search(r"GETDATE\s*\(", sql, re.IGNORECASE).start()),
                         "GETDATE() 为 SQL Server 函数，其他库用 NOW()/CURRENT_TIMESTAMP"))
    return findings


def check_limit(sql):
    findings = []
    # 顶层单条 SELECT 无 LIMIT（探索性查询建议加 LIMIT 防爆量）
    statements = re.split(r";\s*\n", sql)
    top_selects = [s for s in statements if re.search(r"\bSELECT\b", s, re.IGNORECASE) and not re.search(r"\bWITH\b", s.strip(), re.IGNORECASE)]
    if len(top_selects) == 1:
        s = top_selects[0]
        if not re.search(r"\bLIMIT\b", s, re.IGNORECASE) and not re.search(r"\bTOP\s+\d+", s, re.IGNORECASE):
            findings.append(("NO_LIMIT", "INFO", line_of(sql, sql.upper().find("SELECT")),
                             "顶层 SELECT 未加 LIMIT/TOP，探索性查询建议加 LIMIT 防止返回过大结果集"))
    return findings


def lint(sql):
    all_findings = []
    all_findings += check_select_star(sql)
    all_findings += check_dml_no_where(sql)
    all_findings += check_paren(sql)
    all_findings += check_cartesian(sql)
    all_findings += check_injection(sql)
    all_findings += check_dialect(sql)
    all_findings += check_limit(sql)
    # 排序：行号
    all_findings.sort(key=lambda x: x[2])
    return all_findings


SEV_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def render(findings):
    if not findings:
        return "[OK] 未发现静态红线问题。仍建议你人工复核业务逻辑与权限。"
    lines = []
    counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for rule, sev, line, msg in findings:
        counts[sev] += 1
        lines.append(f"[{sev}] {rule} (L{line}): {msg}")
    header = f"共 {len(findings)} 条发现 — ERROR:{counts['ERROR']} WARN:{counts['WARN']} INFO:{counts['INFO']}"
    return header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

SAMPLE = """
-- 一段故意埋了多种问题的 SQL

DELETE FROM users;

SELECT * FROM orders o, customers c;

SELECT (a + b FROM t;

SELECT name FROM products WHERE price > 100 OR 1=1;
"""


def selftest():
    findings = lint(SAMPLE)
    rules = {f[0] for f in findings}
    required = {"SELECT_STAR", "DML_NOWHERE", "PAREN", "CARTESIAN", "INJECTION_TAUTOLOGY"}
    missing = required - rules
    if missing:
        print(f"[FAIL] 自检未检出预期问题: {missing}")
        print(render(findings))
        return 1
    # 确认 DML_NOWHERE 是 ERROR 级别
    if not any(f[0] == "DML_NOWHERE" and f[1] == "ERROR" for f in findings):
        print("[FAIL] DML_NOWHERE 未标记为 ERROR")
        return 1
    print(f"[OK] 自检通过：检出 {len(findings)} 条，含预期红线 {sorted(required)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="SQL 静态检查器")
    ap.add_argument("--input", help="SQL 文件路径（缺省读 stdin）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if args.input:
        try:
            with open(args.input, encoding="utf-8") as f:
                sql = f.read()
        except OSError as e:
            print(f"[ERROR] 无法读取文件: {e}")
            sys.exit(2)
    else:
        sql = sys.stdin.read()

    findings = lint(sql)
    if args.json:
        out = [{"rule": r, "severity": s, "line": l, "message": m} for (r, s, l, m) in findings]
        print(json.dumps({"count": len(out), "findings": out}, ensure_ascii=False, indent=2))
    else:
        print(render(findings))
    sys.exit(0)


if __name__ == "__main__":
    main()
