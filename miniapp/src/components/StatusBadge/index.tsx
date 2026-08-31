import React from 'react'
import { View, Text } from '@tarojs/components'
import { STATUS_CONFIG } from '../../utils/constants'
import './index.scss'

interface Props {
  status: string
  label?: string
  size?: 'sm' | 'md'
}

const StatusBadge: React.FC<Props> = ({ status, label, size = 'sm' }) => {
  const cfg = STATUS_CONFIG[status] || { label: '未知', color: '#8B98AB', bg: '#F0F2F6' }
  return (
    <View
      className={`status-badge ${size === 'md' ? 'status-badge--md' : ''}`}
      style={{ color: cfg.color, background: cfg.bg }}
    >
      <View className="status-badge__dot" style={{ background: cfg.color }} />
      <Text>{label || cfg.label}</Text>
    </View>
  )
}

export default StatusBadge
