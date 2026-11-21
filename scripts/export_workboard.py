#!/usr/bin/env python3
"""从 WorkBuddy 平台导出工作计划台 8 张表的 schema 与全量记录。

必须在 WorkBuddy 会话环境内运行：数据脚本靠桌面宿主 IPC 认证，
--token-stdin 会被静默忽略，服务器上无法运行本脚本。

输出：migration/export/<表名>.json + manifest.json
"""
import json
import subprocess
import datetime
import pathlib
import sys
import csv
import io

SKILL_DIR = pathlib.Path(
    "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/"
    "resources/plugins/workbuddy-builtin/skills/library/database"
)
REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "export"
OUT.mkdir(parents=True, exist_ok=True)

TABLES = {
    "task": "bxluDICB3pU5oFPbnX4IAl",
    "review": "AQ579PfPM4ahM3cAPQZVja",
    "milestone": "UQdz6a0OwZjymOgVNqXgRE",
    "time": "76VzPEVzq4WsgsVTVLoOZ7",
    "week": "m3kxJh6pHA7YRnIJoL9EjR",
    "log": "Hs1rMXbiT6UUstrSFLoz6T",
    "inbox": "0j8YUMJbgCi635FVgC6LjL",
    "subtask": "SP2n6UsLiB4GqA7GWUZeKW",
}
PAGE_SIZE = 200


def call(script, *args):
    """调用平台脚本并解析 JSON；返回 (data, raw_stderr)。"""
    p = subprocess.run(
        ["python3", str(SKILL_DIR / script), *map(str, args)],
        capture_output=True, text=True, timeout=180,
    )
    raw = p.stdout.strip()
    start = raw.find("{")
    if start < 0:
        return {"_error": raw or p.stderr.strip() or "empty output"}, p.stderr
    try:
        return json.loads(raw[start:]), p.stderr
    except json.JSONDecodeError as e:
        return {"_error": f"json decode: {e}; head={raw[:200]}"}, p.stderr


def export_table(name, dbid):
    schema, _ = call("get_database_schema.py", "--database-id", dbid)
    if "_error" in schema or "error" in schema:
        reason = schema.get("_error") or schema.get("error")
        return {"status": "skipped", "reason": str(reason)[:300]}

    rows, cursor, pages = [], "", 0
    while True:
        args = ["--database-id", dbid, "--page-size", PAGE_SIZE]
        if cursor:
            args += ["--start-cursor", cursor]
        page, err = call("query_database_record.py", *args)
        if "_error" in page or "error" in page:
            return {"status": "error",
                    "reason": str(page.get("_error") or page.get("error"))[:300],
                    "partial": len(rows)}
        batch = page.get("results", [])
        rows.extend(batch)
        pages += 1
        if not page.get("has_more"):
            break
        nxt = page.get("next_cursor")
        if not nxt or nxt == cursor:
            return {"status": "error", "reason": "cursor not advancing",
                    "partial": len(rows)}
        cursor = nxt
        if pages > 100:
            return {"status": "error", "reason": "too many pages", "partial": len(rows)}

    # 独立通道交叉校验行数（get_database_content 走不同 API 路径）
    csv_check, _ = call("get_database_content.py", "--database-id", dbid)
    csv_count = None
    if isinstance(csv_check, str):
        csv_count = len([ln for ln in csv_check.splitlines() if ln.strip()]) - 1
    elif isinstance(csv_check, dict):
        content = csv_check.get("content")
        if isinstance(content, str):
            # 必须用 csv.reader：字段内含换行符时按 splitlines 数会虚高
            parsed = [r for r in csv.reader(io.StringIO(content))
                      if any(c.strip() for c in r)]
            csv_count = max(0, len(parsed) - 1)
        else:
            for key in ("count", "total", "rows"):
                v = csv_check.get(key)
                if isinstance(v, int):
                    csv_count = v
                    break
                if isinstance(v, list):
                    csv_count = len(v)
                    break

    payload = {
        "table": name,
        "database_id": dbid,
        "title": schema.get("title"),
        "schema": schema,
        "rows": rows,
        "count": len(rows),
        "csv_cross_check_count": csv_count,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (OUT / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return {
        "status": "ok", "count": len(rows), "pages": pages,
        "csv_count": csv_count,
        "fields": [p.get("name") for p in schema.get("properties", [])],
    }


def main():
    manifest = {
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "WorkBuddy 资料库数据表（桌面宿主 IPC）",
        "tables": {},
    }
    for name, dbid in TABLES.items():
        print(f"[{name}] {dbid} ...", flush=True)
        info = export_table(name, dbid)
        manifest["tables"][name] = info
        print("   ", info, flush=True)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = [n for n, i in manifest["tables"].items() if i["status"] == "ok"]
    total = sum(manifest["tables"][n]["count"] for n in ok)
    print(f"\n完成：{len(ok)}/{len(TABLES)} 张表，合计 {total} 行")
    return 0 if len(ok) >= 7 else 1


if __name__ == "__main__":
    sys.exit(main())
