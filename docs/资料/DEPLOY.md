# 「言权」上线部署手册

> 目标：把项目从"本地可运行"变成"微信小程序正式上线"。按顺序执行，全程约 1-2 周（主要耗时在备案与审核）。

---

## 一、部署全景

```
用户微信 → 微信小程序（已发布）→ HTTPS API 域名 → 云服务器（Docker 跑 FastAPI）→ SQLite/后续 MySQL
```

| 组件 | 需要准备 | 成本参考 |
|------|----------|----------|
| 微信小程序账号 | 个人/企业主体注册 | 个人免费 / 企业 300 元/年认证 |
| 云服务器 | 阿里云/腾讯云轻量应用服务器（2C2G 即可） | ~50-100 元/月 |
| 域名 | 1 个（如 api.yanquan.cn）+ ICP 备案 | ~50 元/年 |
| HTTPS 证书 | 免费（Let's Encrypt / 腾讯云免费证书） | 0 元 |
| 阿里云百炼 API Key | https://bailian.console.aliyun.com/ | 按量付费（演示够用） |

---

## 二、后端部署（服务器）

### 2.1 服务器初始化（以 Ubuntu 22.04 为例）

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# 创建项目目录
mkdir -p /opt/yanquan && cd /opt/yanquan
```

> 备案通过后，可用项目内置的一键部署脚本（推荐）：
> ```bash
> sudo bash scripts/deploy_server.sh api.yanquan.cn
> ```
> 脚本会自动安装 Docker/Nginx、构建后端容器、配置 HTTPS，详见脚本内注释。

### 2.2 上传代码并配置

将本地 `backend/` 目录上传到 `/opt/yanquan/`（scp / rsync / Git 均可）。

```bash
cd /opt/yanquan/backend
cp .env.example .env
vim .env
# 必填：DASHSCOPE_API_KEY、ENVIRONMENT=production
# 选填：WECHAT_APPID、WECHAT_SECRET（小程序登录）
```

### 2.3 Docker 构建与启动

```bash
docker build -t yanquan-backend .
docker run -d --name yanquan \
  -p 8000:8000 \
  -v /opt/yanquan/backend/data:/app/backend/data \
  --restart unless-stopped \
  yanquan-backend

# 验证
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"1.0.0","mode":"llm",...}   ← mode 应为 llm
```

> 数据目录挂载到宿主机 `data/`，升级容器不丢数据。

### 2.4 Nginx + HTTPS（反向代理）

```nginx
server {
    listen 443 ssl http2;
    server_name api.yanquan.cn;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    client_max_body_size 20m;   # 语音/图片上传

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;   # AI 生成较慢，放宽超时
    }
}
```

```bash
# 免费证书（certbot）
apt install certbot python3-certbot-nginx
certbot --nginx -d api.yanquan.cn
```

> **重要**：微信小程序要求 **HTTPS + 备案域名**，且不能是 IP 直连。域名 ICP 备案需 7-20 天，请提前办理。

---

## 三、微信小程序发布

### 3.1 准备事项

1. 注册小程序：https://mp.weixin.qq.com
2. 在「开发管理 → 开发设置」获取 **AppID / AppSecret**，填入 `backend/.env`
3. 在「开发管理 → 开发设置 → 服务器域名」配置：
   - request 合法域名：`https://api.yanquan.cn`
   - uploadFile 合法域名：`https://api.yanquan.cn`
4. 在「设置 → 服务内容声明」选择服务类目（工具 → 信息查询 / 生活服务）
5. 在「设置 → 用户隐私保护指引」声明收集的信息（手机号、维权内容、图片）并配置《隐私政策》
6. 若使用微信登录，需在「设置 → 服务内容声明」勾选"用户基本信息"能力

### 3.2 修改 API 地址并构建

编辑 `miniapp/src/services/api.ts`：

```ts
export const BASE_URL = 'https://api.yanquan.cn'   // 生产域名
```

构建：

```bash
cd miniapp
npm run build:weapp
```

### 3.3 上传与审核

1. 打开**微信开发者工具** → 导入 `miniapp/` 目录
2. 点击右上角「上传」→ 填写版本号（1.0.0）与备注
3. 登录小程序后台 →「版本管理」→ 提交审核
4. 审核通过后「发布」

### 3.4 上线前检查清单

- [ ] `project.config.json` 中的 AppID 正确
- [ ] 后端 `/health` 返回 mode=llm、environment=production
- [ ] 域名已备案、HTTPS 证书有效、合法域名已配置
- [ ] 隐私保护指引与《隐私政策》已配置
- [ ] 用户协议/免责声明页面可访问
- [ ] 真机测试：登录、文字生成、语音、OCR、记录同步

---

## 四、常见问题

| 问题 | 原因与解决 |
|------|-----------|
| 小程序请求失败 errno 600001 | 域名未备案 / 未配置 request 合法域名 / 证书无效 |
| 语音识别报错 | 未配置 DASHSCOPE_API_KEY 或模型名不正确 |
| 微信登录失败 401 | WECHAT_APPID/SECRET 未配置或与小程序不匹配 |
| AI 生成超时 | Nginx proxy_read_timeout 调大；LLM 模型换 qwen-plus 提速 |
| 数据丢失 | 容器重启未挂载 data 目录（务必用 -v 挂载） |

---

## 五、生产环境建议（后续迭代）

1. **数据库**：SQLite 单机够用；用户量上来后迁移 PostgreSQL（SQLAlchemy 层抽象）
2. **验证码存储**：当前内存存储 → 接入阿里云短信 + Redis
3. **监控**：接入腾讯云 CLS / 阿里云日志服务
4. **备份**：data 目录每日定时备份（crontab + 对象存储）
5. **CI/CD**：GitHub Actions 构建镜像 → 服务器自动拉取重启


---

## 六、零备案方案：微信云托管（推荐新手，免域名免备案）

> 如果你不想买服务器、不想做 ICP 备案，用微信官方「云托管」（CloudBase Run）最省事：
> 服务器、域名、HTTPS 全部由腾讯提供，**不需要单独备案**，成本按量计费（有免费额度）。

### 6.1 原理

```
小程序 → 云托管服务域名（腾讯提供 https://xxx.ap-shanghai.run.tcloudbase.com）→ FastAPI 容器
```

- 云托管会为服务生成一个 **HTTPS 域名**，这个域名天然在小程序请求白名单体系内（云调用免配置合法域名）
- 我们的后端已带 Dockerfile，云托管可直接用源码/Dockerfile 构建
- 数据库（SQLite）与上传文件都在 `backend/data/`，需挂载云托管**持久化磁盘**

### 6.2 开通步骤

1. **微信开发者工具** → 顶部工具栏点「云开发」→ 按提示开通环境（选按量付费或包月，有免费额度）
2. 控制台进入「云托管」→ 新建服务（地域选离你最近的，如上海）
3. 部署方式选「**Dockerfile 构建**」→ 上传代码包（整个 backend 目录）或关联 Git 仓库
4. 在服务设置里配置**环境变量**（来自 backend/.env）：
   - `DASHSCOPE_API_KEY`（必填）
   - `WECHAT_APPID` / `WECHAT_SECRET`（微信登录）
   - `ENVIRONMENT=production`
5. 配置**持久化磁盘**：挂载到容器路径 `/app/backend/data`（保存数据库和证据文件，避免重启丢失）
6. 部署完成后拿到服务域名，如 `https://backend-xxxx.ap-shanghai.run.tcloudbase.com`

### 6.3 小程序接入

1. 修改 `miniapp/src/services/api.ts`：
   ```ts
   export const BASE_URL = 'https://backend-xxxx.ap-shanghai.run.tcloudbase.com'
   ```
2. `npm run build:weapp`
3. 微信开发者工具重新编译，真机测试登录、文字生成、语音、证据上传
4. 云托管域名若提示需配置合法域名，在小程序后台「开发管理 → 开发设置 → 服务器域名」添加（无需备案）

### 6.4 注意事项

- **数据库持久化**：一定要挂载磁盘，否则容器重建后记录丢失；用户量上来后再迁移到云数据库（MySQL/PostgreSQL）
- **费用**：云托管按量计费，开发期几乎免费；上线后有免费额度，超出部分按量
- **审核流程不变**：云部署解决的是"服务器+备案"，小程序**审核发布**（类目、隐私指引、提审）仍要走，这部分是必须的