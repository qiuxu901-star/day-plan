#!/bin/bash
# 一键部署到 47.103.25.159 / 2566.online
set -e

APP_DIR="/opt/weekly-board"
DOMAIN="2566.online"

echo "🚀 部署周计划看板到 $DOMAIN..."

# 1. 创建目录
sudo mkdir -p "$APP_DIR"
sudo chown -R $USER:$USER "$APP_DIR"

# 2. 复制文件
cp -r . "$APP_DIR"
cd "$APP_DIR"

# 3. Python 虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 确认 .env 存在
if [ ! -f .env ]; then
    cp deploy/.env.example .env
    echo "⚠️  请编辑 $APP_DIR/.env 填入飞书凭证"
    exit 1
fi

# 5. systemd 服务
sudo cp deploy/weekly-board.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weekly-board

# 6. Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/weekly-board
sudo ln -sf /etc/nginx/sites-available/weekly-board /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 7. HTTPS 证书（如果还没有）
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@$DOMAIN
fi

# 8. 设置密码
if [ ! -f /etc/nginx/.htpasswd ]; then
    echo "⚠️  请设置 Basic Auth 密码: sudo htpasswd -c /etc/nginx/.htpasswd admin"
fi

echo ""
echo "✅ 部署完成！"
echo "🌐 https://$DOMAIN"
echo ""
echo "后续管理："
echo "  sudo systemctl restart weekly-board   # 重启服务"
echo "  sudo journalctl -u weekly-board -f    # 查看日志"
