#!/usr/bin/env python3
"""把 4 个 workboard 技能的完整 SKILL.md + 脚本源码灌入服务器 skills 表。

默认只填空（content < 1000 字节的摘要行），--force 才覆盖用户编辑。
用法：python3 seed_skills_full.py [--force] [--dry-run]
"""
import sqlite3, pathlib, hashlib, datetime, argparse, json, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DB = REPO / "data" / "workboard.db"
SKILLS_DIR = pathlib.Path.home() / ".workbuddy" / "skills"

NAMES = ["workboard-today-plan", "workboard-today-review",
         "workboard-database-write", "workboard-page-publish"]
RELATED = {
    "workboard-today-plan": ["workboard-today-review", "workboard-database-write"],
    "workboard-today-review": ["workboard-today-plan", "workboard-database-write"],
    "workboard-database-write": ["workboard-today-plan", "workboard-today-review"],
    "workboard-page-publish": ["workboard-database-write"],
}


def sid(name):
    return "s_" + hashlib.sha1(name.encode()).hexdigest()[:12]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect(name):
    d = SKILLS_DIR / name
    sk = d / "SKILL.md"
    if not sk.exists():
        return None
    content = sk.read_text(encoding="utf-8")
    scripts = {}
    sdir = d / "scripts"
    if sdir.exists():
        for f in sorted(sdir.iterdir()):
            if f.is_file() and f.suffix in (".py", ".js", ".sh", ".md"):
                scripts[f.name] = f.read_text(encoding="utf-8", errors="replace")
    return {
        "id": sid(name),
        "name": name,
        "content": content,
        "scripts_json": json.dumps(scripts, ensure_ascii=False),
        "related_json": json.dumps(RELATED.get(name, []), ensure_ascii=False),
        "source_sha": sha(content),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已有正文")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DB.exists():
        print("数据库不存在:", DB)
        return 1
    c = sqlite3.connect(str(DB))
    ts = datetime.datetime.now().isoformat(timespec="seconds") + "Z"

    # 确保列存在（本地库可能也是旧结构）
    cols = set(r[1] for r in c.execute("PRAGMA table_info(skills)"))
    for col in ("scripts_json", "related_json", "source_sha"):
        if col not in cols:
            c.execute(f"ALTER TABLE skills ADD COLUMN {col} TEXT")

    for name in NAMES:
        item = collect(name)
        if not item:
            print(f"[{name}] SKILL.md 不存在，跳过")
            continue
        cur = c.execute("SELECT content FROM skills WHERE id=?", (item["id"],)).fetchone()
        if cur and len(cur[0] or "") >= 1000 and not args.force:
            print(f"[{name}] 已有正文 {len(cur[0])} 字节，跳过（--force 可覆盖）")
            continue
        print(f"[{name}] {'DRY-RUN ' if args.dry_run else ''}正文 {len(item['content'])} 字节 "
              f"| 脚本 {len(json.loads(item['scripts_json']))} 个 | sha {item['source_sha'][:8]}")
        if args.dry_run:
            continue
        c.execute("""INSERT INTO skills
            (id,name,description,content,status,created_at,updated_at,scripts_json,related_json,source_sha)
            VALUES (?,?,?,?,'active',?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              content=excluded.content, scripts_json=excluded.scripts_json,
              related_json=excluded.related_json, source_sha=excluded.source_sha,
              description=COALESCE(skills.description,excluded.description),
              updated_at=excluded.updated_at""",
            (item["id"], item["name"], "", item["content"], ts, ts,
             item["scripts_json"], item["related_json"], item["source_sha"]))
    if not args.dry_run:
        c.commit()
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
