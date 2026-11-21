#!/usr/bin/env bash
# WorkBoard 一键部署：拉代码 → 同步页面 → 校验配置 → 重启服务 → 健康检查
# 用法：cd <仓库目录> && bash deploy/deploy.sh
# 首次部署会自动 clone 缺失内容；后续只需重跑本脚本。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${WB_APP_DIR:-/home/admin/workboard}"     # 后端运行目录
WEB_DIR="${WB_WEB_DIR:-/opt/workboard/www}"        # nginx 读取的页面目录
SERVICE="workboard"
PORT="${WB_PORT:-8100}"

echo "==> [1/6] 拉取最新代码"
cd "$REPO"
git fetch --quiet origin
git pull --quiet --ff-only origin "$(git rev-parse --abbrev-ref HEAD)"
echo "    当前版本: $(git rev-parse --short HEAD)  $(git log -1 --format=%s)"

echo "==> [2/6] 校验配置文件"
if [ ! -f "$APP_DIR/config/workboard.env" ]; then
  echo "    ⚠️  缺少 $APP_DIR/config/workboard.env"
  echo "    请先: cp $REPO/deploy/workboard.env.example $APP_DIR/config/workboard.env"
  echo "    并填入真实密码与 JWT_SECRET（chmod 600）"
  exit 1
fi
if grep -q '^WB_ADMIN_PASSWORD=CHANGE_ME' "$APP_DIR/config/workboard.env"; then
  echo "    ⚠️  workboard.env 仍是占位密码，请先修改"
  exit 1
fi

echo "==> [3/6] 同步后端代码"
cp "$REPO/server.js" "$APP_DIR/server.js"
echo "    server.js 已更新"

echo "==> [4/6] 同步 H5 页面"
sudo mkdir -p "$WEB_DIR"
sudo cp "$REPO/web/workboard.html" "$WEB_DIR/index.html"
sudo chmod -R a+rX "$WEB_DIR"
echo "    页面已部署到 $WEB_DIR/index.html"

echo "==> [5/6] 重启服务"
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
  sudo systemctl restart "$SERVICE"
else
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$SERVICE"
fi
sleep 2
if ! systemctl is-active --quiet "$SERVICE"; then
  echo "    ❌ 服务启动失败，最近日志："
  sudo journalctl -u "$SERVICE" -n 20 --no-pager
  exit 1
fi
echo "    服务运行中"

echo "==> [6/6] 健康检查"
for i in 1 2 3 4 5; do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/tmp/wb_health.json 2>/dev/null; then
    echo "    ✅ $(cat /tmp/wb_health.json)"
    echo
    echo "部署完成。版本 $(git rev-parse --short HEAD)，地址 https://2566.online/workboard/"
    exit 0
  fi
  sleep 1
done
echo "    ❌ 健康检查失败，最近日志："
sudo journalctl -u "$SERVICE" -n 20 --no-pager
exit 1
