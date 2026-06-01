# Kazusa Home Portal

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

## 域名策略

| 域名 | 说明 |
|------|------|
| `kazusa.feng.moe` | 门户主页（公开） |
| `home.kazusa.feng.moe` | 门户主页别名（公开） |
| `*.kazusa.feng.moe` | 受保护服务（需登录 + ACL） |
| `*.milktea-jp1.feng.moe` | 旧域名（公开，向后兼容） |

## 服务注册

在 `docker-compose.yml` 中添加 `homepage.*` labels：

```yaml
labels:
  - "homepage.enable=true"
  - "homepage.title=My Service"
  - "homepage.description=A brief description"
  - "homepage.icon=🔧"
  - "homepage.category=Tools"
  - "homepage.order=10"
  # 启用认证
  - "traefik.http.routers.my-service.middlewares=kazusa-auth@docker"
```

## ACL 管理

通过 `/admin` 页面或直接操作 `home_acl` 表：

```sql
-- 允许特定用户访问特定服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('gex.kazusa.feng.moe', 'user@example.com', true);

-- 允许所有用户访问（通配符）
INSERT INTO home_acl (domain, email, enabled) VALUES ('*.kazusa.feng.moe', '*@*', true);
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | OAuth 回调地址 |
| `SESSION_SECRET` | Session cookie 签名密钥 |
| `ADMIN_EMAIL` | 默认管理员邮箱 |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` | PostgreSQL 连接 |
| `PORTAL_URL` | 门户地址 |

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

## 技术栈

- **后端：** FastAPI + uvicorn
- **前端：** 原生 HTML/CSS/JS（SPA）
- **数据库：** PostgreSQL
- **认证：** Google OAuth 2.0 + HMAC-SHA256 session
- **反向代理：** Traefik v3 + forwardAuth
- **包管理：** uv (pyproject.toml + uv.lock)
