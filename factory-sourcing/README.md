# 源厂河北（MVP）

河北产业带 / 源头工厂采购平台第一版。

## 当前能力

- 首页产品、产业带、企业关键词搜索
- 河北产业带列表与 SEO 详情页
- 企业库与企业 SEO 详情页
- 工厂入驻流程预留
- 自动 sitemap / robots
- 移动端适配
- 首版数据通过公开 JSON API 获取，并做 24 小时缓存

## 数据来源

首版引用：河北内卷网《河北产业开放数据》v3，CC BY 4.0。
公开数据 API：`https://hebeineijuan.com/api/v1/`

后续正式运营建议迁移至自有 PostgreSQL/Supabase 数据库，并保留原始数据引用字段。

## 本地运行

```bash
npm install
npm run dev
```

## 部署到 Vercel

1. 导入 GitHub 仓库 `Andy-jx/main`
2. Root Directory 选择 `factory-sourcing`
3. Framework 选择 Next.js（通常自动识别）
4. 设置环境变量：
   - `NEXT_PUBLIC_SITE_URL=https://你的域名`
   - 可选：`DATA_API_BASE=https://hebeineijuan.com/api/v1`
5. Deploy

## 域名绑定

域名注册后，在 Vercel 项目 Settings -> Domains 添加域名，再按 Vercel 提示到域名 DNS 控制台添加 A/CNAME 记录。

## 下一阶段

- Supabase/PostgreSQL 自有数据库
- 管理后台：产业 / 工厂 / 产品 / 入驻审核
- 在线询盘
- 产品索引与按城市筛选
- 中英文页面
- 企业自主维护资料
- 数据导入与来源审计
