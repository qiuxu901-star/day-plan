# 周计划看板

整周平铺 + 逐条编辑 + 昨日继承 + 周任务联动。

## 技术栈
- 后端：Python FastAPI + 飞书多维表 API
- 前端：Vue 3 CDN + 参考 day-plan 设计
- 部署：Nginx + systemd

## 快速开始
```bash
pip install -r requirements.txt
cp deploy/.env.example .env  # 编辑填入飞书凭证
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 服务器部署
```bash
bash scripts/deploy.sh
htpasswd -c /etc/nginx/.htpasswd admin
```
