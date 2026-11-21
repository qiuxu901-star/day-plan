#!/usr/bin/env python3
"""双向同步桥接器 —— 必须在用户 Mac 的 WorkBuddy 会话内运行。

为什么在 Mac：WorkBuddy 平台数据 API 靠桌面宿主 IPC 认证，服务器无法直连。
方向：
  下行 platform -> server : 拉平台全量快照 POST /api/sync/push（跳过 pending）
  回写 server -> platform : 读 /api/sync/pending，逐条写回平台，再 POST /api/sync/ack
裁决：平台为主真源；本地 pending 优先（防覆盖本地新写）；双改冲突记 sync_conflicts。

用法：
  python3 sync_bridge.py --mode full      # 全量下行 + 回写
  python3 sync_bridge.py --mode down      # 仅下行
  python3 sync_bridge.py --mode up        # 仅回写
  python3 sync_bridge.py --dry-run        # 只报告不落库
"""
import json
import os
import sys
import argparse
import datetime
import pathlib
import subprocess
import urllib.request
import urllib.error

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT = REPO / "data"
EXPORT = ROOT / "export"
CONFIG = pathlib.Path.home() / ".workbuddy" / "workboard" / "config.json"
SKILL_DIR = pathlib.Path(
    "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/"
    "resources/plugins/workbuddy-builtin/skills/library/database"
)

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


def load_config():
    if not CONFIG.exists():
        raise SystemExit(f"缺少配置 {CONFIG}，需含 base_url/api_key")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not cfg.get("base_url") or not cfg.get("api_key"):
        raise SystemExit("config.json 必须含 base_url 和 api_key")
    return cfg


def refresh_token(cfg):
    """每次运行先登录换 token，避免 JWT 7 天过期导致同步静默停摆。"""
    password = cfg.get("password") or cfg.get("api_key")
    url = cfg["base_url"].rstrip("/") + "/api/auth/login"
    data = json.dumps({"password": password}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cfg["_token"] = json.loads(r.read().decode())["token"]
    return cfg["_token"]


def api(cfg, path, method="GET", body=None):
    url = cfg["base_url"].rstrip("/") + path
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + cfg.get("_token", cfg.get("api_key", "")),
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise RuntimeError(f"HTTP {e.code} {path}: {detail}")


def platform_query(dbid, page_size=200):
    """调平台脚本拉全量（宿主 IPC 认证）。"""
    rows, cursor = [], ""
    while True:
        args = ["python3", str(SKILL_DIR / "query_database_record.py"),
                "--database-id", dbid, "--page-size", str(page_size)]
        if cursor:
            args += ["--start-cursor", cursor]
        p = subprocess.run(args, capture_output=True, text=True, timeout=180)
        raw = p.stdout.strip()
        i = raw.find("{")
        if i < 0:
            raise RuntimeError(f"平台查询失败 {dbid}: {raw[:200] or p.stderr[:200]}")
        data = json.loads(raw[i:])
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        nxt = data.get("next_cursor")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
    return rows


_SCHEMA_CACHE = {}


def field_types(dbid):
    """拉取字段类型映射：select/date 必须用对应 oneof，否则平台静默存空。"""
    if dbid in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[dbid]
    p = subprocess.run(
        ["python3", str(SKILL_DIR / "get_database_schema.py"),
         "--database-id", dbid], capture_output=True, text=True, timeout=120)
    raw = p.stdout.strip()
    i = raw.find("{")
    if i < 0:
        raise RuntimeError(f"取 schema 失败 {dbid}: {raw[:200]}")
    schema = json.loads(raw[i:])
    types = {f["name"]: f.get("type", "text")
             for f in schema.get("properties", [])}
    _SCHEMA_CACHE[dbid] = types
    return types


def wrap_oneof(payload, types):
    """按字段类型包装 PropertyValue；select/date/number 不可统一用 text。"""
    out = {}
    for k, v in payload.items():
        if k == "record_id" or v is None:
            continue
        t = types.get(k, "text")
        if t == "select":
            out[k] = {"select": str(v)}
        elif t == "date":
            out[k] = {"date": str(v)}
        elif t == "number":
            out[k] = {"number": v if isinstance(v, (int, float)) else float(v)}
        else:
            out[k] = {"text": str(v)}
    return out


def platform_write(dbid, op, rid, payload):
    """回写平台：add / update / delete。字段值按类型做 oneof 包装。"""
    script = {"add": "batch_add_database_records.py",
              "update": "batch_update_database_records.py",
              "delete": "batch_delete_database_records.py"}[op]
    if op == "add":
        recs = [wrap_oneof(payload, field_types(dbid))]
    elif op == "update":
        recs = [{"record_id": rid,
                 "properties": wrap_oneof(payload, field_types(dbid))}]
    else:
        recs = [{"record_id": rid}]
    args = ["python3", str(SKILL_DIR / script),
            "--database-id", dbid, "--records", json.dumps(recs, ensure_ascii=False)]
    p = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if p.returncode != 0 or "error" in p.stdout.lower():
        raise RuntimeError(f"平台回写失败 {op} {rid}: {p.stdout[:200]} {p.stderr[:100]}")
    return True


def down_sync(cfg, dry=False):
    """平台 -> 新库。拉平台快照推送；pending 记录由服务端跳过。"""
    result = {"pushed": {}, "errors": []}
    for table, dbid in TABLES.items():
        if table == "subtask":
            continue  # 平台表已失效
        try:
            rows = platform_query(dbid)
            if dry:
                result["pushed"][table] = len(rows)
                continue
            resp = api(cfg, "/api/sync/push", "POST",
                       {"table": table, "records": rows})
            result["pushed"][table] = resp
        except Exception as e:
            result["errors"].append(f"{table}: {e}")
    return result


def up_sync(cfg, dry=False):
    """新库 -> 平台。读 pending 逐条回写，成功后 ack。"""
    pending = api(cfg, "/api/sync/pending")
    result = {"total": len(pending), "written": 0, "acked": [], "errors": []}
    for item in pending:
        table, op, rid = item["table_name"], item["op"], item["record_id"]
        dbid = TABLES.get(table)
        if not dbid:
            result["errors"].append(f"未知表 {table} id={item['id']}")
            continue
        try:
            payload = json.loads(item.get("payload") or "{}")
            if not dry:
                platform_write(dbid, op, rid, payload)
                api(cfg, "/api/sync/ack", "POST", {"ids": [item["id"]]})
                result["acked"].append(item["id"])
            result["written"] += 1
        except Exception as e:
            result["errors"].append(f"{table}/{op}/{rid}: {e}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["full", "down", "up"], default="full")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    try:
        refresh_token(cfg)
    except Exception as e:
        raise SystemExit(f"登录自托管 API 失败（检查 config.json 的 password）: {e}")
    out = {"at": datetime.datetime.now().isoformat(timespec="seconds"),
           "mode": args.mode, "dry": args.dry_run}
    if args.mode in ("full", "down"):
        out["down"] = down_sync(cfg, args.dry_run)
    if args.mode in ("full", "up"):
        out["up"] = up_sync(cfg, args.dry_run)

    logdir = ROOT / "sync_logs"
    if not logdir.exists():
        logdir.mkdir()
    logfile = logdir / (datetime.date.today().isoformat() + ".jsonl")
    with logfile.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
