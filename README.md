# Kazusa Home Portal

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

基于 Docker labels 的 Web 服务门户系统，提供服务展示、Google OAuth 登录、扫码登录和基于角色的访问控制（RBAC）。

## 架构

```
浏览器 → Traefik → kazusa-auth@docker (forwardAuth) → /auth/verify
                      ↓ 200                     ↓ 401/403
                 上游服务（带 X-User-* headers）   错误页面 / 登录重定向
```

**认证流程：**
1. Traefik 收到请求，通过 `kazusa-auth@docker` 中间件调用 `/auth/verify`
2. 验证 session cookie（HMAC-SHA256 签名）
3. 检查 ACL（先查 `home_role_acl` 角色规则，再查 `home_acl` 用户规则，均支持 fnmatch 通配符）
4. 通过 → 设置 `X-User-Id/Email/Name/Role` headers 转发给上游
5. 失败 → 返回 401（未登录）或 403（无权限）错误页面

## 扫码登录

支持已登录设备扫码授权未登录设备，适用于无法直接访问 Google OAuth 的设备（如内网设备、无 Google 服务的浏览器等）。

### 流程

```
设备 B（未登录）                    设备 A（已登录）
     │                                  │
     ├─ 点击「扫码登录」                │
     ├─ POST /auth/qr/create           │
     ├─ 显示二维码 (240x240)            │
     │   ┌─────────────┐               │
     │   │  QR Code     │◄── 摄像头扫描 ┤
     │   │  5 分钟有效   │               │
     │   └─────────────┘               ├─ 打开确认页面
     │                                  ├─ 显示用户信息
     ├─ 轮询 GET /auth/qr/status        ├─ 点击「确认授权」
     │   (每 2 秒)                      ├─ POST /auth/qr/confirm
     │                                  │
     │◄──── status: confirmed ──────────┤
     ├─ 跳转 /auth/qr/token?sid=xxx     │
     ├─ 设置 session cookie             │
     └─ 登录完成，跳转首页              └─ 显示「回到主页 (3)」倒计时
```

### 入口

- **未登录用户**：门户首页和登录页均有「扫码登录」按钮，点击显示二维码
- **已登录用户**：用户栏有「扫码」按钮，点击打开摄像头扫描器（基于 jsQR）

### API

| Method | Endpoint | 说明 |
|--------|----------|------|
| POST | `/auth/qr/create` | 创建 QR 会话，返回 `{sid, svg, expires_in}` |
| GET | `/auth/qr/status?sid=` | 轮询状态（pending/confirmed/expired） |
| GET | `/auth/qr/confirm?sid=` | 扫描端确认页面（需登录） |
| POST | `/auth/qr/confirm` | 确认授权（CSRF 保护） |
| GET | `/auth/qr/token?sid=` | 设置 cookie 并跳转首页 |

### 安全设计

- QR 会话 5 分钟过期，内存存储（无需数据库）
- Token 一次性使用，二次访问返回 410
- 确认端点需要 CSRF 校验 + 已登录状态
- 未登录设备扫码会先跳转 Google OAuth
- 操作记入审计日志（`qr-login`）

## 服务注册

在目标服务的 `docker-compose.yml` 中添加 `homepage.*` labels：

```yaml
labels:
  - "homepage.enable=true"
  - "homepage.title=My Service"
  - "homepage.description=A brief description"
  - "homepage.icon=🔧"
  - "homepage.category=Tools"
  - "homepage.order=10"
  # 启用认证（可选）
  - "traefik.http.routers.my-service.middlewares=kazusa-auth@docker"
```

门户通过 Docker socket 自动发现带有 `homepage.enable=true` 的容器。

## ACL 管理

系统采用**角色优先**的两层 ACL 架构：

### 检查顺序

1. **`home_role_acl`** — 按 `(domain, role)` 匹配，支持 fnmatch 通配符（优先）
2. **`home_acl`** — 按 `(domain, email)` 匹配，支持 fnmatch 通配符（兜底）

### 角色 ACL（推荐）

按角色批量授权，同一角色的用户共享权限：

```sql
-- admin 角色可访问所有 kazusa 服务
INSERT INTO home_role_acl (domain, role) VALUES ('*.kazusa.feng.moe', 'admin');

-- user 角色可访问门户首页
INSERT INTO home_role_acl (domain, role) VALUES ('home.kazusa.feng.moe', 'user');

-- 自定义角色（角色不限于 admin/user，任意字符串均可）
INSERT INTO home_role_acl (domain, role) VALUES ('quant.kazusa.feng.moe', 'quant');
```

### 角色预设

在用户首次登录前预分配角色：

```sql
-- 用户首次 Google 登录时自动获得指定角色
INSERT INTO home_role_presets (email, role) VALUES ('friend@example.com', 'friend');
```

### 用户级 ACL（兜底）

当角色规则不匹配时，按邮箱精确/通配匹配：

```sql
-- 允许特定用户访问特定服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', 'user@example.com', true);

-- 允许所有已登录用户访问某个服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', '*@*', true);

-- 允许特定域名邮箱访问所有服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('*.example.com', '*@company.com', true);
```

### Admin API

| Method | Endpoint | 说明 |
|--------|----------|------|
| GET/POST | `/api/admin/role-acl` | 列出 / 创建角色规则 `{domain, role}` |
| PUT/DELETE | `/api/admin/role-acl/{id}` | 更新 `{enabled, domain, role}` / 删除 |
| GET/POST | `/api/admin/role-presets` | 列出 / 创建角色预设 `{email, role}` |
| PUT/DELETE | `/api/admin/role-presets/{id}` | 更新 `{email, role}` / 删除 |
| GET/POST | `/api/admin/acl` | 列出 / 创建用户规则 `{domain, email}` |
| PUT/DELETE | `/api/admin/acl/{id}` | 更新 `{enabled, domain, email}` / 删除 |
| GET/POST | `/api/admin/announcements` | 列出 / 创建公告 `{message, level}` |
| PUT/DELETE | `/api/admin/announcements/{id}` | 切换 active / 删除 |
| GET | `/api/admin/users` | 用户列表 |
| POST | `/api/admin/users/{id}/role` | 修改用户角色 |
| DELETE | `/api/admin/users/{id}` | 删除用户 |
| GET | `/api/admin/audit-log` | 最近 200 条审计日志 |

## 跨服务鉴权

Traefik forwardAuth 成功后会向下游服务注入 `X-User-Id`、`X-User-Email`、`X-User-Name`（URL 编码）、`X-User-Role` headers。任何接入 `kazusa-auth@docker` 的服务都可以直接读取这些 headers 实现角色判断，无需自行实现 OAuth。

```python
from fastapi import Request

def _require_admin(request: Request) -> bool:
    return request.headers.get("X-User-Role", "") == "admin"
```

> ⚠️ 这些 headers 仅在请求经由 Traefik 转发时可信（Traefik 会先剥离客户端伪造的 X-User-* headers 再调用 forwardAuth）。直接访问服务端口时可被伪造。

## 安全特性

- **CSRF 保护** — Token 从 session cookie HMAC 派生，所有状态变更请求（POST/PUT/DELETE）通过 `X-CSRF-Token` header 校验
- **CORS** — `allow_origins` 限制为门户域名，`allow_credentials=True`
- **Rate Limiting** — slowapi 限流：默认 120/min/IP，登录回调 10/min，删除用户 10/min，修改角色 30/min
- **Docker API 缓存** — 30s TTL + 后台线程刷新，避免每次请求都调用 Docker socket
- **DB 连接池** — psycopg2 `ThreadedConnectionPool(2, 10)`
- **审计日志** — 所有 admin 变更自动记录到 `home_audit_log`，Admin UI 可查最近 200 条
- **Session 服务端撤销** — Token hash 存储在 `home_sessions`，支持单点登出和并发会话上限（10/session/user）

## 公告系统

管理员可通过 Admin UI 发布全局公告，支持 `info`（蓝色）、`warn`（橙色）、`error`（红色）三个级别，可切换启用/禁用。门户首页自动展示活跃公告，支持客户端侧关闭。

## PWA 支持

- `manifest.json` — standalone 显示模式，深色主题
- `sw.js` — 静态资源 stale-while-revalidate，跳过 `/api/` 和 `/auth/` 路径

## 环境变量

参见 [`.env.example`](.env.example)，所有配置项说明：

| 变量 | 说明 | 示例 |
|------|------|------|
| `DOMAIN` | 主域名（Traefik Host 规则） | `example.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | OAuth 回调地址 | `https://home.example.com/auth/callback` |
| `SESSION_SECRET` | Session cookie 签名密钥 | 64 位随机 hex |
| `SESSION_MAX_AGE` | Session 有效期（秒） | `2592000`（30 天） |
| `COOKIE_DOMAIN` | Cookie 域名（跨子域共享） | `.example.com` |
| `PORTAL_URL` | 门户地址 | `https://example.com` |
| `PORTAL_HOSTS` | 门户域名白名单（逗号分隔） | `example.com,home.example.com` |
| `ADMIN_EMAIL` | 默认管理员邮箱 | `admin@example.com` |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL 连接 | — |

## 部署

```bash
# 复制并填写环境变量
cp .env.example .env
nano .env

# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f
```

**前置要求：**
- Docker + Docker Compose
- Traefik v3（需配置 `traefik-net` 网络）
- PostgreSQL 实例
- Google Cloud Console 创建的 OAuth 2.0 Web 应用凭据

## 技术栈

- **后端：** FastAPI + uvicorn
- **前端：** 原生 HTML/CSS/JS（SPA）
- **数据库：** PostgreSQL（7 张表：users, sessions, acl, role_acl, role_presets, audit_log, announcements）
- **认证：** Google OAuth 2.0 + HMAC-SHA256 session + CSRF 保护
- **扫码登录：** segno（服务端 SVG 二维码生成）+ jsQR（客户端摄像头扫码）
- **反向代理：** Traefik v3 + forwardAuth
- **限流：** slowapi
- **包管理：** uv (pyproject.toml + uv.lock)

## License

[Apache License 2.0](LICENSE)
