#!/usr/bin/env bash
# 重新生成「云托管上传包」：yanquan-cloudrun.zip
# 用法：bash scripts/make_cloudrun_zip.sh
# 输出：scripts/yanquan-cloudrun.zip（部署时上传这个文件即可）
set -e
cd "$(dirname "$0")/.."

rm -rf scripts/cloudrun/backend
mkdir -p scripts/cloudrun/backend
rsync -a --exclude '.env' --exclude 'data' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude 'tests' --exclude '*.db' --exclude '.DS_Store' \
  backend/ scripts/cloudrun/backend/

cd scripts/cloudrun
rm -f ../yanquan-cloudrun.zip
zip -qr ../yanquan-cloudrun.zip .
cd ..
echo "已生成：$(pwd)/yanquan-cloudrun.zip"
ls -la yanquan-cloudrun.zip
