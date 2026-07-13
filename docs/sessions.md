# Session 管理

用户可以在 `/account/sessions` 页面查看当前账号下所有活跃 Session，并撤销单个或全部（除当前设备外）的登录。

## 设备信息

创建 Session 时会记录：

- IP 地址（优先取 `X-Forwarded-For` 最左侧）
- User-Agent
- 创建时间
- 过期时间
- 最后使用时间

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/me/sessions` | 列出自己的 Session |
| DELETE | `/api/me/sessions/{session_id}` | 撤销指定 Session |
| DELETE | `/api/me/sessions` | 撤销所有其他 Session |

`session_id` 是 session token 的 SHA256 hash，也是 `home_sessions.id` 主键。

## 安全

- 用户只能看到/操作自己的 Session
- 不能撤销当前正在使用的 Session（避免误跳出自己）
- 撤销后相应 token 立即失效
