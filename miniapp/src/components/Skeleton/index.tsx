import React from 'react'
import { View } from '@tarojs/components'
import './index.scss'

interface Props {
  rows?: number
  type?: 'list' | 'card'
}

/** 加载骨架屏：用于列表/卡片加载时的占位反馈 */
const Skeleton: React.FC<Props> = ({ rows = 3, type = 'list' }) => {
  return (
    <View className={`skeleton skeleton--${type}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <View key={i} className="skeleton__item">
          <View className="skeleton__bar skeleton__bar--title" />
          <View className="skeleton__bar skeleton__bar--line" />
          <View className="skeleton__bar skeleton__bar--short" />
        </View>
      ))}
    </View>
  )
}

export default Skeleton
