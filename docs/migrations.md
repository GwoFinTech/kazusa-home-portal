# 数据库迁移

项目启动时会自动检查 `app/migrations/` 目录，按文件名排序执行未应用的 SQL migration。

## 运行机制

1. 创建 `home_migrations` 表（若不存在）
2. 检查 `home_migrations` 是否为空且核心表 `home_users` 已存在
   - 若是，将小于等于 `BASELINE_MIGRATION` 的 migration 标记为已应用（免费升级旧部署）
3. 遍历 `app/migrations/*.sql`，对每个未在 `home_migrations` 中的文件：
   - 在事务中执行 SQL
   - 成功后插入 `home_migrations`
   - 失败则回滚

## 添加新 migration

按照顺序命名：

```
app/migrations/004_new_feature.sql
```

内容示例：

```sql
-- Migration 004: new feature
ALTER TABLE home_users ADD COLUMN IF NOT EXISTS nickname TEXT;
```

## Baseline 策略

- 全新部署：直接运行所有 migration
- 已有部署：修改 `app/db.py` 中的 `BASELINE_MIGRATION` 为已手动应用的最新 migration，以免重复执行已存在的表结构
