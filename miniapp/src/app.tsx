import React from 'react'
import Taro, { useLaunch } from '@tarojs/taro'
import './app.scss'
import { initCloud, wechatLogin } from './services/api'

// 静默登录：启动时尝试微信登录（失败不阻塞，后续操作再登录）
async function silentLogin() {
  if (Taro.getStorageSync('token')) return
  try {
    const { code } = await Taro.login()
    if (!code) return
    const data = await wechatLogin(code, '')
    Taro.setStorageSync('token', data.token)
    Taro.setStorageSync('user_id', String(data.user_id))
    Taro.setStorageSync('nickname', data.nickname || '')
  } catch (e) {
    console.warn('[静默登录] 未登录，继续以游客身份使用', e)
  }
}

function App({ children }) {

  useLaunch(() => {
    initCloud()
    silentLogin()
  })
  return children
}

export default App
