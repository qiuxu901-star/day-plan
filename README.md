# day-plan

一个部署在 Vercel 上的单页计划录入页。

现在页面会通过同源 `/api/*` 代理自动连接到你的本机写回服务，不需要再在浏览器里手动输入 `ngrok URL` 和 `Bearer Token`。

## 页面能力

- 单页录入周计划 + 日计划
- 自动读取最近 3 个 `WK` 文件
- 切换当前日期
- 承接昨日 `明日优先`
- 承接昨日 `迁移项`
- 保存周计划
- 保存日计划

## 仓库文件

- `index.html`：页面结构
- `styles.css`：页面样式
- `app.js`：前端逻辑
- `api/`：Vercel 服务端代理
- `vercel.json`：Vercel 部署配置

## 工作方式

浏览器访问 Vercel 页面后：

1. 页面请求同源 `/api/*`
2. Vercel 服务端代理转发到当前本机 `ngrok` 地址
3. 代理在服务端附加本机写回 API 所需的 Bearer Token
4. 本机 API 再把内容写回 Obsidian `WK` 文件

## 本机侧要求

本机需要同时运行：

- `00_Codex/day-plan-vercel/start_local_api.sh`
- `00_Codex/day-plan-vercel/start_ngrok.sh`

当前代理默认连接到一次有效的 `ngrok` 地址；如果未来隧道地址变化，建议把它改成 Vercel 环境变量：

- `LOCAL_API_BASE_URL`
- `LOCAL_API_TOKEN`

这样就不需要把当前地址和 token 固化在代码里。
