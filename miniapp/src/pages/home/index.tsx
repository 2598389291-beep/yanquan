import React, { useState } from 'react'
import { View, Text, Image, Button } from '@tarojs/components'
import Taro, { useDidShow, useShareAppMessage } from '@tarojs/taro'
import { getComplaintList, getMeta, type ComplaintListItem, type MetaInfo } from '../../services/api'
import { CATEGORY_COLORS, STATUS_CONFIG } from '../../utils/constants'
import { useVoiceRecorder } from '../../hooks/useVoiceRecorder'
import Skeleton from '../../components/Skeleton'
import { formatTime as fmtTime, shortText } from '../../utils/format'
import './index.scss'

interface RecentItem {
  id: number
  summary: string
  category: string
  status: string
  status_label: string
  created_at: string
}

const IMG = {
  mic: require('../../assets/icons/mic.png'),
  keyboard: require('../../assets/icons/keyboard.png'),
  camera: require('../../assets/icons/camera.png'),
  scale: require('../../assets/icons/scale.png'),
  shield: require('../../assets/icons/shield.png'),
  letter: require('../../assets/icons/letter.png'),
  chevron: require('../../assets/icons/chevron.png'),
}

const HomePage: React.FC = () => {
  const [recent, setRecent] = useState<RecentItem[]>([])
  const [meta, setMeta] = useState<MetaInfo | null>(null)
  const [loading, setLoading] = useState(false)

  // 全局录音（首页按住说话 → 跳转生成页并自动识别）
  const {
    isRecording,
    seconds: recordSeconds,
    start: startVoice,
    stop: stopVoice,
    reset: resetVoice,
  } = useVoiceRecorder((filePath) => {
    // 仅当当前正在首页时才跳转（生成页也在监听，避免互相干扰）
    const pages = getCurrentPages()
    const route = pages[pages.length - 1]?.route
    if (route !== 'pages/home/index') return
    Taro.setStorageSync('__pendingAudio', filePath)
    setTimeout(() => Taro.navigateTo({ url: '/pages/compose/index?focus=1' }), 400)
  })

  useShareAppMessage(() => ({
    title: '说出你的维权经历，言权帮你写好投诉信',
    path: '/pages/home/index',
  }))

  useDidShow(() => {
    // 重新进入页面时复位录音状态
    stopVoice()
    resetVoice()
    // 首次打开：先进入引导页（仅一次，可跳过）
    if (!Taro.getStorageSync('__onboarded')) {
      Taro.redirectTo({ url: '/pages/onboard/index' })
      return
    }
    loadMeta()
    loadRecent()
  })

  const loadMeta = async () => {
    try {
      const m = await getMeta()
      setMeta(m)
    } catch (e) {
      console.warn('[Home] meta 加载失败', e)
    }
  }

  const loadRecent = async () => {
    setLoading(true)
    try {
      const resp = await getComplaintList(1, 5)
      setRecent(
        resp.items.map((item: ComplaintListItem) => ({
          id: item.id,
          summary: shortText(item.raw_text, 40),
          category: item.category || '未分类',
          status: item.status,
          status_label: item.status_label || STATUS_CONFIG[item.status]?.label || '已生成',
          created_at: fmtTime(item.created_at),
        }))
      )
    } catch (e) {
      console.error('[Home] 最近记录加载失败:', e)
      setRecent([])
    } finally {
      setLoading(false)
    }
  }

  const fmt = (sec: number) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0')
    const s = (sec % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  const startRecord = () => {
    if (meta?.demo_mode) {
      Taro.showModal({
        title: '演示模式',
        content: '当前未配置语音识别服务，请使用文字输入。配置 DASHSCOPE_API_KEY 后即可体验语音维权。',
        confirmText: '去输入',
        cancelText: '知道了',
        success: (res) => {
          if (res.confirm) goComposeText()
        },
      })
      return
    }
    startVoice()
  }

  const stopRecord = () => stopVoice()

  const goComposeText = () => Taro.navigateTo({ url: '/pages/compose/index?focus=1' })

  const goComposeOcr = () => {
    Taro.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFilePaths?.[0]
        if (path) {
          Taro.setStorageSync('__pendingOcr', path)
          Taro.navigateTo({ url: '/pages/compose/index' })
        }
      },
    })
  }

  const goDetail = (id: number) => Taro.navigateTo({ url: `/pages/detail/index?id=${id}` })

  const goGuide = () => Taro.navigateTo({ url: '/pages/guide/index' })

  const HOT_TEMPLATES = [
    { key: 'auto_renewal', label: '自动续费' },
    { key: 'express_loss', label: '快递丢件' },
    { key: 'return_refused', label: '退货被拒' },
    { key: 'prepaid_card', label: '预付卡退费' },
    { key: 'food_delivery', label: '外卖纠纷' },
    { key: 'education_refund', label: '教育退费' },
  ]

  const goGuideTemplate = (key: string) => {
    Taro.setStorageSync('__guideTarget', JSON.stringify({ tab: 'templates', key }))
    Taro.navigateTo({ url: '/pages/guide/index' })
  }

  const stats = meta?.stats || { laws: 21, scenarios: 8, templates: 10, cases: 8 }

  return (
    <View className="home">
      {/* Hero */}
      <View className="hero">
        <View className="hero__top">
          <View className="hero__brand">
            <View className="hero__logo">
              <Image className="hero__logo-img" src={IMG.scale} mode="aspectFit" />
            </View>
            <View>
              <Text className="hero__name">言权</Text>
              <Text className="hero__slogan">口述即出信 · 维权有依据</Text>
            </View>
          </View>
        </View>

        <View className="hero__tag">
          <View className="hero__tag-line" />
          <Text>消费者权益 · 让维权变简单</Text>
          <View className="hero__tag-line" />
        </View>
        <Text className="hero__title">维权，从一句话开始</Text>
        <Text className="hero__subtitle">让维权，不再是普通人不敢做的事</Text>

        {/* 录音按钮 */}
        <View className="record-zone">
          <View
            className={`record-btn ${isRecording ? 'record-btn--active' : ''}`}
            onTouchStart={startRecord}
            onTouchEnd={stopRecord}
            onTouchCancel={stopRecord}
          >
            <Image className="record-btn__icon" src={IMG.mic} mode="aspectFit" />
          </View>
          {isRecording && (
            <View className="record-timer">
              <View className="record-timer__dot" />
              <Text>{fmt(recordSeconds)}</Text>
            </View>
          )}
          <Text className="record-hint">{isRecording ? '正在录音，松手结束' : '按住说话，直接开始维权'}</Text>
          <View className="hero__chips">
            {HOT_TEMPLATES.map((c) => (
              <View key={c.key} className="hero__chip" onClick={() => goGuideTemplate(c.key)}>
                <Text className="hero__chip-text">{c.label}</Text>
              </View>
            ))}
          </View>
        </View>

        {meta?.demo_mode && (
          <View className="demo-banner" onClick={goComposeText}>
            <View className="demo-banner__dot" />
            <Text>演示模式运行中：语音能力未开启，可先体验文字生成</Text>
          </View>
        )}
      </View>

      {/* 信任条（数字来自后端 meta，随知识库自动更新） */}
      <View className="trust-strip">
        <View className="trust-strip__item"><Text className="trust-strip__num">{stats.laws}</Text><Text className="trust-strip__label">高频法条</Text></View>
        <View className="trust-strip__divider" />
        <View className="trust-strip__item"><Text className="trust-strip__num">{stats.templates}</Text><Text className="trust-strip__label">即用模板</Text></View>
        <View className="trust-strip__divider" />
        <View className="trust-strip__item"><Text className="trust-strip__num">{stats.scenarios}</Text><Text className="trust-strip__label">场景指南</Text></View>
        <View className="trust-strip__divider" />
        <View className="trust-strip__item"><Text className="trust-strip__num">{stats.cases}</Text><Text className="trust-strip__label">案例参考</Text></View>
      </View>

      {/* 紧凑流程条 */}
      <View className="flow-strip">
        <View className="flow-strip__item">
          <View className="flow-strip__icon"><Image className="flow-strip__img" src={IMG.mic} mode="aspectFit" /></View>
          <Text className="flow-strip__text">口述经历</Text>
        </View>
        <View className="flow-strip__arrow" />
        <View className="flow-strip__item">
          <View className="flow-strip__icon"><Image className="flow-strip__img" src={IMG.letter} mode="aspectFit" /></View>
          <Text className="flow-strip__text">言权出信</Text>
        </View>
        <View className="flow-strip__arrow" />
        <View className="flow-strip__item">
          <View className="flow-strip__icon"><Image className="flow-strip__img" src={IMG.shield} mode="aspectFit" /></View>
          <Text className="flow-strip__text">提交维权</Text>
        </View>
      </View>

      {/* 其他输入方式（跳转生成页） */}
      <View className="entries">
        <View className="entry-card" onClick={goComposeText}>
          <View className="entry-card__icon entry-card__icon--blue">
            <Image className="entry-card__img" src={IMG.keyboard} mode="aspectFit" />
          </View>
          <View className="entry-card__body">
            <Text className="entry-card__title">文字输入</Text>
            <Text className="entry-card__desc">打字描述经历，同样生成投诉信</Text>
          </View>
          <Image className="entry-card__arrow" src={IMG.chevron} mode="aspectFit" />
        </View>
        <View className="entry-card" onClick={goComposeOcr}>
          <View className="entry-card__icon entry-card__icon--gold">
            <Image className="entry-card__img" src={IMG.camera} mode="aspectFit" />
          </View>
          <View className="entry-card__body">
            <Text className="entry-card__title">订单截图</Text>
            <Text className="entry-card__desc">上传订单/聊天截图，自动提取信息</Text>
          </View>
          <Image className="entry-card__arrow" src={IMG.chevron} mode="aspectFit" />
        </View>
      </View>

      {/* 维权指南入口 */}
      <View className="guide-entry" onClick={goGuide}>
        <View className="guide-entry__icon">
          <Image className="guide-entry__img" src={IMG.scale} mode="aspectFit" />
        </View>
        <View className="guide-entry__body">
          <Text className="guide-entry__title">维权指南</Text>
          <Text className="guide-entry__desc">场景指南 · 即用模板 · 证据清单 · 案例参考</Text>
        </View>
        <Image className="guide-entry__arrow" src={IMG.chevron} mode="aspectFit" />
      </View>

      {/* 最近记录 */}
      <View className="recent card">
        <View className="recent__head">
          <View className="section-title">
            <View className="section-title-bar" />
            <Text>最近记录</Text>
          </View>
          <Text className="recent__more" onClick={() => Taro.switchTab({ url: '/pages/history/index' })}>查看全部</Text>
        </View>
        {loading ? (
          <View className="recent__skeleton"><Skeleton rows={2} /></View>
        ) : recent.length === 0 ? (
          <View className="recent__empty">
            <Text className="recent__empty-text">还没有维权记录，说出第一段经历吧</Text>
            <Button className="recent__cta" onClick={goComposeText}>起草第一封维权文书</Button>
          </View>
        ) : (
          recent.map((item) => {
            const catColor = CATEGORY_COLORS[item.category] || '#8B98AB'
            const status = STATUS_CONFIG[item.status] || { label: item.status_label, color: '#8B98AB', bg: '#F0F2F6' }
            return (
              <View key={item.id} className="recent-item" onClick={() => goDetail(item.id)}>
                <View className="recent-item__dot" style={{ background: catColor }} />
                <View className="recent-item__main">
                  <Text className="recent-item__summary">{item.summary}</Text>
                  <View className="recent-item__meta">
                    <Text className="recent-item__cat">{item.category}</Text>
                    <Text className="recent-item__time">{item.created_at}</Text>
                  </View>
                </View>
                <View className="recent-item__right">
                  <View className="recent-item__status" style={{ color: status.color, background: status.bg }}>{status.label}</View>
                  <Image className="recent-item__arrow" src={IMG.chevron} mode="aspectFit" />
                </View>
              </View>
            )
          })
        )}
      </View>

      <View className="home__footer">
        <Image className="home__footer-icon" src={IMG.shield} mode="aspectFit" />
        <Text>生成内容仅供参考，不构成法律意见</Text>
      </View>
      <View style={{ height: 40 }} />
    </View>
  )
}

export default HomePage
