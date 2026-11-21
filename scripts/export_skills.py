#!/usr/bin/env python3
"""在本机把 4 个 workboard 技能导出成 JSON 包（供 scp 到服务器导入）。

用法：python3 export_skills.py --out /tmp/skills_pack.json
输出不含任何密钥，只含技能正文/脚本/关联/sha。
"""
import pathlib, hashlib, json, argparse, sys

SKILLS_DIR = pathlib.Path.home() / ".workbuddy" / "skills"
NAMES = ["workboard-today-plan", "workboard-today-review",
         "workboard-database-write", "workboard-page-publish"]
RELATED = {
    "workboard-today-plan": ["workboard-today-review", "workboard-database-write"],
    "workboard-today-review": ["workboard-today-plan", "workboard-database-write"],
    "workboard-database-write": ["workboard-today-plan", "workboard-today-review"],
    "workboard-page-publish": ["workboard-database-write"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pack = []
    for name in NAMES:
        d = SKILLS_DIR / name
        sk = d / "SKILL.md"
        if not sk.exists():
            print(f"[{name}] 跳过（无 SKILL.md）")
            continue
        content = sk.read_text(encoding="utf-8")
        scripts = {}
        sdir = d / "scripts"
        if sdir.exists():
            for f in sorted(sdir.iterdir()):
                if f.is_file() and f.suffix in (".py", ".js", ".sh", ".md"):
                    scripts[f.name] = f.read_text(encoding="utf-8", errors="replace")
        pack.append({
            "id": "s_" + hashlib.sha1(name.encode()).hexdigest()[:12],
            "name": name,
            "content": content,
            "scripts_json": json.dumps(scripts, ensure_ascii=False),
            "related_json": json.dumps(RELATED.get(name, []), ensure_ascii=False),
            "source_sha": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
        print(f"[{name}] 正文 {len(content)} 字节 | 脚本 {len(scripts)} 个")
    pathlib.Path(args.out).write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已导出 {len(pack)} 个技能 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
