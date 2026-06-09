#!/bin/bash
# 健康检查脚本：API 连续 3 次失败则重启服务
# 用法：crontab -e 添加  */5 * * * * /opt/weekly-board/scripts/healthcheck.sh

HEALTH_URL="http://127.0.0.1:8000/api/health"
MAX_FAILURES=3
FAIL_FILE="/tmp/weekly-board-fail-count"

# 健康检查
if curl -sf --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
    echo "[$(date)] ✅ 服务正常"
    rm -f "$FAIL_FILE"
    exit 0
fi

# 记录失败次数
if [ -f "$FAIL_FILE" ]; then
    FAIL_COUNT=$(cat "$FAIL_FILE")
else
    FAIL_COUNT=0
fi
FAIL_COUNT=$((FAIL_COUNT + 1))
echo "$FAIL_COUNT" > "$FAIL_FILE"

echo "[$(date)] ⚠️ 健康检查失败 ($FAIL_COUNT/$MAX_FAILURES)"

if [ "$FAIL_COUNT" -ge "$MAX_FAILURES" ]; then
    echo "[$(date)] 🔄 连续 $MAX_FAILURES 次失败，重启服务..."
    sudo systemctl restart weekly-board
    rm -f "$FAIL_FILE"
    echo "[$(date)] ✅ 服务已重启"
fi
