#!/usr/bin/env bash
# ============================================================
# 「言权」一键启动（双击本文件即可）
# 作用：启动后端 + 预览服务，然后打开微信开发者工具
# 关闭服务：双击「停止服务.command」
# 备注：浏览器网页预览是备用入口，需要时手动打开
#       http://127.0.0.1:8090
# ============================================================

UID_NUM=$(id -u)

echo "== 启动后端服务 =="
launchctl bootstrap gui/$UID_NUM ~/Library/LaunchAgents/com.yanquan.backend.plist 2>/dev/null
launchctl kickstart gui/$UID_NUM/com.yanquan.backend 2>/dev/null
sleep 4
if curl -s -m 2 http://127.0.0.1:8000/health > /dev/null 2>&1; then
  echo "  后端启动成功 ✓"
else
  echo "  后端启动失败，请稍后重试或检查日志 /private/tmp/yanquan_backend.log"
fi

echo "== 启动预览服务 =="
launchctl bootstrap gui/$UID_NUM ~/Library/LaunchAgents/com.yanquan.h5.plist 2>/dev/null
launchctl kickstart gui/$UID_NUM/com.yanquan.h5 2>/dev/null
sleep 2

echo "== 打开微信开发者工具 =="
open -a wechatwebdevtools

echo ""
echo "完成！微信开发者工具已打开，点「编译」即可预览。"
echo "（按任意键关闭本窗口）"
read -r _
