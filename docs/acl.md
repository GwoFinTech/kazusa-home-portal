# ACL 管理

系统采用**角色优先**的两层 ACL 架构。

## 检查顺序

1. **`home_role_acl`** — 按 `(domain, role)` 匹配，支持 fnmatch 通配符（优先）
2. **`home_acl`** — 按 `(domain, email)` 匹配，支持 fnmatch 通配符（兜底）

## 角色 ACL（推荐）

按角色批量授权，同一角色的用户共享权限：

```sql
-- admin 角色可访问所有 kazusa 服务
INSERT INTO home_role_acl (domain, role) VALUES ('*.kazusa.feng.moe', 'admin');

-- user 角色可访问门户首页
INSERT INTO home_role_acl (domain, role) VALUES ('home.kazusa.feng.moe', 'user');

-- 自定义角色（角色不限于 admin/user，任意字符串均可）
INSERT INTO home_role_acl (domain, role) VALUES ('quant.kazusa.feng.moe', 'quant');
```

### 特殊角色 `user`

**所有已登录用户都隐式拥有 `user` 基准角色**。
这意味着：

- 角色为 `quant` 的用户，也会自动匹配 `role='user'` 的角色 ACL 规则
- 只要给用户分配了任何角色（`quant`、`friend`、`admin` 等），他/她都能访问所有 `user` 组下的站点
- 如果某个站点只希望特定角色访问，请仅创建该角色的规则（如 `role='quant'`），不要创建 `role='user'` 规则

## 角色预设

在用户首次登录前预分配角色：

```sql
-- 用户首次 Google 登录时自动获得指定角色
INSERT INTO home_role_presets (email, role) VALUES ('friend@example.com', 'friend');
```

## 用户级 ACL（兜底）

当角色规则不匹配时，按邮箱精确/通配匹配：

```sql
-- 允许特定用户访问特定服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', 'user@example.com', true);

-- 允许所有已登录用户访问某个服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('app.example.com', '*@*', true);

-- 允许特定域名邮箱访问所有服务
INSERT INTO home_acl (domain, email, enabled) VALUES ('*.example.com', '*@company.com', true);
```

## Admin API

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
