# day-plan

一个部署在 Vercel 上的单页计划录入页。

它本身不直接保存 Obsidian 文件，而是通过 `ngrok` 暴露的本机 API 把内容写回你的 `WK` 文件。

## 页面能力

- 单页录入周计划 + 日计划
- 读取最近 3 个 `WK` 文件
- 切换当前日期
- 承接昨日 `明日优先`
- 承接昨日 `迁移项`
- 保存周计划
- 保存日计划

## 仓库文件

- `index.html`：页面结构
- `styles.css`：页面样式
- `app.js`：前端逻辑
- `vercel.json`：Vercel 静态部署配置

## 本机 API 要求

本机服务需要提供：

- `GET /api/weeks`
- `GET /api/plan`
- `POST /api/save/weekly`
- `POST /api/save/daily`

并要求请求头：

```text
Authorization: Bearer <DAY_PLAN_API_TOKEN>
```

## 本机服务启动

在 Obsidian vault 根目录执行：

```bash
export DAY_PLAN_API_TOKEN="替换成你自己的长 Token"
PYTHONPATH="$PWD/00_Codex" python3 00_Codex/weekly_planner/local_web.py
```

## ngrok 暴露

```bash
ngrok http 8765
```

把生成的公网地址填到页面顶部的 `API Base URL`。

## Vercel 部署

当前仓库已经是静态站点结构，直接在 Vercel 里 `Import Git Repository` 这个仓库即可。
