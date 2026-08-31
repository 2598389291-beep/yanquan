import React, { useState } from 'react'
import { View, Text, Textarea, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { submitFeedback, submitOutcome, type ComplaintDetail } from '../../services/api'
import { CATEGORY_COLORS, findChannelEntry, buildChannelEntryText } from '../../utils/constants'
import SectionCard from '../SectionCard'
import './index.scss'

const ICONS = {
  path: require('../../assets/icons/arrow.png'),
  law: require('../../assets/icons/scale.png'),
  letter: require('../../assets/icons/letter.png'),
  chat: require('../../assets/icons/chat.png'),
  shield: require('../../assets/icons/shield.png'),
  check: require('../../assets/icons/check.png'),
  edit: require('../../assets/icons/edit.png'),
  copy: require('../../assets/icons/copy.png'),
  chevron: require('../../assets/icons/chevron.png'),
}

interface Props {
  data: ComplaintDetail
}

const copyText = async (text: string, tip: string) => {
  try {
    await Taro.setClipboardData({ data: text })
    Taro.showToast({ title: tip, icon: 'success' })
  } catch (e) {
    Taro.showToast({ title: '复制失败', icon: 'none' })
  }
}

const CHANNEL_TYPE_CLASS: Record<string, string> = {
  '协商': 'channel-type--xieshang',
  '投诉': 'channel-type--tousu',
  '举报': 'channel-type--jubao',
  '诉讼': 'channel-type--susong',
}

const ResultView: React.FC<Props> = ({ data }) => {
  const [editing, setEditing] = useState(false)
  const [letter, setLetter] = useState(data.complaint_letter)
  const [expandedLaw, setExpandedLaw] = useState(-1)
  const [feedbackDone, setFeedbackDone] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackComment, setFeedbackComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [doneSteps, setDoneSteps] = useState<number[]>([])
  const [outcomeSent, setOutcomeSent] = useState<boolean>(!!Taro.getStorageSync(`__outcome_${data.id}`))
  const catColor = CATEGORY_COLORS[data.category] || '#8B98AB'

  const evidence = data.evidence || []

  // ---------- 反馈 ----------
  const handleFeedback = async (rating: 'helpful' | 'unhelpful') => {
    if (feedbackDone || submitting) return
    if (rating === 'helpful') {
      setSubmitting(true)
      try {
        await submitFeedback(data.id, 'helpful')
        setFeedbackDone(true)
        Taro.showToast({ title: '感谢反馈！', icon: 'success' })
      } catch (e) {
        console.error('[Feedback] 提交失败', e)
      } finally {
        setSubmitting(false)
      }
    } else {
      setFeedbackOpen(true)
    }
  }

  const handleFeedbackSubmit = async () => {
    setSubmitting(true)
    try {
      await submitFeedback(data.id, 'unhelpful', feedbackComment)
      setFeedbackDone(true)
      setFeedbackOpen(false)
      Taro.showToast({ title: '已收到反馈，我们会持续优化', icon: 'success' })
    } catch (e) {
      console.error('[Feedback] 提交失败', e)
    } finally {
      setSubmitting(false)
    }
  }

  // ---------- 材料包 ----------
  const buildMaterialPack = (): string => {
    const lines: string[] = []
    lines.push('【投诉信】')
    lines.push(letter)
    lines.push('')
    lines.push('【证据清单：先去准备这些】')
    const ev = data.evidence_checklist
    if (ev?.items?.length) {
      ev.items.forEach((it, i) => {
        lines.push(`${i + 1}. ${it.item}（${it.how}）`)
      })
    } else {
      lines.push('（暂无，建议补充订单/聊天截图）')
    }
    if (evidence.length) {
      lines.push('')
      lines.push('你已上传的证据：')
      evidence.forEach((it, i) => {
        lines.push(`${i + 1}. ${it.file_name || '证据图片'}`)
      })
    }
    return lines.join('\n')
  }

  // 官方渠道列表：每个渠道一个独立按钮，复制搜索词/链接
  const CHANNEL_BUTTONS = [
    { name: '全国12315平台', kind: '小程序', search: '全国12315平台', url: 'https://www.12315.cn/', phone: '12315' },
    { name: '黑猫投诉', kind: '小程序', search: '黑猫投诉', url: 'https://tousu.sina.com.cn/', phone: '' },
    { name: '国家邮政局申诉网站', kind: '官网', search: '国家邮政局申诉网站', url: 'https://sswz.spb.gov.cn/', phone: '12305' },
    { name: '工信部电信用户申诉受理中心', kind: '官网', search: '工信部申诉受理', url: 'https://yhssglxt.miit.gov.cn/', phone: '12300' },
    { name: '12321举报中心', kind: '小程序', search: '12321举报中心', url: 'https://www.12321.cn/', phone: '12321' },
    { name: '12345 政务服务便民热线', kind: '热线', search: '', url: '', phone: '12345' },
    { name: '12348 法律援助热线', kind: '热线', search: '', url: '', phone: '12348' },
  ]

  const callPhone = (c: { phone: string }) => {
    if (!c.phone) return
    Taro.makePhoneCall({ phoneNumber: c.phone }).catch(() => {})
  }

  const copyChannel = (c: { name: string; kind: string; search: string; url: string; phone: string }) => {
    if (c.kind === '热线') return
    if (c.kind === '小程序') {
      copyText(c.search, '搜索词已复制，去微信搜索框粘贴')
    } else {
      copyText(c.url, '官网链接已复制，去浏览器打开')
    }
  }

  // 上游分流：一键复制投诉信 + 平台操作指引
  const go12315 = () => {
    copyText(letter, '投诉信已复制')
    setTimeout(() => {
      Taro.showModal({
        title: '去 12315 投诉',
        content: '1. 微信搜索「全国12315平台」小程序\n2. 选择「投诉」，粘贴投诉信\n3. 12315 会自动智能识别内容，补充企业全称\n4. 上传证据截图，提交等待受理',
        confirmText: '知道了',
        showCancel: false,
      })
    }, 600)
  }

  const goHemaio = () => {
    copyText(letter, '投诉信已复制')
    setTimeout(() => {
      Taro.showModal({
        title: '去黑猫投诉曝光',
        content: '1. 微信搜索「黑猫投诉」小程序\n2. 新建投诉，粘贴投诉信\n3. 附上证据截图\n4. 提交后投诉公开可见，商家更愿意快速处理',
        confirmText: '知道了',
        showCancel: false,
      })
    }, 600)
  }

  const sections: React.ReactNode[] = []

  // ---------- 维权行动向导（照着一步步做） ----------
  if (data.action_checklist?.length) {
    sections.push(
      <SectionCard key="action" title="维权行动向导" icon={ICONS.check}>
        <Text className="action-guide__sub">不用想流程，照着下面一步步做就行</Text>
        {data.action_checklist.map((s) => {
          const done = doneSteps.includes(s.step)
          return (
            <View key={s.step} className={`action-step ${done ? 'action-step--done' : ''}`} onClick={() => {
              setDoneSteps((prev) => done ? prev.filter((x) => x !== s.step) : [...prev, s.step])
            }}>
              <View className={`action-step__check ${done ? 'action-step__check--done' : ''}`}>
                {done && <View className="action-step__tick" />}
              </View>
              <View className="action-step__body">
                <View className="action-step__head">
                  <Text className="action-step__action">第{s.step}步 · {s.action}</Text>
                  <Text className="action-step__duration">{s.duration}</Text>
                </View>
                <Text className="action-step__detail">{s.detail}</Text>
              </View>
            </View>
          )
        })}
        <Text className="action-guide__foot">完成一步点一下，全部做完就可以去提交啦</Text>
      </SectionCard>
    )
  }

  // ---------- 证据收集清单 ----------
  if (data.evidence_checklist?.items?.length) {
    const ev = data.evidence_checklist
    sections.push(
      <SectionCard key="evidence-list" title={`证据收集清单 · ${ev.title}`} icon={ICONS.shield} collapsible defaultOpen>
        <Text className="evidence-list__hint">举证是关键，先把这些证据留全，投诉才有分量</Text>
        {ev.items.map((it, i) => (
          <View key={i} className="evidence-list__item">
            <View className="evidence-list__num">{i + 1}</View>
            <View className="evidence-list__main">
              <Text className="evidence-list__name">{it.item}</Text>
              <Text className="evidence-list__purpose">为什么留：{it.purpose}</Text>
              <Text className="evidence-list__how">怎么留：{it.how}</Text>
            </View>
          </View>
        ))}
      </SectionCard>
    )
  }

  // ---------- 维权路径 ----------
  if (data.action_path?.length) {
    sections.push(
      <SectionCard key="path" title="维权路径" icon={ICONS.path} collapsible defaultOpen={false}>
        <View className="path-list">
          {data.action_path.map((s) => (
            <View key={s.step} className="path-item">
              <View className="path-item__rail">
                <View className="path-item__num" style={{ background: catColor }}>{s.step}</View>
                {s.step < data.action_path.length && <View className="path-item__line" style={{ borderColor: catColor }} />}
              </View>
              <View className="path-item__content">
                <Text className="path-item__action">{s.action}</Text>
                <Text className="path-item__detail">{s.detail}</Text>
              </View>
            </View>
          ))}
        </View>
      </SectionCard>
    )
  }

  // ---------- 渠道建议 ----------
  if (data.channel_advice?.channels?.length) {
    sections.push(
      <SectionCard key="channel" title="维权渠道建议" icon={ICONS.path} collapsible defaultOpen={false}>
        <View className="channel-summary">{data.channel_advice.summary}</View>
        {data.channel_advice.channels.map((c, i) => (
          <View key={i} className="channel-item">
            <View className="channel-item__head">
              <Text className={`channel-type ${CHANNEL_TYPE_CLASS[c.type] || ''}`}>{c.type}</Text>
              <Text className="channel-item__name">{c.channel}</Text>
            </View>
            <Text className="channel-item__reason">{c.reason}</Text>
            <Text className="channel-item__law">法律依据：{c.legal_basis}</Text>
            <Text className="channel-item__action">{c.action}</Text>
          </View>
        ))}
        {data.channel_advice.channels.map((c, i) => {
          const entry = findChannelEntry(c.channel)
          return (
            <View key={i} className="channel-item">
              <View className="channel-item__head">
                <Text className={`channel-type ${CHANNEL_TYPE_CLASS[c.type] || ''}`}>{c.type}</Text>
                <Text className="channel-item__name">{c.channel}</Text>
              </View>
              <Text className="channel-item__reason">{c.reason}</Text>
              <Text className="channel-item__law">法律依据：{c.legal_basis}</Text>
              <Text className="channel-item__action">{c.action}</Text>
              {entry && (entry.search || entry.url) && (
                <Button className="channel-item__entry" onClick={() => copyText(buildChannelEntryText(c.channel, entry), '官方入口已复制')}>
                  复制官方入口
                </Button>
              )}
            </View>
          )
        })}
      </SectionCard>
    )
  }

  // ---------- 法律依据（可溯源） ----------
  const legalList = data.legal_details?.length
    ? data.legal_details.map((d) => ({ title: `${d.law_name} ${d.article}`, content: d.content, url: d.source_url }))
    : (data.legal_basis || []).map((b) => ({ title: b, content: '', url: '' }))

  if (legalList.length) {
    sections.push(
      <SectionCard key="law" title="法律依据" icon={ICONS.law} collapsible defaultOpen={false}>
        <View className="law-list">
          {legalList.map((law, i) => (
            <View key={i} className="law-card">
              <View className="law-card__head" onClick={() => setExpandedLaw(expandedLaw === i ? -1 : i)}>
                <View className="law-card__seal">法</View>
                <Text className="law-card__title">{law.title}</Text>
                <Image className={`law-card__arrow ${expandedLaw === i ? 'law-card__arrow--open' : ''}`} src={ICONS.chevron} mode="aspectFit" />
              </View>
              {expandedLaw === i && (
                <View className="law-card__body">
                  {law.content ? (
                    <>
                      <Text className="law-card__content" selectable>{law.content}</Text>
                      <Button
                        className="law-card__link"
                        onClick={() => copyText(law.url, '官方检索链接已复制')}
                      >
                        复制官方检索链接
                      </Button>
                      <Text className="law-card__note">来源：国家法律法规数据库（flk.npc.gov.cn）</Text>
                    </>
                  ) : (
                    <Text className="law-card__content">点击上方链接可查看官方条文原文。</Text>
                  )}
                </View>
              )}
            </View>
          ))}
        </View>
        <View className="law-note">法律条文引用自公开法律法规，建议以官方原文为准；本内容不构成法律意见。</View>
      </SectionCard>
    )
  }

  // ---------- 投诉信 ----------
  sections.push(
    <SectionCard
      key="letter"
      title="投诉信正文（复制后去平台粘贴）"
      icon={ICONS.letter}
      collapsible
      right={
        editing ? (
          <Button className="letter-edit-btn" onClick={() => { setEditing(false); Taro.showToast({ title: '已保存', icon: 'success' }) }}>
            完成
          </Button>
        ) : (
          <Button className="letter-edit-btn" onClick={() => setEditing(true)}>
            <Image className="letter-edit-btn__icon" src={ICONS.edit} mode="aspectFit" />
            编辑
          </Button>
        )
      }
    >
      {editing ? (
        <Textarea
          className="letter-textarea"
          value={letter}
          onInput={(e) => setLetter(e.detail.value)}
          autoHeight
          maxlength={8000}
        />
      ) : (
        <View className="letter-doc" selectable>
          <Text className="letter-doc__text">{letter}</Text>
        </View>
      )}
      <View className="letter-actions">
        <Button className="letter-copy" onClick={() => copyText(letter, '投诉信已复制')}>
          <Image className="letter-copy__icon" src={ICONS.copy} mode="aspectFit" />
          复制投诉信
        </Button>
      </View>
    </SectionCard>
  )

  // ---------- 沟通话术 ----------
  if (data.negotiation_script?.steps?.length) {
    sections.push(
      <SectionCard key="script" title="沟通话术模板" icon={ICONS.chat} collapsible defaultOpen={false}>
        {data.negotiation_script.steps.map((s) => (
          <View key={s.step} className="script-item">
            <View className="script-item__head">
              <View className="script-item__num">{s.step}</View>
              <Text className="script-item__title">{s.title}</Text>
            </View>
            <Text className="script-item__target">发送对象：{s.target}</Text>
            <Text className="script-item__scenario">{s.scenario}</Text>
            <View className="script-item__body" selectable>{s.script}</View>
            <Text className="script-item__tips">提示：{s.tips}</Text>
            <Button className="script-item__copy" onClick={() => copyText(s.script, '话术已复制')}>
              复制此段话术
            </Button>
          </View>
        ))}
      </SectionCard>
    )
  }

  // ---------- 商家资质 ----------
  if (data.merchant_qualification_advice?.items?.length) {
    sections.push(
      <SectionCard key="qual" title="商家资质查验建议" icon={ICONS.shield} collapsible defaultOpen={false}>
        <View className="qual-summary">{data.merchant_qualification_advice.summary}</View>
        {data.merchant_qualification_advice.items.map((q, i) => (
          <View key={i} className="qual-item">
            <Text className="qual-item__title">{q.qualification}</Text>
            <Text className="qual-item__row">如何查验：{q.how_to_check}</Text>
            <Text className="qual-item__row">重要性：{q.importance}</Text>
            <Text className="qual-item__row qual-item__row--warn">风险提示：{q.red_flag}</Text>
          </View>
        ))}
      </SectionCard>
    )
  }

  return (
    <View className="result-view">
      {/* 下一步引导：上游分流桥 */}
      <View className="next-step">
        <View className="next-step__head">
          <Text className="next-step__title">你的维权，从这里出发</Text>
          <Text className="next-step__sub">材料已帮你备齐，选一条路，剩下的交给平台</Text>
        </View>

        {data.path_recommendation && (
          <View className="rec-card">
            <View className="rec-card__label">系统建议你走这条路</View>
            <View className="rec-card__main">
              <Text className="rec-card__name">{data.path_recommendation.recommended}</Text>
            </View>
            <Text className="rec-card__reason">为什么：{data.path_recommendation.reason}</Text>
            <Text className="rec-card__backup">备选：{data.path_recommendation.backup}</Text>
          </View>
        )}

        <View className="route-card route-card--12315" onClick={go12315}>
          <View className="route-card__head">
            <Text className="route-card__name">去 12315 投诉</Text>
            <Text className="route-card__tag">官方受理 · 调解</Text>
          </View>
          <Text className="route-card__desc">权威通道：市场监管部门受理并组织调解，适合大多数纠纷</Text>
          <Text className="route-card__action">点击复制投诉信 + 操作指引 →</Text>
        </View>

        <View className="route-card route-card--hemao" onClick={goHemaio}>
          <View className="route-card__head">
            <Text className="route-card__name">去黑猫投诉曝光</Text>
            <Text className="route-card__tag">公开曝光 · 施压</Text>
          </View>
          <Text className="route-card__desc">舆论通道：投诉公开可见，商家更怕曝光，适合被拖延、推诿的纠纷</Text>
          <Text className="route-card__action">点击复制投诉信 + 操作指引 →</Text>
        </View>

        {data.path_recommendation?.upgrade_plan && (
          <View className="planb-card">
            <View className="planb-card__head">
              <Text className="planb-card__title">B 计划：商家不回应怎么办</Text>
              <Text className="planb-card__tag">别卡住，还有路可走</Text>
            </View>
            {data.path_recommendation.upgrade_plan.map((p) => (
              <View key={p.step} className="planb-card__item">
                <View className="planb-card__num">{p.step}</View>
                <View className="planb-card__body">
                  <Text className="planb-card__action">{p.action}</Text>
                  <Text className="planb-card__detail">{p.detail}</Text>
                </View>
              </View>
            ))}
          </View>
        )}

        <Button className="next-step__btn" onClick={() => copyText(buildMaterialPack(), '全套材料已复制')}>
          <Image className="next-step__btn-icon" src={ICONS.copy} mode="aspectFit" />
          <Text className="next-step__btn-text">复制全套材料（投诉信 + 证据清单）</Text>
        </Button>

        <View className="next-step__tip">主流投诉平台（12315 / 黑猫 / 消费保）都支持「粘贴文字 + 上传截图」；12315 还会自动智能识别整理内容。粘贴后你只需补充企业全称、上传证据附件。</View>

        {data.matched_channels?.length > 0 && (
          <View className="matched-channels">
            <View className="more-channels__label">按你的情况推荐渠道</View>
            {data.matched_channels.map((mc, i) => {
              const entry = findChannelEntry(mc.name)
              return (
                <View key={i} className="matched-channel" onClick={() => copyChannel(mc)}>
                  <View className="matched-channel__info">
                    <Text className="matched-channel__name">{mc.name}</Text>
                    <Text className="matched-channel__reason">为什么选它：{mc.reason}</Text>
                    <Text className="matched-channel__entry">
                      {mc.kind === '小程序' ? `微信搜索「${mc.search}」` : `浏览器打开 ${mc.url}`}{mc.phone ? ` · 热线 ${mc.phone}` : ''}
                    </Text>
                  </View>
                  <View className="channel-copy-row__btn channel-copy-row__btn--mp">复制入口</View>
                </View>
              )
            })}
          </View>
        )}

        <View className="more-channels__label">更多渠道</View>
        <View className="next-step__channels">
            {CHANNEL_BUTTONS.map((c, i) => (
              <View key={i} className="channel-copy-row" onClick={() => copyChannel(c)}>
                <View className="channel-copy-row__info">
                  <Text className="channel-copy-row__name">{c.name}</Text>
                  <Text className="channel-copy-row__desc">
                    {c.kind === '热线'
                      ? `投诉热线：${c.phone}（工作时段拨打）`
                      : c.kind === '小程序'
                        ? `微信搜索「${c.search}」${c.phone ? ` · 热线 ${c.phone}` : ''}`
                        : `浏览器打开 ${c.url}${c.phone ? ` · 热线 ${c.phone}` : ''}`}
                  </Text>
                </View>
                {c.kind === '热线' ? (
                  <View className="channel-copy-row__btn channel-copy-row__btn--call" onClick={() => callPhone(c)}>
                    拨打 {c.phone}
                  </View>
                ) : (
                  <View className={`channel-copy-row__btn channel-copy-row__btn--${c.kind === '小程序' ? 'mp' : 'web'}`}>
                    {c.kind === '小程序' ? '复制搜索词' : '复制链接'}
                  </View>
                )}
              </View>
            ))}
          </View>
      </View>

      {sections}

      {/* 轻回访：真实处理结果（一次，可忽略） */}
      {!outcomeSent && (
        <View className="outcome-card">
          <Text className="outcome-card__title">方便的话，告诉我们最终结果（仅一次，用于积累真实数据）</Text>
          <View className="outcome-card__btns">
            {[
              ['resolved', '已解决'],
              ['partial', '部分解决'],
              ['unresolved', '没解决'],
              ['no_response', '商家没回应'],
            ].map(([val, label]) => (
              <View key={val} className="outcome-card__btn" onClick={async () => {
                try {
                  await submitOutcome(data.id, val)
                  Taro.setStorageSync(`__outcome_${data.id}`, '1')
                  setOutcomeSent(true)
                  Taro.showToast({ title: '感谢反馈', icon: 'success' })
                } catch (e) {
                  Taro.showToast({ title: '提交失败，可稍后重试', icon: 'none' })
                }
              }}>
                <Text className="outcome-card__btn-text">{label}</Text>
              </View>
            ))}
          </View>
          <Text className="outcome-card__skip" onClick={() => { Taro.setStorageSync(`__outcome_${data.id}`, '1'); setOutcomeSent(true) }}>忽略</Text>
        </View>
      )}

      {/* 反馈 */}
      <View className="feedback">
        {feedbackDone ? (
          <Text className="feedback__done">感谢你的反馈，我们会持续优化生成质量 ✨</Text>
        ) : (
          <>
            <Text className="feedback__title">这封投诉信对你有帮助吗？</Text>
            {!feedbackOpen ? (
              <View className="feedback__btns">
                <Button className="feedback__btn" onClick={() => handleFeedback('helpful')}>有帮助 👍</Button>
                <Button className="feedback__btn feedback__btn--no" onClick={() => handleFeedback('unhelpful')}>需要改进 👎</Button>
              </View>
            ) : (
              <View className="feedback__form">
                <Textarea
                  className="feedback__textarea"
                  value={feedbackComment}
                  onInput={(e) => setFeedbackComment(e.detail.value)}
                  placeholder="哪里不满意？例如：法律条文引用不准确 / 事实描述有误…"
                  placeholderClass="feedback__placeholder"
                  maxlength={300}
                  autoHeight
                />
                <Button className="feedback__submit" onClick={handleFeedbackSubmit} loading={submitting}>
                  提交反馈
                </Button>
              </View>
            )}
          </>
        )}
      </View>

      <View className="disclaimer">
        <Text className="disclaimer__title">免责声明</Text>
        <Text className="disclaimer__text">
          本平台生成的投诉信与维权建议基于您提供的信息整理而成，仅供参考，不构成法律意见。提交前请核对事实与法律依据，必要时咨询执业律师。您的个人信息将严格按照《隐私政策》处理。
        </Text>
      </View>
    </View>
  )
}

export default ResultView
