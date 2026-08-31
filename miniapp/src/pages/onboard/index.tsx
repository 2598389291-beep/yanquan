import React from 'react'
import { View, Text, Image, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

const IMG = {
  scale: require('../../assets/icons/scale.png'),
}

const OnboardPage: React.FC = () => {
  const finish = () => {
    Taro.setStorageSync('__onboarded', '1')
    Taro.switchTab({ url: '/pages/home/index' })
  }

  return (
    <View className="onboard">
      <View className="onboard__skip" onClick={finish}>
        <Text>跳过</Text>
      </View>

      <View className="onboard__brand">
        <View className="onboard__logo">
          <Image className="onboard__logo-img" src={IMG.scale} mode="aspectFit" />
        </View>
        <Text className="onboard__name">言权</Text>
        <View className="onboard__brand-line">
          <View className="onboard__brand-line__bar" />
          <Text className="onboard__brand-tag">消费者权益 · 维权文书助手</Text>
          <View className="onboard__brand-line__bar" />
        </View>
      </View>

      <View className="onboard__center">
        <View className="onboard__quote-block">
          <Text className="onboard__quote">法不恕无理</Text>
          <Text className="onboard__quote onboard__quote--sub">亦不欺弱小</Text>
        </View>
        <View className="onboard__slogan-row">
          <View className="onboard__slogan-row__line" />
          <Text className="onboard__slogan">口述即出信 · 维权有依据</Text>
          <View className="onboard__slogan-row__line" />
        </View>
      </View>

      <View className="onboard__footer safe-area-bottom">
        <Button className="onboard__btn" onClick={finish}>
          立即开始，免费维权
        </Button>
      </View>
    </View>
  )
}

export default OnboardPage
