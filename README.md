# Kazusa Home Portal

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Docker-label 驱动的 Web 服务门户，集成 Google OAuth、扫码登录、角色访问控制和 Traefik forwardAuth 网关。

## 架构

```
浏览器 → Traefik → kazusa-auth@docker (forwardAuth) → /auth/verify
                      ↓ 200                     ↓ 401/403
                 上游服务（带 X-User-* headers）   错误页面 / 登录重定向
```

1. Traefik 通过 `kazusa-auth@docker` 中间件调用 `/auth/verify`
2. 验证 session cookie → 检查角色/用户 ACL → 通过则注入 `X-User-*` headers 转发

## 功能

- **服务发现** — 自动扫描带 `homepage.*` labels 的 Docker 容器，展示为卡片网格
- **Google OAuth** — Web 应用类型 OAuth 2.0，首次登录自动应用角色预设
- **[扫码登录](docs/qr-login.md)** — 已登录设备扫码授权未登录设备，支持摄像头实时识别
- **[角色 ACL](docs/acl.md)** — 两层 ACL（角色优先 + 用户兜底），支持 fnmatch 通配符
- **[安全特性](docs/security.md)** — CSRF、Rate Limiting、Session 服务端撤销、审计日志
- **[API Token](docs/api-tokens.md)** — 创建个人 Bearer Token，程序化访问所有受保护服务
- **[Session 管理](docs/sessions.md)** — 查看/撤销已登录设备
- **真实健康检查** — 首页服务卡片异步 HTTP 探活，异常标红
- **自动 Migration** — 启动时自动执行未应用的 SQL migration
- **健康检查端点** — `/health` 暴露 DB、Docker 状态，供 compose healthcheck 使用
- **公告系统** — 全局公告（info/warn/error），Admin UI 管理，首页自动展示
- **PWA** — `manifest.json` + Service Worker（stale-while-revalidate）
- **深色模式** — 三态切换（跟随系统 / 浅色 / 深色），localStorage 持久化
- **Pydantic 类型** — 前后端 API 请求/响应模型校验

## 服务注册

在目标服务的 `docker-compose.yml` 中添加 labels：

```yaml
labels:
  - "homepage.enable=true"
  - "homepage.title=My Service"
  - "homepage.description=A brief description"
  - "homepage.icon=🔧"
  # 启用认证
  - "traefik.http.routers.my-service.middlewares=kazusa-auth@docker"
```

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `DOMAIN` | 主域名 | `example.com` |
| `GOOGLE_CLIENT_ID` | OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | OAuth Client Secret | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | 回调地址 | `https://home.example.com/auth/callback` |
| `SESSION_SECRET` | Cookie 签名密钥 | 64 位随机 hex |
| `SESSION_MAX_AGE` | Session 有效期（秒） | `2592000` |
| `COOKIE_DOMAIN` | Cookie 域名 | `.example.com` |
| `PORTAL_URL` | 门户地址 | `https://example.com` |
| `PORTAL_HOSTS` | 门户域名白名单 | `example.com,home.example.com` |
| `ADMIN_EMAIL` | 默认管理员邮箱 | `admin@example.com` |
| `DB_*` | PostgreSQL 连接 | — |

## 部署

```bash
cp .env.example .env && nano .env
docker compose up -d
```

**前置要求：** Docker + Compose、Traefik v3、PostgreSQL、Google OAuth 2.0 凭据

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + uvicorn |
| 前端 | 原生 HTML/CSS/JS SPA |
| 数据库 | PostgreSQL（7 张表） |
| 认证 | Google OAuth 2.0 + HMAC-SHA256 session |
| 扫码 | segno（SVG 生成）+ jsQR（摄像头识别） |
| 代理 | Traefik v3 + forwardAuth |
| 限流 | slowapi |
| 包管理 | uv |

## 文档

- [扫码登录](docs/qr-login.md) — 设备间扫码授权流程、API、安全设计
- [ACL 管理](docs/acl.md) — 角色 ACL、用户 ACL、Admin API、跨服务鉴权
- [安全特性](docs/security.md) — Session、CSRF、CORS、限流、审计日志
- [API Token](docs/api-tokens.md) — Token 方案、Schema、使用示例
- [Session 管理](docs/sessions.md) — 查看、撤销活跃 Session，设备信息跟踪
- [数据库迁移](docs/migrations.md) — 自动 migration 运行机制、baseline 策略

## License

[Apache License 2.0](LICENSE)
