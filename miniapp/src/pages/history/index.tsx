import React, { useMemo, useState } from 'react'
import { View, Text, Image, Button, ScrollView } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { getComplaintList, type ComplaintListItem } from '../../services/api'
import { CATEGORY_COLORS, STATUS_CONFIG, STATUS_FILTERS } from '../../utils/constants'
import { formatTime, shortText } from '../../utils/format'
import StatusBadge from '../../components/StatusBadge'
import Skeleton from '../../components/Skeleton'
import './index.scss'

interface HistoryItem {
  id: number
  summary: string
  category: string
  status: string
  status_label: string
  created_at: string
}

const IMG = {
  chevron: require('../../assets/icons/chevron.png'),
  doc: require('../../assets/icons/doc.png'),
  empty: require('../../assets/icons/empty.png'),
}

const HistoryPage: React.FC = () => {
  const [activeStatus, setActiveStatus] = useState('all')
  const [list, setList] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({ total: 0, in_progress: 0, categories: 0 })

  const loadData = async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const resp = await getComplaintList(1, 100, activeStatus)
      setList(
        resp.items.map((item: ComplaintListItem) => ({
          id: item.id,
          summary: shortText(item.raw_text, 46),
          category: item.category || '未分类',
          status: item.status,
          status_label: item.status_label || STATUS_CONFIG[item.status]?.label || '已生成',
          created_at: formatTime(item.created_at),
        }))
      )
    } catch (e) {
      console.error('[History] 加载失败:', e)
      setList([])
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const all = await getComplaintList(1, 100)
      const total = all.total
      const inProgress = all.items.filter((i) => ['submitted', 'following_up'].includes(i.status)).length
      const categories = new Set(all.items.map((i) => i.category)).size
      setStats({ total, in_progress: inProgress, categories })
    } catch (e) {
      console.warn('[History] 统计失败', e)
    }
  }

  useDidShow(() => {
    loadData()
    loadStats()
  })

  usePullDownRefresh(async () => {
    await loadData(false)
    await loadStats()
    Taro.stopPullDownRefresh()
  })

  const changeStatus = (key: string) => {
    setActiveStatus(key)
    loadData()
  }

  const goDetail = (id: number) => Taro.navigateTo({ url: `/pages/detail/index?id=${id}` })
  const goCompose = () => Taro.navigateTo({ url: '/pages/compose/index' })

  const grouped = useMemo(() => {
    const byDate: { date: string; items: HistoryItem[] }[] = []
    list.forEach((item) => {
      const date = (item.created_at || '').slice(0, 10)
      const last = byDate[byDate.length - 1]
      if (last && last.date === date) last.items.push(item)
      else byDate.push({ date, items: [item] })
    })
    return byDate
  }, [list])

  return (
    <View className="history">
      {/* 统计条 */}
      <View className="stat-bar">
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

      {/* 状态筛选 */}
      <ScrollView className="filter-bar" scrollX showScrollbar={false}>
        {STATUS_FILTERS.map((f) => (
          <View
            key={f.key}
            className={`filter-chip ${activeStatus === f.key ? 'filter-chip--active' : ''}`}
            onClick={() => changeStatus(f.key)}
          >
            {f.label}
          </View>
        ))}
      </ScrollView>

      {/* 列表 */}
      {loading && list.length === 0 ? (
        <View style={{ padding: "0 24rpx" }}><Skeleton rows={4} type="card" /></View>
      ) : list.length === 0 ? (
        <View className="empty-wrap">
          <Image className="empty-icon" src={IMG.empty} mode="aspectFit" />
          <Text className="empty-title">还没有维权记录</Text>
          <Text className="empty-text">把第一次委屈变成文字，言权帮你写好投诉信</Text>
          <Button className="empty-btn" onClick={goCompose}>生成第一封投诉信</Button>
        </View>
      ) : (
        <View className="list">
          {grouped.map((group) => (
            <View key={group.date} className="group">
              <Text className="group__date">{group.date}</Text>
              {group.items.map((item) => {
                const catColor = CATEGORY_COLORS[item.category] || '#8B98AB'
                return (
                  <View key={item.id} className="item" onClick={() => goDetail(item.id)}>
                    <View className="item__top">
                      <View className="item__cat" style={{ color: catColor, background: `${catColor}1A` }}>
                        <View className="item__dot" style={{ background: catColor }} />
                        {item.category}
                      </View>
                      <StatusBadge status={item.status} label={item.status_label} />
                    </View>
                    <Text className="item__summary">{item.summary}</Text>
                    <View className="item__bottom">
                      <Text className="item__time">{item.created_at}</Text>
                      <View className="item__more">
                        <Text className="item__more-text">查看详情</Text>
                        <Image className="item__arrow" src={IMG.chevron} mode="aspectFit" />
                      </View>
                    </View>
                  </View>
                )
              })}
            </View>
          ))}
        </View>
      )}
      <View style={{ height: 40 }} />
    </View>
  )
}

export default HistoryPage
