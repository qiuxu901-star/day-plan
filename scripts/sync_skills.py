#!/usr/bin/env python3
"""技能双向同步（手动显式，默认 dry-run）。

  --direction pull : 服务器 → 本机 SKILL.md + scripts/（覆盖前 .bak）
  --direction push : 本机 → 服务器（通过 export_skills.py 生成的包 + API）

冲突保护：source_sha 与本机当前 sha 不一致且服务器更新 → 拒绝，需 --force。
用法：
  python3 sync_skills.py --direction pull            # 只看会改什么
  python3 sync_skills.py --direction pull --yes      # 真正落盘
  python3 sync_skills.py --direction push --yes      # 推到服务器
"""
import json, pathlib, hashlib, argparse, sys, urllib.request, urllib.error, datetime

CONFIG = pathlib.Path.home() / ".workbuddy" / "workboard" / "config.json"
SKILLS_DIR = pathlib.Path.home() / ".workbuddy" / "skills"


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def api(cfg, path, method="GET", body=None, token=None):
    url = cfg["base_url"].rstrip("/") + path
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def load_cfg():
    if not CONFIG.exists():
        raise SystemExit("缺少 " + str(CONFIG))
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def do_pull(cfg, yes, force):
    pwd = cfg.get("password") or cfg.get("api_key")
    tok = api(cfg, "/api/auth/login", "POST", {"password": pwd})["token"]
    skills = api(cfg, "/api/skills", token=tok)
    changed = 0
    for s in skills:
        name = s.get("name", "")
        if not name.startswith("workboard-"):
            continue
        content = s.get("content") or ""
        if len(content) < 200:
            print(f"[{name}] 正文过短，跳过")
            continue
        target = SKILLS_DIR / name / "SKILL.md"
        local_sha = sha(target.read_text(encoding="utf-8")) if target.exists() else ""
        srv_sha = s.get("source_sha", "")
        if local_sha != srv_sha and not force:
            print(f"[{name}] 冲突：本机 {local_sha[:8]} / 服务器标记 {srv_sha[:8]}，需 --force")
            continue
        if local_sha == sha(content):
            print(f"[{name}] 无变化")
            continue
        print(f"[{name}] {'WRITE' if yes else 'DRY-RUN'} {len(content)} 字节 → {target}")
        changed += 1
        if yes:
            if target.exists():
                target.with_suffix(".md.bak").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            # 脚本
            try:
                scripts = json.loads(s.get("scripts_json") or "{}")
            except Exception:
                scripts = {}
            for fn, code in scripts.items():
                fp = target.parent / "scripts" / fn
                fp.parent.mkdir(parents=True, exist_ok=True)
                if fp.exists():
                    fp.with_suffix(fp.suffix + ".bak").write_text(fp.read_text(encoding="utf-8"), encoding="utf-8")
                fp.write_text(code, encoding="utf-8")
    print(f"pull: {changed} 个技能{'已写入' if yes else '待写入（加 --yes 落盘）'}")


def do_push(cfg, yes):
    # push 用本机导出包，逐条 PATCH 到服务器
    pwd = cfg.get("password") or cfg.get("api_key")
    tok = api(cfg, "/api/auth/login", "POST", {"password": pwd})["token"]
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    # 直接复用导出逻辑
    from export_skills import NAMES, SKILLS_DIR, RELATED
    for name in NAMES:
        d = SKILLS_DIR / name
        sk = d / "SKILL.md"
        if not sk.exists():
            continue
        content = sk.read_text(encoding="utf-8")
        scripts = {}
        sdir = d / "scripts"
        if sdir.exists():
            for f in sorted(sdir.iterdir()):
                if f.is_file() and f.suffix in (".py", ".js", ".sh", ".md"):
                    scripts[f.name] = f.read_text(encoding="utf-8", errors="replace")
        sid = "s_" + hashlib.sha1(name.encode()).hexdigest()[:12]
        body = {"content": content, "scripts_json": json.dumps(scripts, ensure_ascii=False),
                "related_json": json.dumps(RELATED.get(name, []), ensure_ascii=False),
                "source_sha": sha(content)}
        print(f"[{name}] {'PUSH' if yes else 'DRY-RUN'} {len(content)} 字节 | 脚本 {len(scripts)}")
        if yes:
            try:
                api(cfg, "/api/skills/" + sid, "PATCH", body, token=tok)
            except urllib.error.HTTPError as e:
                print(f"    失败 HTTP {e.code}: {e.read().decode()[:100]}")
    print(f"push: {'已完成' if yes else '加 --yes 真正推送'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--direction", choices=["pull", "push"], required=True)
    ap.add_argument("--yes", action="store_true", help="真正落盘/推送（默认只预览）")
    ap.add_argument("--force", action="store_true", help="pull 时忽略 sha 冲突")
    args = ap.parse_args()
    cfg = load_cfg()
    if args.direction == "pull":
        do_pull(cfg, args.yes, args.force)
    else:
        do_push(cfg, args.yes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
