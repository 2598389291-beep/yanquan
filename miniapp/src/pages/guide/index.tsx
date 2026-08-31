import React, { useState } from 'react'
import { View, Text, Image, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import {
  getGuideScenarios,
  getCommonTemplates,
  getReferenceCases,
  getEvidenceChecklist,
  getEvidenceScenarios,
  getScenarioDecisions,
  type GuideScenario,
  type CommonTemplate,
  type ReferenceCase,
  type DecisionChannel,
  type EvidenceChecklist,
} from '../../services/api'
import { findChannelEntry, buildChannelEntryText } from '../../utils/constants'
import Skeleton from '../../components/Skeleton'
import './index.scss'

const IMG = {
  chevron: require('../../assets/icons/chevron.png'),
  scale: require('../../assets/icons/scale.png'),
  chat: require('../../assets/icons/chat.png'),
  arrow: require('../../assets/icons/arrow.png'),
}

type Tab = 'scenarios' | 'templates' | 'cases' | 'evidence'

const copyText = async (text: string, tip: string) => {
  try {
    await Taro.setClipboardData({ data: text })
    Taro.showToast({ title: tip, icon: 'success' })
  } catch (e) {
    Taro.showToast({ title: '复制失败', icon: 'none' })
  }
}

const GuidePage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('scenarios')
  const [scenarios, setScenarios] = useState<GuideScenario[]>([])
  const [templates, setTemplates] = useState<CommonTemplate[]>([])
  const [cases, setCases] = useState<ReferenceCase[]>([])
  const [decisions, setDecisions] = useState<Record<string, DecisionChannel[]>>({})
  const [evidenceScenarios, setEvidenceScenarios] = useState<{ key: string; title: string; icon: string }[]>([])
  const [evidenceChecklist, setEvidenceChecklist] = useState<EvidenceChecklist | null>(null)
  const [evidenceKey, setEvidenceKey] = useState('general')
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string>('')
  const [expandedTemplate, setExpandedTemplate] = useState<string>('')
  const [expandedCase, setExpandedCase] = useState<string>('')

  const reload = async () => {
    setLoading(true)
    try {
      const [s, t, c, d, ev] = await Promise.all([
        getGuideScenarios().catch(() => null),
        getCommonTemplates().catch(() => null),
        getReferenceCases().catch(() => null),
        getScenarioDecisions().catch(() => null),
        getEvidenceScenarios().catch(() => null),
      ])
      setScenarios(s?.scenarios || [])
      setTemplates(t?.templates || [])
      setCases(c?.cases || [])
      setDecisions(d?.decisions || {})
      const evs = ev?.scenarios || []
      setEvidenceScenarios(evs)
      if (evs.length) {
        setEvidenceKey(evs[0].key)
        loadEvidence(evs[0].key)
      }
    } catch (e) {
      console.error('[Guide] 加载失败', e)
    } finally {
      setLoading(false)
    }
  }

  const loadEvidence = async (key: string) => {
    setEvidenceKey(key)
    try {
      setEvidenceChecklist(await getEvidenceChecklist(key))
    } catch (e) {
      console.warn('[Guide] 证据清单加载失败', e)
    }
  }

  useDidShow(() => {
    reload()
    // 首页热门场景 → 直达对应模板
    const target = Taro.getStorageSync('__guideTarget')
    if (target) {
      Taro.removeStorageSync('__guideTarget')
      try {
        const t = JSON.parse(target)
        if (t.tab === 'templates') {
          setTab('templates')
          if (t.key) setExpandedTemplate(t.key)
        } else if (t.tab === 'cases') {
          setTab('cases')
        }
      } catch (e) {}
    }
  })

  const toggle = (key: string) => setExpanded(expanded === key ? '' : key)
  const toggleTemplate = (key: string) => setExpandedTemplate(expandedTemplate === key ? '' : key)
  const toggleCase = (key: string) => setExpandedCase(expandedCase === key ? '' : key)

  const useTemplate = (letter: string) => {
    Taro.setStorageSync('__pendingTemplate', letter)
    Taro.navigateTo({ url: '/pages/compose/index' })
  }

  const copyChannelEntries = (channel: string) => {
    const segs = channel.split(/[→>]/).map((x) => x.trim()).filter(Boolean)
    const lines = segs
      .map((seg) => {
        const entry = findChannelEntry(seg)
        if (!entry || (!entry.search && !entry.url)) return null
        return buildChannelEntryText(seg, entry)
      })
      .filter(Boolean) as string[]
    copyText(lines.length ? lines.join('\n') : `建议渠道：${channel}`, '官方入口已复制')
  }

  const copyTemplateEntry = (t: CommonTemplate) => {
    copyText(
      `【${t.channel_name}】\n微信搜索「${t.search_key}」${t.channel_url ? `\n浏览器打开：${t.channel_url}` : ''}`,
      '官方入口已复制',
    )
  }

  return (
    <View className="guide">
      <View className="guide-hero">
        <View className="guide-hero__icon">
          <Image className="guide-hero__img" src={IMG.scale} mode="aspectFit" />
        </View>
        <Text className="guide-hero__title">维权指南</Text>
        <Text className="guide-hero__sub">场景指南 · 即用模板 · 真实案例参考</Text>
      </View>

      <View className="guide-tabs">
        <View className={`guide-tab ${tab === 'scenarios' ? 'guide-tab--active' : ''}`} onClick={() => setTab('scenarios')}>
          场景指南
        </View>
        <View className={`guide-tab ${tab === 'templates' ? 'guide-tab--active' : ''}`} onClick={() => setTab('templates')}>
          通用模板
        </View>
        <View className={`guide-tab ${tab === 'cases' ? 'guide-tab--active' : ''}`} onClick={() => setTab('cases')}>
          案例参考
        </View>
        <View className={`guide-tab ${tab === 'evidence' ? 'guide-tab--active' : ''}`} onClick={() => setTab('evidence')}>
          证据清单
        </View>
      </View>

      {loading ? (
        <View style={{ padding: '0 24rpx' }}><Skeleton rows={4} type="card" /></View>
      ) : tab === 'scenarios' ? (
        <View className="guide-list">
          {scenarios.length === 0 ? (
            <View className="guide-loading">
              <Text>加载失败，请检查网络</Text>
              <Button className="guide-retry" onClick={reload}>点击重试</Button>
            </View>
          ) : (
            scenarios.map((s) => {
              const open = expanded === s.key
              return (
                <View key={s.key} className={`scenario ${open ? 'scenario--open' : ''}`} onClick={() => toggle(s.key)}>
                  <View className="scenario__head">
                    <Text className="scenario__icon">{s.icon}</Text>
                    <View className="scenario__info">
                      <Text className="scenario__title">{s.title}</Text>
                      <Text className="scenario__summary">{s.summary}</Text>
                    </View>
                    <Image className={`scenario__arrow ${open ? 'scenario__arrow--open' : ''}`} src={IMG.chevron} mode="aspectFit" />
                  </View>

                  {open && (
                    <View className="scenario__body">
                      <View className="scenario__section">
                        <View className="scenario__label">
                          <Image className="scenario__label-icon" src={IMG.scale} mode="aspectFit" />
                          <Text>适用法律</Text>
                        </View>
                        {s.laws.map((law, i) => (
                          <View key={i} className="law-row">
                            <View className="law-row__seal">法</View>
                            <Text className="law-row__text">{law.law_name} {law.article}</Text>
                          </View>
                        ))}
                      </View>

                      <View className="scenario__section">
                        <View className="scenario__label">
                          <Image className="scenario__label-icon" src={IMG.arrow} mode="aspectFit" />
                          <Text>行动步骤</Text>
                        </View>
                        {s.steps.map((step, i) => (
                          <View key={i} className="step-row">
                            <View className="step-row__num">{i + 1}</View>
                            <Text className="step-row__text">{step}</Text>
                          </View>
                        ))}
                      </View>

                      <View className="scenario__section">
                        <View className="scenario__label">
                          <Image className="scenario__label-icon" src={IMG.chat} mode="aspectFit" />
                          <Text>小技巧</Text>
                        </View>
                        {s.tips.map((tip, i) => (
                          <View key={i} className="tip-row">
                            <View className="tip-row__dot" />
                            <Text className="tip-row__text">{tip}</Text>
                          </View>
                        ))}
                      </View>

                      <View className="scenario__channel">
                        <Text className="scenario__channel-label">建议渠道</Text>
                        <Text className="scenario__channel-text">{s.channel}</Text>
                        <Button className="scenario__channel-btn" onClick={() => copyChannelEntries(s.channel)}>
                          复制官方入口
                        </Button>
                      </View>

                      {(decisions[s.key] || []).length > 0 && (
                        <View className="scenario__decision">
                          <View className="scenario__label">
                            <Image className="scenario__label-icon" src={IMG.arrow} mode="aspectFit" />
                            <Text>路线怎么选（决策参考）</Text>
                          </View>
                          {decisions[s.key].map((d, i) => (
                            <View key={i} className="decision-card">
                              <View className="decision-card__head">
                                <Text className="decision-card__name">{d.channel}</Text>
                                <Text className="decision-card__cost">{d.cost}</Text>
                              </View>
                              <Text className="decision-card__row">适用：{d.when}</Text>
                              <Text className="decision-card__row">耗时：{d.duration}</Text>
                              <Text className="decision-card__row decision-card__row--next">之后：{d.next}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                    </View>
                  )}
                </View>
              )
            })
          )}
        </View>
      ) : tab === 'templates' ? (
        <View className="guide-list">
          <View className="tab-note">高频纠纷即用模板，把【】里的内容替换成你的实际情况即可</View>
          {templates.map((t) => {
            const open = expandedTemplate === t.key
            return (
              <View key={t.key} className={`tpl-card ${open ? 'tpl-card--open' : ''}`}>
                <View className="tpl-card__head" onClick={() => toggleTemplate(t.key)}>
                  <Text className="tpl-card__icon">{t.icon}</Text>
                  <View className="tpl-card__info">
                    <Text className="tpl-card__title">{t.title}</Text>
                    <Text className="tpl-card__summary">{t.summary}</Text>
                  </View>
                  <Image className={`tpl-card__arrow ${open ? 'tpl-card__arrow--open' : ''}`} src={IMG.chevron} mode="aspectFit" />
                </View>

                {open && (
                  <View className="tpl-card__body">
                    <View className="tpl-card__label">投诉信模板</View>
                    <View className="tpl-card__letter" selectable>{t.letter}</View>

                    <View className="tpl-card__label">法律依据</View>
                    {t.laws.map((law, i) => (
                      <View key={i} className="law-row">
                        <View className="law-row__seal">法</View>
                        <Text className="law-row__text">{law}</Text>
                      </View>
                    ))}

                    <View className="tpl-card__label">提交渠道</View>
                    <View className="tpl-card__channel">
                      <Text className="tpl-card__channel-name">{t.channel_name}</Text>
                      <Text className="tpl-card__channel-hint">
                        微信搜索「{t.search_key}」{t.channel_url ? `，或浏览器打开 ${t.channel_url}` : ''}
                      </Text>
                    </View>

                    <View className="tpl-card__actions">
                      <Button className="tpl-btn tpl-btn--use" onClick={() => useTemplate(t.letter)}>填入并生成</Button>
                      <Button className="tpl-btn tpl-btn--copy" onClick={() => copyText(t.letter, '模板已复制，替换【】后使用')}>复制全文</Button>
                      <Button className="tpl-btn tpl-btn--entry" onClick={() => copyTemplateEntry(t)}>复制官方入口</Button>
                    </View>
                  </View>
                )}
              </View>
            )
          })}
        </View>
      ) : tab === 'cases' ? (
        <View className="guide-list">
          <View className="tab-note">脱敏处理后的公开维权案例，供你参考处理路径和解决周期</View>
          {cases.map((c) => {
            const open = expandedCase === c.key
            return (
              <View key={c.key} className={`case-card ${open ? 'case-card--open' : ''}`}>
                <View className="case-card__head" onClick={() => toggleCase(c.key)}>
                  <Text className="case-card__icon">{c.icon}</Text>
                  <View className="case-card__info">
                    <Text className="case-card__title">{c.title}</Text>
                    <Text className="case-card__summary">{c.summary}</Text>
                  </View>
                  <Image className={`case-card__arrow ${open ? 'case-card__arrow--open' : ''}`} src={IMG.chevron} mode="aspectFit" />
                </View>

                {open && (
                  <View className="case-card__body">
                    <View className="case-card__meta">
                      <View className="case-card__meta-item"><Text className="case-card__meta-label">处理结果</Text><Text className="case-card__meta-value">{c.outcome}</Text></View>
                      <View className="case-card__meta-item"><Text className="case-card__meta-label">解决周期</Text><Text className="case-card__meta-value">{c.duration}</Text></View>
                      <View className="case-card__meta-item"><Text className="case-card__meta-label">处理渠道</Text><Text className="case-card__meta-value">{c.channel}</Text></View>
                    </View>
                    <View className="case-card__label">关键做法</View>
                    {c.points.map((p, i) => (
                      <View key={i} className="tip-row">
                        <View className="tip-row__dot" />
                        <Text className="tip-row__text">{p}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )
          })}
        </View>
      ) : (
        <View className="guide-list">
          <View className="tab-note">选一个场景，看看投诉前需要留哪些证据（举证是维权的关键）</View>
          <View className="evidence-tabs">
            {evidenceScenarios.map((e) => (
              <View
                key={e.key}
                className={`evidence-tab ${evidenceKey === e.key ? 'evidence-tab--active' : ''}`}
                onClick={() => loadEvidence(e.key)}
              >
                <Text className="evidence-tab__icon">{e.icon}</Text>
                <Text className="evidence-tab__title">{e.title}</Text>
              </View>
            ))}
          </View>
          {evidenceChecklist && (
            <View className="evidence-card">
              <View className="evidence-card__head">
                <Text className="evidence-card__title">{evidenceChecklist.icon} {evidenceChecklist.title} · 建议留这些证据</Text>
              </View>
              {evidenceChecklist.items.map((it, i) => (
                <View key={i} className="evidence-card__item">
                  <View className="evidence-card__num">{i + 1}</View>
                  <View className="evidence-card__main">
                    <Text className="evidence-card__name">{it.item}</Text>
                    <Text className="evidence-card__row">为什么留：{it.purpose}</Text>
                    <Text className="evidence-card__row evidence-card__row--how">怎么留：{it.how}</Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      )}

      <View className="guide-footer">
        <Text>以上内容仅供参考，不构成法律意见。重要纠纷请咨询执业律师。</Text>
      </View>
      <View style={{ height: 40 }} />
    </View>
  )
}

export default GuidePage
