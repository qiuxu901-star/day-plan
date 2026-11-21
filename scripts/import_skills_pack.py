#!/usr/bin/env python3
"""在服务器把 skills JSON 包导入 skills 表。

用法：python3 import_skills_pack.py --pack /path/to/skills_pack.json [--force]
默认只填空摘要行（content < 1000 字节），--force 覆盖。
"""
import sqlite3, pathlib, json, datetime, argparse, sys

DB = pathlib.Path("/home/admin/workboard/data/workboard.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    pack = json.loads(pathlib.Path(args.pack).read_text(encoding="utf-8"))
    c = sqlite3.connect(str(DB))
    ts = datetime.datetime.now().isoformat(timespec="seconds") + "Z"

    cols = set(r[1] for r in c.execute("PRAGMA table_info(skills)"))
    for col in ("scripts_json", "related_json", "source_sha"):
        if col not in cols:
            c.execute(f"ALTER TABLE skills ADD COLUMN {col} TEXT")

    for it in pack:
        cur = c.execute("SELECT content FROM skills WHERE id=?", (it["id"],)).fetchone()
        if cur and len(cur[0] or "") >= 1000 and not args.force:
            print(f"[{it['name']}] 已有正文 {len(cur[0])} 字节，跳过（--force 覆盖）")
            continue
        print(f"[{it['name']}] 导入正文 {len(it['content'])} 字节 | "
              f"脚本 {len(json.loads(it['scripts_json']))} 个 | sha {it['source_sha'][:8]}")
        c.execute("""INSERT INTO skills
            (id,name,description,content,status,created_at,updated_at,scripts_json,related_json,source_sha)
            VALUES (?,?,?,?,'active',?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              content=excluded.content, scripts_json=excluded.scripts_json,
              related_json=excluded.related_json, source_sha=excluded.source_sha,
              updated_at=excluded.updated_at""",
            (it["id"], it["name"], it.get("description", ""), it["content"], ts, ts,
             it["scripts_json"], it["related_json"], it["source_sha"]))
    c.commit()
    c.close()
    print("导入完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
