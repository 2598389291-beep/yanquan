import React, { useState } from 'react'
import { View, Text, Image, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { getComplaintStats } from '../../services/api'
import './index.scss'

const IMG = {
  shield: require('../../assets/icons/shield.png'),
  chevron: require('../../assets/icons/chevron.png'),
  lock: require('../../assets/icons/lock.png'),
  doc: require('../../assets/icons/doc.png'),
  chat: require('../../assets/icons/chat.png'),
}

const ProfilePage: React.FC = () => {
  const [loggedIn, setLoggedIn] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [stats, setStats] = useState({ total: 0, in_progress: 0, categories: 0 })
  const refresh = () => {
    const token = Taro.getStorageSync('token')
    setLoggedIn(!!token)
    setDisplayName(Taro.getStorageSync('nickname') || Taro.getStorageSync('phone') || '')
    if (token) {
      getComplaintStats()
        .then((s) => setStats(s))
        .catch(() => {})
    } else {
      setStats({ total: 0, in_progress: 0, categories: 0 })
    }
  }

  useDidShow(refresh)

  const goLogin = () => Taro.navigateTo({ url: '/pages/login/index' })

  const goAgreement = (type: string) => Taro.navigateTo({ url: `/pages/agreement/index?type=${type}` })

  const handleLogout = () => {
    Taro.showModal({
      title: '退出登录',
      content: '退出后本机将清除登录信息，确定退出吗？',
      success: (res) => {
        if (!res.confirm) return
        Taro.removeStorageSync('token')
        Taro.removeStorageSync('user_id')
        Taro.removeStorageSync('nickname')
        Taro.removeStorageSync('phone')
        setLoggedIn(false)
        setDisplayName('')
        Taro.showToast({ title: '已退出登录', icon: 'success' })
      },
    })
  }

  const menus = [
    { icon: IMG.doc, label: '维权指南', action: () => Taro.navigateTo({ url: '/pages/guide/index' }) },
    { icon: IMG.lock, label: '用户协议', action: () => goAgreement('user') },
    { icon: IMG.shield, label: '隐私政策', action: () => goAgreement('privacy') },
    { icon: IMG.chat, label: '意见反馈', action: () => Taro.showModal({ title: '意见反馈', content: '欢迎通过微信搜索「言权」公众号或发送邮件至 support@yanquan.app 反馈建议。', showCancel: false }) },
  ]

  return (
    <View className="profile">
      {/* 用户卡片 */}
      <View className="user-card">
        <View className="user-card__avatar">
          <Text className="user-card__avatar-text">{loggedIn ? (displayName || '言').slice(0, 1) : '言'}</Text>
        </View>
        <View className="user-card__info">
          {loggedIn ? (
            <>
              <Text className="user-card__name">{displayName || '微信用户'}</Text>
              <Text className="user-card__desc">已登录 · 记录云端同步</Text>
            </>
          ) : (
            <>
              <Text className="user-card__name">游客模式</Text>
              <Text className="user-card__desc">登录后跨设备同步维权记录</Text>
            </>
          )}
        </View>
        {!loggedIn && (
          <Button className="user-card__login" onClick={goLogin}>登录</Button>
        )}
      </View>

      {/* 统计 */}
      <View className="stat-card">
        <View className="stat">
          <Text className="stat__num">{stats.total}</Text>
          <Text className="stat__label">累计投诉</Text>
        </View>
        <View className="stat">
          <Text className="stat__num">{stats.in_progress}</Text>
          <Text className="stat__label">处理中</Text>
        </View>
        <View className="stat">
          <Text className="stat__num">{stats.categories}</Text>
          <Text className="stat__label">覆盖类型</Text>
        </View>
      </View>

      {/* 菜单 */}
      <View className="menu-card">
        {menus.map((m, i) => (
          <View key={i} className="menu-item" onClick={m.action}>
            <View className="menu-item__left">
              <View className="menu-item__icon">
                <Image className="menu-item__img" src={m.icon} mode="aspectFit" />
              </View>
              <Text className="menu-item__label">{m.label}</Text>
            </View>
            <Image className="menu-item__arrow" src={IMG.chevron} mode="aspectFit" />
          </View>
        ))}
      </View>

      {/* 版本 + 退出 */}
      <Text className="version">言权 v1.0.0 · AI 消费者维权助手</Text>
      {loggedIn && (
        <Button className="logout" onClick={handleLogout}>退出登录</Button>
      )}
      <View style={{ height: 40 }} />
    </View>
  )
}

export default ProfilePage
