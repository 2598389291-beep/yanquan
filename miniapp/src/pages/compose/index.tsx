import React, { useEffect, useRef, useState } from 'react'
import { View, Text, Textarea, Button, Image, ScrollView } from '@tarojs/components'
import Taro, { useDidShow, useRouter, useShareAppMessage } from '@tarojs/taro'
import {
  createTextTask,
  generateByText,
  getMeta,
  getTaskStatus,
  getUsage,
  readFileAsBase64,
  transcribeVoiceByBase64,
  transcribeVoiceByUrl,
  uploadEvidence,
  uploadFileToCloud,
  type ComplaintDetail,
  type EvidenceItem,
  type MetaInfo,
  type TaskInfo,
  type UsageInfo,
} from '../../services/api'
import ResultView from '../../components/ResultView'
import { CATEGORY_COLORS } from '../../utils/constants'
import { formatTime } from '../../utils/format'
import './index.scss'

const IMG = {
  camera: require('../../assets/icons/camera.png'),
  doc: require('../../assets/icons/doc.png'),
  mic: require('../../assets/icons/mic.png'),
  spark: require('../../assets/icons/spark.png'),
  copy: require('../../assets/icons/copy.png'),
  share: require('../../assets/icons/share.png'),
  edit: require('../../assets/icons/edit.png'),
  check: require('../../assets/icons/check.png'),
}

const PIPELINE_STEPS = [
  '正在梳理您的维权要点…',
  '正在检索相关法律条文…',
  '正在起草投诉信…',
  '正在复核文书并规划维权路径…',
  '正在整理沟通话术…',
]

const MAX_EVIDENCE = 6

const ComposePage: React.FC = () => {
  const [stage, setStage] = useState<'input' | 'loading' | 'result'>('input')
  const [text, setText] = useState('')
  const [result, setResult] = useState<ComplaintDetail | null>(null)
  const [meta, setMeta] = useState<MetaInfo | null>(null)
  const [usage, setUsage] = useState<UsageInfo | null>(null)
  const [taskSkeleton, setTaskSkeleton] = useState('')
  const [taskProgress, setTaskProgress] = useState(0)
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [focusText, setFocusText] = useState(false)
  const router = useRouter()
  const [taskStage, setTaskStage] = useState('')

  // 维权证据包：本地路径（预览用）+ 服务端条目（提交用）
  const [evidenceLocal, setEvidenceLocal] = useState<string[]>([])
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([])
  const [evidenceUploading, setEvidenceUploading] = useState(false)

  const [orderInfo, setOrderInfo] = useState<Record<string, any>>({})
  const [loadingIndex, setLoadingIndex] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const loadingTimer = useRef<any>(null)
  const abortedRef = useRef(false)

  useShareAppMessage(() => ({
    title: '维权维权文书已起草完成，快来领取你的维权武器',
    path: '/pages/home/index',
  }))

  useDidShow(() => {
    // 从首页文字输入进入：自动聚焦输入框并唤起键盘
    if (router.params.focus === '1') {
      setFocusText(true)
      setTimeout(() => setFocusText(false), 800)
    }
    // 从首页带来的待处理语音：先转写给你确认，不自动生成
    const audio = Taro.getStorageSync('__pendingAudio')
    if (audio) {
      Taro.removeStorageSync('__pendingAudio')
      handleVoiceTranscribe(audio)
      return
    }
    // 从首页带来的待识别截图（加入证据包）
    const ocr = Taro.getStorageSync('__pendingOcr')
    if (ocr) {
      Taro.removeStorageSync('__pendingOcr')
      addEvidence([ocr])
      return
    }
    // 从维权指南带来的通用模板（预填输入框）
    const tmpl = Taro.getStorageSync('__pendingTemplate')
    if (tmpl) {
      Taro.removeStorageSync('__pendingTemplate')
      setText(tmpl)
      return
    }
    loadMetaOnce()
    loadUsage()
  })

  const loadUsage = async () => {
    try {
      setUsage(await getUsage())
    } catch (e) {
      console.warn('[Compose] 剩余次数加载失败', e)
    }
  }

  // 轮询任务式生成：先展示骨架，完成后返回完整结果
  const pollTask = (taskId: string): Promise<ComplaintDetail> =>
    new Promise((resolve, reject) => {
      let failCount = 0
      const tick = async () => {
        if (abortedRef.current) {
          reject(new Error('已取消'))
          return
        }
        try {
          const t: TaskInfo = await getTaskStatus(taskId)
          if (t.skeleton) setTaskSkeleton(t.skeleton)
          if (t.stage) setTaskStage(t.stage)
          if (typeof t.progress === 'number') setTaskProgress(t.progress)
          if (t.status === 'done' && t.result) {
            setTaskProgress(1)
            resolve(t.result)
            return
          }
          if (t.status === 'error') {
            reject(new Error(t.error || '生成失败，请重试'))
            return
          }
          failCount = 0
          setTimeout(tick, 2000)
        } catch (e) {
          // 单次轮询网络抖动不中断生成：连续失败 3 次才放弃
          failCount += 1
          if (failCount >= 3) {
            reject(e)
            return
          }
          setTimeout(tick, 2500)
        }
      }
      tick()
    })

  const loadMetaOnce = async () => {
    if (meta) return
    try {
      setMeta(await getMeta())
    } catch (e) {
      console.warn('[Compose] meta 加载失败', e)
    }
  }

  useEffect(() => {
    if (stage !== 'loading') return
    setLoadingIndex(0)
    setElapsed(0)
    const t = setInterval(() => {
      setLoadingIndex((i) => (i + 1) % PIPELINE_STEPS.length)
    }, 8000)
    const et = setInterval(() => {
      setElapsed((v) => v + 1)
    }, 1000)
    loadingTimer.current = t
    return () => { clearInterval(t); clearInterval(et) }
  }, [stage])

  // ---------- 证据包 ----------

  const chooseEvidence = () => {
    const remain = MAX_EVIDENCE - evidenceLocal.length
    if (remain <= 0) {
      Taro.showToast({ title: '最多上传 6 张证据', icon: 'none' })
      return
    }
    Taro.chooseImage({
      count: remain,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const paths = res.tempFilePaths || []
        if (paths.length) addEvidence(paths)
      },
    })
  }

  const addEvidence = async (paths: string[]) => {
    const remain = MAX_EVIDENCE - evidenceLocal.length
    const usable = paths.slice(0, remain)
    if (!usable.length) return

    setEvidenceLocal((prev) => [...prev, ...usable])
    setEvidenceUploading(true)
    try {
      const items = await uploadEvidence(usable)
      if (items.length) {
        setEvidenceItems((prev) => [...prev, ...items])
        // 合并 OCR 提取到的订单信息
        const merged: Record<string, any> = { ...orderInfo }
        items.forEach((it) => {
          Object.entries(it.order_info || {}).forEach(([k, v]) => {
            if (v && !merged[k]) merged[k] = v
          })
        })
        setOrderInfo(merged)
        Taro.showToast({ title: `已识别 ${items.length} 张证据`, icon: 'success' })
      }
    } catch (e: any) {
      console.error('[Compose] 证据上传失败', e)
    } finally {
      setEvidenceUploading(false)
    }
  }

  const removeEvidence = (index: number) => {
    setEvidenceLocal((prev) => prev.filter((_, i) => i !== index))
    setEvidenceItems((prev) => prev.filter((_, i) => i !== index))
  }

  // ---------- 语音 ----------

  // 语音转写：识别后填进输入框，交给用户确认修改，不自动生成
  const handleVoiceTranscribe = async (audioPath: string) => {
    setVoiceBusy(true)
    try {
      let text = ''
      if (process.env.TARO_ENV !== 'h5') {
        try {
          const url = await uploadFileToCloud(audioPath, 'voice')
          const r = await transcribeVoiceByUrl(url, audioPath.split('/').pop() || 'voice.mp3')
          text = r.text
        } catch (e: any) {
          console.warn('[Compose] 云转写失败，回退 base64', e)
        }
      }
      if (!text) {
        const b64 = await readFileAsBase64(audioPath)
        const r = await transcribeVoiceByBase64(b64, audioPath.split('/').pop() || 'voice.mp3')
        text = r.text
      }
      if (!text) {
        Taro.showToast({ title: '未能识别到内容，请重试', icon: 'none' })
        return
      }
      setText(text)
      setFocusText(true)
      setTimeout(() => setFocusText(false), 1000)
      Taro.showToast({ title: '已转写，可修改后起草', icon: 'none' })
    } catch (e: any) {
      const msg = e?.message || '语音识别失败'
      Taro.showModal({
        title: '语音识别失败',
        content: msg.includes('演示模式') ? '当前为演示模式，未开启语音识别服务，请使用文字输入。' : `${msg}，可改用文字输入。`,
        confirmText: '知道了',
        showCancel: false,
      })
    } finally {
      setVoiceBusy(false)
    }
  }

  // ---------- 文本 ----------

  const handleGenerate = async () => {
    const useText = text.trim()
    if (!useText) {
      Taro.showToast({ title: '请输入维权经历', icon: 'none' })
      return
    }
    if (usage && !usage.unlimited && usage.remaining <= 0) {
      Taro.showModal({
        title: '免费次数已用完',
        content: `您已用完 ${usage.total} 次免费生成额度，感谢体验。更多权益敬请期待。`,
        confirmText: '知道了',
        showCancel: false,
      })
      return
    }
    abortedRef.current = false
    setStage('loading')
    setTaskSkeleton('')
    setTaskStage('')
    setTaskProgress(0.05)
    try {
      let data: ComplaintDetail | null = null
      if (process.env.TARO_ENV !== 'h5') {
        try {
          const { task_id } = await createTextTask(useText, orderInfo, evidenceItems)
          data = await pollTask(task_id)
        } catch (e: any) {
          console.warn('[Compose] 任务式生成不可用，回退同步接口', e)
        }
      }
      if (!data) {
        data = await generateByText(useText, orderInfo, evidenceItems)
      }
      if (abortedRef.current) return
      setResult(data)
      setStage('result')
      loadUsage()
    } catch (e: any) {
      console.error('[Compose] 生成失败', e)
      setStage('input')
      const msg = e?.message || ''
      if (msg.includes('已用完') || msg.includes('免费')) {
        Taro.showModal({ title: '免费次数已用完', content: msg, confirmText: '知道了', showCancel: false })
        loadUsage()
        return
      }
      Taro.showModal({
        title: '生成失败',
        content: '起草过程中出现问题，请检查网络后重试',
        confirmText: '重试',
        cancelText: '知道了',
        success: (res) => {
          if (res.confirm) handleGenerate()
        },
      })
    }
  }

  // ---------- 取消生成 ----------

  const handleCancelGenerate = () => {
    abortedRef.current = true
    Taro.removeStorageSync('__pendingAudio')
    setStage('input')
    Taro.showToast({ title: '已取消生成', icon: 'none' })
  }

  // ---------- 结果操作 ----------

  const handleRetry = () => {
    setResult(null)
    setStage('input')
    setText('')
  }

  const handleCopyLetter = async () => {
    if (!result) return
    try {
      await Taro.setClipboardData({ data: result.complaint_letter })
      Taro.showToast({ title: '投诉信已复制', icon: 'success' })
    } catch (e) {
      Taro.showToast({ title: '复制失败', icon: 'none' })
    }
  }

  return (
    <View className="compose">
      <View className="workbench-head">
        <View className="workbench-head__badge">
          <Image className="workbench-head__badge-img" src={IMG.doc} mode="aspectFit" />
        </View>
        <View className="workbench-head__text">
          <Text className="workbench-head__title">维权工作台</Text>
          <Text className="workbench-head__sub">写或传图，确认后起草文书</Text>
        </View>
      </View>

      {stage === 'input' && (
        <View className="compose-input">
          <View className="input-card card">
            <View className="input-card__head">
              <Image className="input-card__icon" src={IMG.doc} mode="aspectFit" />
              <Text className="input-card__title">描述你的维权经历</Text>
            </View>
            <Textarea
              className="input-card__textarea"
              value={text}
              focus={focusText}
              onInput={(e) => setText(e.detail.value)}
              placeholder={'例如：我在拼多多买了一个蓝牙耳机，99 元，收到发现是假货，商家不退款，我要退一赔三…\n\n建议写清楚：\n· 时间、平台、商家名称\n· 商品/服务、金额\n· 问题经过与你的诉求'}
              placeholderClass="input-card__placeholder"
              maxlength={2000}
              autoHeight
            />
            <View className="input-card__count">{text.length} / 2000</View>

            {/* 证据包 */}
            {evidenceLocal.length === 0 && (
              <View className="evidence-tip">
                <Text className="evidence-tip__title">建议先上传 1-2 张证据</Text>
                <Text className="evidence-tip__text">订单截图 + 聊天记录各一张，有证据的投诉更容易被 12315 受理</Text>
              </View>
            )}
            <View className="evidence-section">
              <View className="evidence-section__head">
                <Text className="evidence-section__title">维权证据（最多 6 张）</Text>
                <Text className="evidence-section__count">{evidenceLocal.length}/{MAX_EVIDENCE}</Text>
              </View>
              <View className="evidence-grid">
                {evidenceLocal.map((path, i) => (
                  <View key={i} className="evidence-cell">
                    <Image className="evidence-cell__img" src={path} mode="aspectFill" />
                    <Text className="evidence-cell__remove" onClick={() => removeEvidence(i)}>×</Text>
                    {evidenceUploading && i === evidenceLocal.length - 1 && (
                      <View className="evidence-cell__loading"><Text>识别中</Text></View>
                    )}
                  </View>
                ))}
                {evidenceLocal.length < MAX_EVIDENCE && (
                  <View className="evidence-add" onClick={chooseEvidence}>
                    <Image className="evidence-add__icon" src={IMG.camera} mode="aspectFit" />
                    <Text className="evidence-add__text">添加截图</Text>
                  </View>
                )}
              </View>
              <Text className="evidence-section__hint">
                订单、聊天记录、物流、支付凭证都可以上传，会自动识别其中的关键信息
              </Text>
            </View>

            {meta?.demo_mode && (
              <View className="demo-tip">
                <Text className="demo-tip__dot" />
                <Text>演示模式：截图识别不可用，可手动在描述中补充订单信息</Text>
              </View>
            )}

            <Button
              className={`btn-primary generate-btn ${!text.trim() ? 'generate-btn--disabled' : ''}`}
              onClick={handleGenerate}
              disabled={!text.trim()}
            >
              <Image className="generate-btn__icon" src={IMG.spark} mode="aspectFit" />
              起草维权文书
            </Button>
            {usage && (
              <View className={`quota-badge ${!usage.unlimited && usage.remaining <= 0 ? 'quota-badge--empty' : ''}`}>
                {usage.unlimited
                  ? '开发者模式 · 无限次数'
                  : usage.remaining > 0
                    ? `免费生成剩余 ${usage.remaining} 次`
                    : `免费次数已用完（${usage.used}/${usage.total}）`}
              </View>
            )}
          </View>

          <View className="compose-tips card">
            <View className="section-title">
              <View className="section-title-bar" />
              <Text>写好投诉描述的小技巧</Text>
            </View>
            <View className="compose-tip-item"><View className="compose-tip-item__num">1</View><Text>说清楚时间、平台、商品、金额，信息越全，投诉信越专业</Text></View>
            <View className="compose-tip-item"><View className="compose-tip-item__num">2</View><Text>上传订单/聊天截图作为证据，12315 更重视有证据的投诉</Text></View>
            <View className="compose-tip-item"><View className="compose-tip-item__num">3</View><Text>明确你的诉求：退款、换货、退一赔三、还是赔偿损失</Text></View>
          </View>
        </View>
      )}

      {stage === 'loading' && (
        <View className="loading-wrap">
          <View className="loading-wrap__ring">
            <Image className="loading-wrap__icon" src={IMG.spark} mode="aspectFit" />
          </View>
          <View className="loading-wrap__steps">
            {PIPELINE_STEPS.map((s, i) => (
              <View key={i} className={`pipeline-step ${i <= loadingIndex ? 'pipeline-step--active' : ''}`}>
                {i < loadingIndex ? (
                  <Image className="pipeline-step__check" src={IMG.check} mode="aspectFit" />
                ) : (
                  <View className={`pipeline-step__dot ${i === loadingIndex ? 'pipeline-step__dot--current' : ''}`} />
                )}
                <Text className={`pipeline-step__text ${i === loadingIndex ? 'pipeline-step__text--current' : ''}`}>{s}</Text>
              </View>
            ))}
          </View>
          <View className="loading-progress">
            <View className="loading-progress__bar">
              <View
                className="loading-progress__fill"
                style={{ width: `${Math.min(100, taskProgress > 0 ? Math.round(taskProgress * 100) : Math.round(((loadingIndex + 1) / PIPELINE_STEPS.length) * 100))}%` }}
              />
            </View>
            <Text className="loading-progress__pct">{Math.min(100, taskProgress > 0 ? Math.round(taskProgress * 100) : Math.round(((loadingIndex + 1) / PIPELINE_STEPS.length) * 100))}%</Text>
          </View>
          {taskStage && <Text className="loading-wrap__stage">{taskStage}</Text>}
          {taskSkeleton && (
            <View className="loading-draft">
              <View className="loading-draft__head">
                <Text className="loading-draft__label">投诉信起草中 · 内容持续完善</Text>
              </View>
              <View className="loading-draft__body" selectable>{taskSkeleton}</View>
            </View>
          )}
          <Text className="loading-wrap__hint">已用时 {elapsed} 秒，先看骨架、稍等完整版</Text>
          <Button className="loading-cancel" onClick={handleCancelGenerate}>取消生成</Button>
        </View>
      )}

      {stage === 'result' && result && (
        <View className="compose-result">
          {/* 结果头部 */}
          <View className="result-hero">
            <View className="result-hero__badge">
              <Image className="result-hero__badge-icon" src={IMG.check} mode="aspectFit" />
            </View>
            <Text className="result-hero__title">投诉信已生成</Text>
            <View className="result-hero__meta">
              <View className="result-hero__cat" style={{ background: `${CATEGORY_COLORS[result.category] || '#8B98AB'}1A`, color: CATEGORY_COLORS[result.category] || '#8B98AB' }}>
                {result.category || '未分类'}
              </View>
              <Text className="result-hero__time">{formatTime(result.created_at)}</Text>
            </View>
          </View>

          <ScrollView scrollY className="result-scroll">
            <ResultView data={result} />
            <View className="result-history" onClick={() => Taro.switchTab({ url: '/pages/history/index' })}>
              <Text className="result-history__text">查看我的维权记录 →</Text>
            </View>
          </ScrollView>

          <View className="bottom-bar safe-area-bottom">
            <View className="bar-inner">
              <Button className="bar-btn" onClick={handleRetry}>
                <Image className="bar-btn__icon" src={IMG.edit} mode="aspectFit" />
                重新生成
              </Button>
              <Button className="bar-btn bar-btn--share" open-type="share">
                <Image className="bar-btn__icon" src={IMG.share} mode="aspectFit" />
                分享
              </Button>
              <Button className="bar-btn bar-btn--primary" onClick={handleCopyLetter}>
                <Image className="bar-btn__icon" src={IMG.copy} mode="aspectFit" />
                复制投诉信
              </Button>
            </View>
          </View>
          <View className="bottom-pad" />
        </View>
      )}
    </View>
  )
}

export default ComposePage
