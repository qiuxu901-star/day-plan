#!/usr/bin/env python3
"""根据 export/ 的 schema + 全量记录，构建 SQLite 库并做四项硬校验。

设计：业务表直接用原始中文列名（SQLite 支持），使导出的扁平记录可直入库、
API 返回中文键，前端 unwrapProps 后与现有业务代码零摩擦对齐。
元数据列以下划线开头，避免与业务列冲突。

输出：data/workboard.db + verify_report.json
"""
import json
import hashlib
import re
import sqlite3
import pathlib
import datetime
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
EXPORT = DATA / "export"
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "workboard.db"
REPORT = DATA / "verify_report.json"

# 表名 -> (导出文件名, 中文显示名)
TABLES = {
    "task": ("task", "任务表"),
    "review": ("review", "复盘表"),
    "milestone": ("milestone", "阶段表"),
    "time": ("time", "时间表"),
    "week": ("week", "周计划表"),
    "log": ("log", "留痕表"),
    "inbox": ("inbox", "收集箱"),
    "subtask": ("subtask", "子任务表"),
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def q(name):
    """引用列名（中文列必须加双引号）。"""
    return '"' + name.replace('"', '""') + '"'


def content_hash(row):
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def create_business_table(conn, name, schema, rows):
    props = schema.get("properties", []) if schema else []
    cols = []
    for p in props:
        fname = p.get("name")
        ftype = p.get("type", "text")
        # number 用 REAL 以便数值比较；其余一律 TEXT（日期原样 ISO 字符串）
        sqltype = "REAL" if ftype == "number" else "TEXT"
        cols.append(f"  {q(fname)} {sqltype}")
    ddl_cols = ", ".join(cols) if cols else '  "_placeholder" TEXT'
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {q(name)} (
          record_id TEXT PRIMARY KEY,
          {ddl_cols},
          "_created_at" TEXT,
          "_updated_at" TEXT,
          "_origin" TEXT NOT NULL DEFAULT 'workbuddy',
          "_sync_status" TEXT NOT NULL DEFAULT 'synced',
          "_content_hash" TEXT
        )
    """)
    now = datetime.datetime.now().isoformat(timespec="seconds") + "Z"
    inserted = 0
    for row in rows:
        rid = row.get("record_id")
        if not rid:
            continue
        business = {p.get("name"): row.get(p.get("name"))
                    for p in props if p.get("name")}
        keys = ["record_id"] + list(business.keys()) + [
            "_created_at", "_updated_at", "_origin", "_sync_status", "_content_hash"
        ]
        vals = [rid] + [business[k] for k in business] + [
            now, now, "workbuddy", "synced", content_hash(business)
        ]
        placeholders = ",".join("?" for _ in keys)
        qcols = ",".join(q(k) for k in keys)
        conn.execute(
            f"INSERT OR REPLACE INTO {q(name)} ({qcols}) VALUES ({placeholders})",
            vals,
        )
        inserted += 1
    return inserted


def create_meta_tables(conn):
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS field_meta (
        table_name TEXT, field_name TEXT, field_type TEXT,
        options_json TEXT, PRIMARY KEY(table_name, field_name)
      );
      CREATE TABLE IF NOT EXISTS api_key (
        id TEXT PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL,
        scope TEXT NOT NULL CHECK(scope IN ('read','write')),
        created_at TEXT, revoked INTEGER DEFAULT 0, note TEXT
      );
      CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT,
        action TEXT, table_name TEXT, record_id TEXT, detail TEXT
      );
      CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, table_name TEXT,
        record_id TEXT, op TEXT, payload TEXT, status TEXT DEFAULT 'pending',
        attempts INTEGER DEFAULT 0, last_error TEXT
      );
      CREATE TABLE IF NOT EXISTS sync_state (
        key TEXT PRIMARY KEY, value TEXT
      );
      CREATE TABLE IF NOT EXISTS sync_conflicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, table_name TEXT,
        record_id TEXT, local_hash TEXT, platform_hash TEXT, note TEXT,
        resolved INTEGER DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
        content TEXT, status TEXT DEFAULT 'active',
        created_at TEXT, updated_at TEXT
      );
    """)


def store_field_meta(conn, table, schema):
    if not schema:
        return
    for p in schema.get("properties", []):
        name = p.get("name")
        ftype = p.get("type")
        cfg = p.get("config") or {}
        opts = cfg.get("options")
        conn.execute(
            "INSERT OR REPLACE INTO field_meta VALUES (?,?,?,?)",
            (table, name, ftype,
             json.dumps(opts, ensure_ascii=False) if opts else None),
        )


def verify(conn, exports, manifest):
    """四项硬校验：条数对齐 / 抽样 / 重复 id / 日期格式。"""
    report = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
              "checks": {}, "passed": True}
    for table, (fname, label) in TABLES.items():
        info = manifest["tables"].get(table, {})
        if info.get("status") != "ok":
            report["checks"][table] = {"status": "skipped",
                                        "reason": info.get("reason")}
            continue

        payload = exports[table]
        src_rows = payload["rows"]
        props = payload["schema"].get("properties", [])
        date_fields = [p["name"] for p in props if p.get("type") == "date"]
        num_fields = [p["name"] for p in props if p.get("type") == "number"]

        # 1) 条数
        db_count = conn.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0]
        # 2) 重复 id（主键保证，仍显式检查）
        dup = conn.execute(
            f"SELECT count(*) FROM (SELECT record_id FROM {q(table)} "
            "GROUP BY record_id HAVING count(*)>1)"
        ).fetchone()[0]
        # 3) 抽样逐字段比对（最多 8 条）
        sample = src_rows[:8]
        mismatches = []
        for s in sample:
            rid = s.get("record_id")
            cols = ["record_id"] + [p["name"] for p in props]
            got = conn.execute(
                f"SELECT {','.join(q(c) for c in cols)} FROM {q(table)} "
                "WHERE record_id=?", (rid,)
            ).fetchone()
            if not got:
                mismatches.append(f"{rid}: 缺失")
                continue
            d = dict(zip(cols, got))
            for p in props:
                f = p["name"]
                a, b = s.get(f), d.get(f)
                if a is None and b is None:
                    continue
                if f in num_fields:
                    try:
                        if abs(float(a or 0) - float(b or 0)) > 1e-9:
                            mismatches.append(f"{rid}.{f}: {a!r} vs {b!r}")
                    except (TypeError, ValueError):
                        mismatches.append(f"{rid}.{f}: 非数值 {a!r}/{b!r}")
                elif str(a or "") != str(b or ""):
                    mismatches.append(f"{rid}.{f}: {a!r} vs {b!r}")
        # 4) 日期格式
        bad_dates = []
        for f in date_fields:
            for (v,) in conn.execute(
                f"SELECT {q(f)} FROM {q(table)} WHERE {q(f)} IS NOT NULL AND {q(f)}!=''"
            ):
                if not DATE_RE.match(str(v)):
                    bad_dates.append(f"{f}={v}")

        ok = (db_count == len(src_rows) and dup == 0
              and not mismatches and not bad_dates)
        report["checks"][table] = {
            "status": "pass" if ok else "FAIL",
            "label": label,
            "source_count": len(src_rows), "db_count": db_count,
            "duplicate_ids": dup,
            "sample_size": len(sample), "sample_mismatches": mismatches[:10],
            "bad_date_values": bad_dates[:10],
        }
        if not ok:
            report["passed"] = False
    return report


def main():
    manifest = json.loads((EXPORT / "manifest.json").read_text(encoding="utf-8"))
    exports = {}
    for table, (fname, _) in TABLES.items():
        p = EXPORT / f"{fname}.json"
        if p.exists():
            exports[table] = json.loads(p.read_text(encoding="utf-8"))

    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")

    create_meta_tables(conn)
    for table, (fname, _) in TABLES.items():
        info = manifest["tables"].get(table, {})
        if info.get("status") != "ok":
            # 失效表建空壳，保留占位与 schema
            conn.execute(
                f'CREATE TABLE IF NOT EXISTS {q(table)} '
                '(record_id TEXT PRIMARY KEY, "_placeholder" TEXT, '
                '"_origin" TEXT DEFAULT "workbuddy", '
                '"_sync_status" TEXT DEFAULT "synced", "_content_hash" TEXT)'
            )
            continue
        payload = exports[table]
        n = create_business_table(conn, table, payload["schema"], payload["rows"])
        store_field_meta(conn, table, payload["schema"])
        print(f"[{table}] 导入 {n} 行")

    conn.execute(
        "INSERT OR REPLACE INTO sync_state VALUES ('schema_version','1')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO sync_state VALUES ('last_export_at',?)",
        (manifest["exported_at"],),
    )
    conn.commit()

    report = verify(conn, exports, manifest)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()

    print("\n=== 校验结果 ===")
    for t, c in report["checks"].items():
        if c["status"] == "skipped":
            print(f"  {t:10s} SKIPPED  {c['reason'][:60]}")
        else:
            flag = "PASS" if c["status"] == "pass" else "FAIL"
            print(f"  {t:10s} {flag:6s} {c['db_count']}/{c['source_count']} 行"
                  f" 重复{c['duplicate_ids']} 抽样错{len(c['sample_mismatches'])}"
                  f" 日期错{len(c['bad_date_values'])}")
    print(f"\n总判定：{'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
