import React, { useMemo } from 'react'
import { View, Text } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import './index.scss'

const USER_AGREEMENT = {
  title: '用户协议',
  updated: '更新日期：2026 年 8 月',
  sections: [
    {
      h: '一、服务说明',
      body: '「言权」是一款基于 AI 大模型的消费者维权辅助工具，帮助用户将口述/文字描述的消费纠纷整理为结构化的投诉信、法律依据检索与维权路径建议。本服务由 AI 自动生成内容，仅供用户参考与辅助使用。',
    },
    {
      h: '二、使用规则',
      body: '1. 用户应保证所描述的事实真实、准确，不得捏造、歪曲事实或恶意投诉；\n2. 用户应对基于 AI 生成内容的使用行为及其后果负责；\n3. 禁止利用本服务从事任何违法活动或侵害他人合法权益的行为；\n4. 用户提交的投诉内容不得包含侮辱、诽谤、侵权或违反公序良俗的信息。',
    },
    {
      h: '三、内容声明',
      body: 'AI 生成的法律依据与投诉信内容仅供参考，不构成法律意见，也不代表任何监管机构或司法机关的立场。重要法律事务请咨询执业律师。平台对因使用生成内容产生的纠纷不承担法律责任，但将依法配合监管部门的调查。',
    },
    {
      h: '四、账号与数据',
      body: '用户可通过微信或手机号登录。用户的维权记录（文字描述、投诉信、状态等）将保存在服务端，用于功能实现与体验优化。用户可随时在「我的」页面退出登录，或联系我们删除全部数据。',
    },
    {
      h: '五、协议变更',
      body: '我们可能根据法律法规或业务需要更新本协议，并在小程序内公示。更新后继续使用本服务，即视为同意修订后的协议。',
    },
  ],
}

const PRIVACY_POLICY = {
  title: '隐私政策',
  updated: '更新日期：2026 年 8 月',
  sections: [
    {
      h: '一、我们收集的信息',
      body: '1. 账号信息：微信登录产生的 openid、手机号（若选择手机号登录）；\n2. 维权内容：您输入的维权描述、上传的订单/聊天截图、AI 生成的投诉信与维权记录；\n3. 设备与日志：为保障服务安全，我们会记录基础的访问日志（IP、时间、接口）。',
    },
    {
      h: '二、信息的使用',
      body: '1. 用于生成投诉信、匹配法律依据、提供维权路径建议；\n2. 用于同步与展示您的维权记录；\n3. 用于改进 AI 生成质量与产品体验（我们会先对内容做去标识化处理）。',
    },
    {
      h: '三、信息的共享',
      body: '我们不会向任何第三方出售您的个人信息。仅在以下情形共享：1) 为您提供 AI 生成服务的技术服务商（如模型服务商，仅传输生成所需的文本）；2) 法律法规要求或监管机构依法调取。',
    },
    {
      h: '四、信息存储与保护',
      body: '您的数据存储于中国大陆境内的服务器，采用访问控制、传输加密等措施保护。您可随时联系我们注销账号并删除全部数据。数据保留期限为实现目的所必需的期限，最长不超过法律法规要求的期限。',
    },
    {
      h: '五、您的权利',
      body: '您有权查询、更正、删除您的个人信息，有权撤回授权、注销账号。行使权利请通过「意见反馈」或联系 support@yanquan.app，我们将在 15 个工作日内处理。',
    },
    {
      h: '六、未成年人保护',
      body: '本服务面向具有完全民事行为能力的成年人。若您为未成年人，请在监护人指导下使用，并征得监护人同意后提交个人信息。',
    },
  ],
}

const AgreementPage: React.FC = () => {
  const router = useRouter()
  const doc = useMemo(() => (router.params.type === 'privacy' ? PRIVACY_POLICY : USER_AGREEMENT), [router.params.type])
  Taro.setNavigationBarTitle({ title: doc.title })

  return (
    <View className="agreement-page">
      <Text className="agreement-page__title">{doc.title}</Text>
      <Text className="agreement-page__updated">{doc.updated}</Text>
      {doc.sections.map((s, i) => (
        <View key={i} className="agreement-page__section">
          <Text className="agreement-page__h">{s.h}</Text>
          <Text className="agreement-page__body" selectable>{s.body}</Text>
        </View>
      ))}
      <View className="agreement-page__footer">
        <Text>「言权」团队</Text>
        <Text>support@yanquan.app</Text>
      </View>
    </View>
  )
}

export default AgreementPage
