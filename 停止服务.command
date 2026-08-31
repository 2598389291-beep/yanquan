#!/usr/bin/env bash
# ============================================================
# 「言权」一键停止（双击本文件即可）
# 作用：关闭后端 + 预览服务，释放笔记本资源
# 重新打开：双击「启动演示.command」
# ============================================================

UID_NUM=$(id -u)

launchctl bootout gui/$UID_NUM ~/Library/LaunchAgents/com.yanquan.backend.plist 2>/dev/null
launchctl bootout gui/$UID_NUM ~/Library/LaunchAgents/com.yanquan.h5.plist 2>/dev/null

echo "后端和预览服务已停止 ✓（不占用算力）"
echo "（按任意键关闭本窗口）"
read -r _
