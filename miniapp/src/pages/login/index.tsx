import React, { useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { emailLogin, wechatLogin } from '../../services/api'
import './index.scss'

const IMG = {
  shield: require('../../assets/icons/shield.png'),
  chevron: require('../../assets/icons/chevron.png'),
}

type Tab = 'email' | 'wechat'

const LoginPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('email')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [agreed, setAgreed] = useState(false)

  const validEmail = /^[\w.+-]+@[\w-]+(\.[\w-]+)+$/.test(email.trim())
  const validPassword = password.length >= 6

  const saveLogin = (token: string, userId: number, account: string, nickname: string) => {
    Taro.setStorageSync('token', token)
    Taro.setStorageSync('user_id', String(userId))
    Taro.setStorageSync('phone', account)
    Taro.setStorageSync('nickname', nickname || '')
    Taro.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      Taro.navigateBack({ delta: 1 }).catch(() => Taro.switchTab({ url: '/pages/profile/index' }))
    }, 800)
  }

  const handleEmailLogin = async () => {
    if (!agreed) return Taro.showToast({ title: '请先勾选同意《用户协议》和《隐私政策》', icon: 'none' })
    if (!validEmail) return Taro.showToast({ title: '请输入正确的邮箱地址', icon: 'none' })
    if (!validPassword) return Taro.showToast({ title: '密码至少 6 位', icon: 'none' })
    setLoading(true)
    try {
      const data = await emailLogin(email.trim(), password)
      saveLogin(data.token, data.user_id, data.email || data.phone, data.nickname)
    } catch (e) {
      // 错误已在 api 层提示
    } finally {
      setLoading(false)
    }
  }

  const handleWechatLogin = async () => {
    if (!agreed) return Taro.showToast({ title: '请先勾选同意《用户协议》和《隐私政策》', icon: 'none' })
    setLoading(true)
    try {
      const { code: wxCode } = await Taro.login()
      if (!wxCode) {
        Taro.showToast({ title: '微信登录失败，请重试', icon: 'none' })
        return
      }
      const data = await wechatLogin(wxCode)
      saveLogin(data.token, data.user_id, data.phone || data.email, data.nickname)
    } catch (e) {
      Taro.showToast({ title: '微信登录失败，请稍后重试', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  const goAgreement = (type: string) => Taro.navigateTo({ url: `/pages/agreement/index?type=${type}` })

  return (
    <View className="login">
      <View className="login-hero">
        <View className="login-hero__logo">
          <Image className="login-hero__shield" src={IMG.shield} mode="aspectFit" />
        </View>
        <Text className="login-hero__title">登录言权</Text>
        <Text className="login-hero__subtitle">登录后跨设备同步你的维权记录</Text>
      </View>

      <View className="login-tabs">
        <View className={`login-tab ${tab === 'email' ? 'login-tab--active' : ''}`} onClick={() => setTab('email')}>
          邮箱登录
        </View>
        <View className={`login-tab ${tab === 'wechat' ? 'login-tab--active' : ''}`} onClick={() => setTab('wechat')}>
          微信登录
        </View>
      </View>

      {tab === 'email' ? (
        <View className="form">
          <View className="form__row">
            <Input
              className="form__input"
              type="text"
              placeholder="请输入邮箱"
              placeholderClass="form__placeholder"
              value={email}
              onInput={(e) => setEmail(e.detail.value)}
            />
          </View>
          <View className="form__row">
            <Input
              className="form__input"
              password
              placeholder="请输入密码（至少 6 位）"
              placeholderClass="form__placeholder"
              value={password}
              onInput={(e) => setPassword(e.detail.value)}
            />
          </View>
          <View className="privacy">
            <View className={`privacy__check ${agreed ? 'privacy__check--on' : ''}`} onClick={() => setAgreed(!agreed)}>
              {agreed && <View className="privacy__tick" />}
            </View>
            <Text className="privacy__text">我已阅读并同意</Text>
            <Text className="privacy__link" onClick={() => goAgreement('user')}>《用户协议》</Text>
            <Text className="privacy__text">和</Text>
            <Text className="privacy__link" onClick={() => goAgreement('privacy')}>《隐私政策》</Text>
          </View>
          <Button
            className={`btn-primary form__login-btn ${(!validEmail || !validPassword || loading) ? 'form__login-btn--disabled' : ''}`}
            disabled={loading}
            onClick={handleEmailLogin}
          >
            {loading ? '登录中...' : '登录 / 注册'}
          </Button>
          <Text className="form__tip">首次使用将自动创建账号，密码仅用于本人登录</Text>
        </View>
      ) : (
        <View className="wx-panel">
          <View className="privacy">
            <View className={`privacy__check ${agreed ? 'privacy__check--on' : ''}`} onClick={() => setAgreed(!agreed)}>
              {agreed && <View className="privacy__tick" />}
            </View>
            <Text className="privacy__text">我已阅读并同意</Text>
            <Text className="privacy__link" onClick={() => goAgreement('user')}>《用户协议》</Text>
            <Text className="privacy__text">和</Text>
            <Text className="privacy__link" onClick={() => goAgreement('privacy')}>《隐私政策》</Text>
          </View>
          <Button className="wx-btn" onClick={handleWechatLogin} loading={loading}>
            微信一键登录
          </Button>
          <Text className="wx-panel__tip">使用微信身份登录，记录随账号跨设备同步</Text>
        </View>
      )}

      <View className="agreement">
        <Text>登录前需勾选同意条款，未勾选无法登录</Text>
      </View>
    </View>
  )
}

export default LoginPage
