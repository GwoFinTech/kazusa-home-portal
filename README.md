# Kazusa Home Portal

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

基于 Docker labels 的 Web 服务门户系统，提供服务展示、Google OAuth 登录和基于 ACL 的访问控制。

## 架构

```
浏览器 → Traefik → kazusa-auth@docker (forwardAuth) → /auth/verify
                      ↓ 200                     ↓ 401/403
                 上游服务（带 X-User-* headers）   错误页面 / 登录重定向
```

**认证流程：**
1. Traefik 收到请求，通过 `kazusa-auth@docker` 中间件调用 `/auth/verify`
2. 验证 session cookie（HMAC-SHA256 签名）
3. 检查 ACL（`home_acl` 表，支持 glob 匹配）
4. 通过 → 设置 `X-User-Id/Email/Name/Role` headers 转发给上游
5. 失败 → 返回 401（未登录）或 403（无权限）错误页面

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

通过 `/admin` 页面或直接操作 `home_acl` 表：

```sql
-- 允许特定用户访问特定服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', 'user@example.com', true);

-- 允许所有已登录用户访问某个服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', '*@*', true);

-- 允许特定域名邮箱访问所有服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('*.example.com', '*@company.com', true);
```

## 环境变量

参见 [`.env.example`](.env.example)，所有配置项说明：

| 变量 | 说明 | 示例 |
|------|------|------|
| `DOMAIN` | 主域名（Traefik Host 规则） | `example.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | OAuth 回调地址 | `https://home.example.com/auth/callback` |
| `SESSION_SECRET` | Session cookie 签名密钥 | 64 位随机 hex |
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
- **数据库：** PostgreSQL
- **认证：** Google OAuth 2.0 + HMAC-SHA256 session
- **反向代理：** Traefik v3 + forwardAuth
- **包管理：** uv (pyproject.toml + uv.lock)

## License

[Apache License 2.0](LICENSE)
