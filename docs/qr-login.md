# 扫码登录

支持已登录设备扫码授权未登录设备，适用于无法直接访问 Google OAuth 的设备（如内网设备、无 Google 服务的浏览器等）。

## 流程

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

## 入口

- **未登录用户**：门户首页和登录页均有「扫码登录」按钮，点击显示二维码
- **已登录用户**：用户栏有「扫码」按钮，点击打开摄像头扫描器（基于 jsQR）

## API

| Method | Endpoint | 说明 |
|--------|----------|------|
| POST | `/auth/qr/create` | 创建 QR 会话，返回 `{sid, svg, expires_in}` |
| GET | `/auth/qr/status?sid=` | 轮询状态（pending/confirmed/expired） |
| GET | `/auth/qr/confirm?sid=` | 扫描端确认页面（需登录） |
| POST | `/auth/qr/confirm` | 确认授权（CSRF 保护） |
| GET | `/auth/qr/token?sid=` | 设置 cookie 并跳转首页 |

## 安全设计

- QR 会话 5 分钟过期，内存存储（无需数据库）
- Token 一次性使用，二次访问返回 410
- 确认端点需要 CSRF 校验 + 已登录状态
- 未登录设备扫码会先跳转 Google OAuth
- 操作记入审计日志（`qr-login`）
