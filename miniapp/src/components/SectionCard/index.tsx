import React, { useState } from 'react'
import { View, Text, Image } from '@tarojs/components'
import './index.scss'

interface Props {
  title: string
  icon?: string
  right?: React.ReactNode
  children: React.ReactNode
  className?: string
  collapsible?: boolean
  defaultOpen?: boolean
}

const SectionCard: React.FC<Props> = ({ title, icon, right, children, className = '', collapsible = false, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <View className={`section-card ${className}`}>
      <View className="section-card__head" onClick={collapsible ? () => setOpen(!open) : undefined}>
        <View className="section-card__title">
          {icon && <Image className="section-card__icon" src={icon} mode="aspectFit" />}
          <View className="section-card__bar" />
          <Text>{title}</Text>
        </View>
        {collapsible && <Text className={`section-card__toggle ${open ? 'section-card__toggle--open' : ''}`}>﹀</Text>}
        {right}
      </View>
      {open && <View className="section-card__body">{children}</View>}
    </View>
  )
}

export default SectionCard
