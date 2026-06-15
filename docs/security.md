# 安全特性

## Session 管理

- **HMAC-SHA256 签名** — Token 格式 `user_id.email.timestamp.signature`，防篡改
- **服务端撤销** — Token hash 存储在 `home_sessions`，支持单点登出
- **并发上限** — 每用户最多 10 个活跃 session，超出自动淘汰最旧的
- **过期清理** — 每次创建新 session 时自动清除过期记录

## CSRF 保护

- Token 从 session cookie HMAC 派生：`HMAC(SECRET, "csrf:{session_token}")[:32]`
- `/api/me` 返回 `csrf` 字段供前端消费
- 所有状态变更请求（POST/PUT/DELETE）通过 `X-CSRF-Token` header 校验
- 前端 `apiFetch()` 自动注入 header

## CORS

- `allow_origins` 限制为门户域名（非 `*`）
- `allow_headers` 限制为 `Content-Type, X-CSRF-Token`
- `allow_credentials=True` 支持 cookie 认证

## Rate Limiting

| 端点 | 限制 |
|------|------|
| 全局默认 | 120/min/IP |
| 登录回调 | 10/min |
| 删除用户 | 10/min |
| 修改角色 | 30/min |
| 服务列表 | 60/min |

## 其他

- **OAuth State 签名** — `auth_login` 对 return URL 做 HMAC 签名，`auth_callback` 验证后才使用，防止开放重定向
- **Docker API 缓存** — 30s TTL + 后台线程刷新，避免每次请求调用 Docker socket
- **DB 连接池** — psycopg2 `ThreadedConnectionPool(2, 10)`
- **审计日志** — 所有 admin 变更自动记录到 `home_audit_log`
- **HTTP headers 编码** — `X-User-Name` 使用 URL 编码，避免非 ASCII 字符导致 `UnicodeEncodeError`

## 公告系统

管理员可通过 Admin UI 发布全局公告，支持 `info`（蓝色）、`warn`（橙色）、`error`（红色）三个级别，可切换启用/禁用。门户首页自动展示活跃公告，支持客户端侧关闭。
