#!/usr/bin/env bash
# ============================================================
# 「言权」服务器一键部署脚本（Ubuntu 22.04+，备案通过后执行）
# 用法：sudo bash scripts/deploy_server.sh your-api-domain.com
# 示例：sudo bash scripts/deploy_server.sh api.yanquan.cn
# 前置：域名已备案且解析到本服务器 IP
# ============================================================
set -e

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "用法：sudo bash $0 你的域名（如 api.yanquan.cn）"
  exit 1
fi

echo "==> 1/6 安装基础组件（docker / nginx / certbot）"
apt-get update -y
apt-get install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx

echo "==> 2/6 创建项目目录并复制后端代码"
mkdir -p /opt/yanquan/backend
cp -r backend/* /opt/yanquan/backend/
cd /opt/yanquan/backend
rm -rf __pycache__ data

echo "==> 3/6 配置环境变量"
if [ ! -f /opt/yanquan/backend/.env ]; then
  cp .env.example /opt/yanquan/backend/.env
  echo "请编辑 /opt/yanquan/backend/.env，填入 DASHSCOPE_API_KEY / WECHAT_APPID / WECHAT_SECRET"
fi

echo "==> 4/6 构建并启动后端容器（SQLite 与上传文件持久化到宿主机）"
docker build -t yanquan-backend .
mkdir -p /opt/yanquan/data
docker rm -f yanquan 2>/dev/null || true
docker run -d --name yanquan \
  -p 127.0.0.1:8000:8000 \
  -v /opt/yanquan/data:/app/backend/data \
  --restart unless-stopped \
  yanquan-backend

echo "==> 5/6 配置 Nginx 反向代理（仅本机回环访问后端，对外走 443）"
cat > /etc/nginx/sites-available/yanquan <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 20m;
        proxy_read_timeout 120s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/yanquan /etc/nginx/sites-enabled/yanquan
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 6/6 申请 HTTPS 证书（Let's Encrypt 免费证书）"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN" --redirect || \
  echo "证书申请失败，可稍后手动执行：certbot --nginx -d $DOMAIN"

echo ""
echo "部署完成！请验证："
echo "  curl https://$DOMAIN/health"
echo "  → 应返回 {\"status\":\"ok\",\"version\":\"1.1.0\",\"mode\":\"llm\",...}"
echo ""
echo "下一步：把小程序 src/services/api.ts 的 BASE_URL 改为 https://$DOMAIN"
