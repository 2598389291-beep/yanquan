import React, { useEffect, useState } from 'react'
import { View, Text, Image, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage } from '@tarojs/taro'
import {
  BASE_URL,
  deleteComplaint,
  getComplaintDetail,
  type ComplaintDetail as DetailData,
} from '../../services/api'
import ResultView from '../../components/ResultView'
import StatusBadge from '../../components/StatusBadge'
import Skeleton from '../../components/Skeleton'
import { CATEGORY_COLORS } from '../../utils/constants'
import { formatTime } from '../../utils/format'
import './index.scss'

const IMG = {
  copy: require('../../assets/icons/copy.png'),
  trash: require('../../assets/icons/trash.png'),
  doc: require('../../assets/icons/doc.png'),
  empty: require('../../assets/icons/empty.png'),
}

const DetailPage: React.FC = () => {
  const router = useRouter()
  const [data, setData] = useState<DetailData | null>(null)
  const [loading, setLoading] = useState(true)

  const loadDetail = async (id: number) => {
    setLoading(true)
    try {
      setData(await getComplaintDetail(id))
    } catch (e) {
      console.error('[Detail] 加载失败:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const id = Number(router.params.id)
    if (!id) {
      Taro.showToast({ title: '参数错误', icon: 'none' })
      return
    }
    loadDetail(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.params.id])

  useShareAppMessage(() => ({
    title: '我的维权投诉信 - 言权',
    path: `/pages/detail/index?id=${router.params.id || 1}`,
  }))

  const handleCopy = async () => {
    if (!data) return
    try {
      await Taro.setClipboardData({ data: data.complaint_letter })
      Taro.showToast({ title: '投诉信已复制', icon: 'success' })
    } catch (e) {
      Taro.showToast({ title: '复制失败', icon: 'none' })
    }
  }

  const handleDelete = () => {
    if (!data) return
    Taro.showModal({
      title: '删除记录',
      content: '删除后无法恢复，确定删除这条维权记录吗？',
      confirmColor: '#E05B5B',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await deleteComplaint(data.id)
          Taro.showToast({ title: '已删除', icon: 'success' })
          setTimeout(() => Taro.navigateBack({ delta: 1 }), 800)
        } catch (e) {
          console.error('[Detail] 删除失败', e)
        }
      },
    })
  }

  if (loading) {
    return (
      <View className="detail" style={{ padding: '24rpx' }}>
        <Skeleton rows={4} type="card" />
      </View>
    )
  }

  if (!data) {
    return (
      <View className="detail">
        <View className="empty-wrap">
          <Image className="empty-icon" src={IMG.empty} mode="aspectFit" />
          <Text className="empty-title">记录不存在或已被删除</Text>
          <Text className="empty-text">回到记录页看看其他维权记录吧</Text>
        </View>
      </View>
    )
  }

  const catColor = CATEGORY_COLORS[data.category] || '#8B98AB'
  const orderInfo = data.order_info || {}
  const evidence = data.evidence || []

  return (
    <View className="detail">
      {/* 头部信息 */}
      <View className="detail-hero">
        <View className="detail-hero__top">
          <View className="detail-hero__cat" style={{ color: catColor, background: `${catColor}1A` }}>
            <View className="detail-hero__dot" style={{ background: catColor }} />
            {data.category || '未分类'}
          </View>
          <StatusBadge status={data.status} label={data.status_label} size="md" />
        </View>
        <Text className="detail-hero__time">{formatTime(data.created_at)}</Text>

        {/* 订单信息 */}
        {orderInfo && (orderInfo.platform || orderInfo.seller || orderInfo.amount) && (
          <View className="order-chips">
            {orderInfo.platform && <View className="order-chip">平台：{orderInfo.platform}</View>}
            {orderInfo.seller && <View className="order-chip">商家：{orderInfo.seller}</View>}
            {orderInfo.product_name && <View className="order-chip">商品：{orderInfo.product_name}</View>}
            {orderInfo.amount && <View className="order-chip">金额：{orderInfo.amount}元</View>}
            {orderInfo.order_number && <View className="order-chip">订单号：{orderInfo.order_number}</View>}
          </View>
        )}
      </View>

      {/* 原始描述 */}
      <View className="quote card">
        <Text className="quote__label">你的维权描述</Text>
        <Text className="quote__text" selectable>{data.raw_text}</Text>
      </View>

      {/* 维权证据 */}
      {evidence.length > 0 && (
        <View className="detail-evidence card">
          <View className="section-title">
            <View className="section-title-bar" />
            <Text>维权证据（{evidence.length} 张）</Text>
          </View>
          <View className="detail-evidence__grid">
            {evidence.map((it, i) => (
              <View key={i} className="detail-evidence__cell">
                <Image
                  className="detail-evidence__img"
                  src={it.file_base64 ? `data:image/png;base64,${it.file_base64}` : (it.file_url.startsWith('http') ? it.file_url : `${BASE_URL}${it.file_url}`)}
                  mode="aspectFill"
                />
              </View>
            ))}
          </View>
          <Text className="detail-evidence__hint">证据已随投诉信一起保存，提交 12315 时可一并使用</Text>
        </View>
      )}

      {/* 完整结果 */}
      <ResultView data={data} />

      {/* 底部操作栏 */}
      <View className="bottom-bar safe-area-bottom">
        <View className="bar-inner">
          <Button className="bar-btn bar-btn--copy" onClick={handleCopy}>
            <Image className="bar-btn__icon" src={IMG.copy} mode="aspectFit" />
            复制
          </Button>
          <Button className="bar-btn bar-btn--delete" onClick={handleDelete}>
            <Image className="bar-btn__icon" src={IMG.trash} mode="aspectFit" />
            删除
          </Button>
        </View>
      </View>
      <View className="bottom-pad" />
    </View>
  )
}

export default DetailPage
