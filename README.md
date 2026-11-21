# WorkBoard · 工作计划台

个人工作/时间/想法/计划的统一管理平台。双端并存、双向同步：

- **WorkBuddy 平台页**（原链接）：数据经平台数据表存储，靠宿主 IPC 读写
- **自有服务器 H5**：`https://2566.online/workboard/`，Node 22 + 内置 SQLite，多端可写

## 架构

```
WorkBuddy 会话（唯一能访问平台 IPC 的环境）
  └─ scripts/sync_bridge.py  每小时双向同步
       ├─ 下行：平台 8 张表 → 服务器（跳过 pending）
       └─ 回写：服务器本地新增/修改 → 平台（成功后 ack）
                    ↓
服务器 47.103.25.159 : 2566.online
  ├─ server.js       Node 22 单文件后端，零 npm 依赖
  ├─ SQLite          8 张表，data/workboard.db（不进 git）
  └─ nginx 443       /workboard/ + /workboard/api/
```

**技术选择说明**：服务器 Python 仅 3.6.8，无法运行现代 FastAPI，故后端用 Node 22 内置 `node:sqlite` 实现，与服务器已有的 CSR 服务同运行时。

## 目录

| 路径 | 用途 |
|---|---|
| `server.js` | 后端 API（CRUD / JWT / API Key / 限流 / AI 代理 / 同步接口）|
| `web/workboard.html` | H5 页面成品，部署到 nginx |
| `web/workboard.fusion.html` | 页面源文件（平台版），改页面从这里改 |
| `scripts/make_h5.py` | 由源文件生成自托管版（删 inject.js、换数据层）|
| `scripts/export_workboard.py` | 从平台导出 8 张表 schema + 全量数据 |
| `scripts/build_db.py` | 建 SQLite 库并做四项校验 |
| `scripts/sync_bridge.py` | 双向同步桥接器（在 WorkBuddy 会话内运行）|
| `scripts/verify_h5.js` | jsdom 回放验证页面 |
| `deploy/` | 部署脚本与配置模板 |

## 日常开发：改代码 → 部署

```bash
# 本地改代码后
git add -A && git commit -m "改动说明" && git push

# 服务器上一条命令完成更新
cd /home/admin/workboard && bash deploy/deploy.sh
```

部署脚本会：拉代码 → 校验配置 → 复制 server.js 与页面 → 重启服务 → 健康检查。失败会明确报错并打印服务日志。

## 首次部署（新服务器）

1. 装 Node 22（服务器已装于 `/usr/local/node22/bin/node`）
2. clone 仓库：`git clone https://github.com/qiuxu901-star/day-plan.git /home/admin/workboard`
3. 配置环境：
   ```bash
   cp deploy/workboard.env.example /home/admin/workboard/config/workboard.env
   # 修改 WB_JWT_SECRET 与 WB_ADMIN_PASSWORD，chmod 600
   sudo cp deploy/workboard.service /etc/systemd/system/workboard.service
   sudo cp deploy/nginx-locations.conf /etc/nginx/snippets/workboard-locations.conf
   # 在 443 server 块 include 该片段，nginx -t && nginx -s reload
   ```
4. 导入数据（首次）：在 WorkBuddy 会话内运行 `scripts/export_workboard.py` → `scripts/build_db.py`，把 `data/workboard.db` 传到服务器 `data/`
5. 部署：`bash deploy/deploy.sh`

## 数据迁移与同步（在用户 Mac 的 WorkBuddy 会话内执行）

平台数据 API 靠桌面宿主 IPC 认证，**服务器无法直连**，所以导出与同步脚本必须在 WorkBuddy 会话里跑。

```bash
python3 scripts/export_workboard.py          # 导出 → data/export/
python3 scripts/build_db.py                  # 建库 + 四项校验
cp deploy/sync-config.example.json ~/.workbuddy/workboard/config.json   # 填密码
python3 scripts/sync_bridge.py --mode full   # 双向同步
```

同步裁决：**平台为主真源 + 本地 pending 优先**，避免双主写冲突；极端冲突记入 `sync_conflicts` 表，不自动覆盖。

## API

- `GET /api/healthz` 健康检查
- `POST /api/auth/login` 登录取 JWT
- `GET|POST|PATCH|DELETE /api/v1/{table}` 业务 CRUD（JWT）
- `GET|POST /api/external/v1/{table}` 开放 API（`X-API-Key`，默认只读）
- `POST /api/ai/chat`、`/api/ai/actions/top3` AI 能力（需配置端点）
- `/api/sync/*` 同步桥接专用

表名白名单：`task / review / milestone / time / week / log / inbox / subtask`

## 密码与密钥

**密码绝不进 git。** 改管理员密码需同时改两处且保持一致：

1. 服务器 `/home/admin/workboard/config/workboard.env` 的 `WB_ADMIN_PASSWORD`
2. 本机 `~/.workbuddy/workboard/config.json` 的 `password`

AI 端点在 `workboard.env` 的 `AI_BASE_URL / AI_API_KEY / AI_MODEL`，留空则 AI 问答返回 503。

## 备份

`/etc/cron.d/workboard-backup` 每日 03:30 用 sqlite3 `.backup` 生成快照，gzip 后保留 30 天。`data/` 与 `config/` 均不进 git，需单独备份。
