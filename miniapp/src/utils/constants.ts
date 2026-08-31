// 分类展示配置
export const CATEGORY_COLORS: Record<string, string> = {
  '网购纠纷': '#2F6AB8',
  '服务纠纷': '#8B6BCB',
  '产品质量': '#1E9E6A',
  '食品安全': '#D97742',
  '虚假宣传': '#C2578A',
  '价格欺诈': '#D97706',
  '合同纠纷': '#5B8DEF',
  '其他': '#8B98AB',
}

export const CATEGORY_LABELS = Object.keys(CATEGORY_COLORS)

// 状态配置
export const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  generated: { label: '已生成', color: '#5B6B82', bg: '#EEF1F6' },
  copied: { label: '已复制', color: '#2F6AB8', bg: '#E7EFFB' },
  submitted: { label: '已提交', color: '#8A5CD6', bg: '#F1EAFB' },
  following_up: { label: '跟进中', color: '#D97706', bg: '#FDF1E3' },
  resolved: { label: '已解决', color: '#1E9E6A', bg: '#E4F5EE' },
  abandoned: { label: '已放弃', color: '#8B98AB', bg: '#F0F2F6' },
}

export const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'generated', label: '已生成' },
  { key: 'copied', label: '已复制' },
  { key: 'submitted', label: '已提交' },
  { key: 'following_up', label: '跟进中' },
  { key: 'resolved', label: '已解决' },
  { key: 'abandoned', label: '已放弃' },
]

// 状态流转（详情页 action sheet 使用）
export const STATUS_TRANSITIONS: Record<string, { key: string; label: string }[]> = {
  generated: [{ key: 'copied', label: '已复制投诉信' }],
  copied: [{ key: 'submitted', label: '已提交 12315' }],
  submitted: [{ key: 'following_up', label: '进入跟进中' }],
  following_up: [
    { key: 'resolved', label: '已解决' },
    { key: 'abandoned', label: '已放弃' },
  ],
}

// 官方投诉渠道入口（微信内无法直接跳转外部网页/小程序，统一用「复制入口指引」）
export interface ChannelEntry {
  name: string
  url: string
  search: string
}

export const CHANNEL_LINKS: Record<string, ChannelEntry> = {
  '12315': { name: '全国12315平台', url: 'https://www.12315.cn/', search: '全国12315平台' },
  '市场监管': { name: '全国12315平台', url: 'https://www.12315.cn/', search: '全国12315平台' },
  '黑猫': { name: '黑猫投诉', url: 'https://tousu.sina.com.cn/', search: '黑猫投诉' },
  '12321': { name: '12321网络不良与垃圾信息举报中心', url: 'https://www.12321.cn/', search: '12321举报中心' },
  '邮政': { name: '国家邮政局申诉网站', url: 'https://sswz.spb.gov.cn/', search: '国家邮政局申诉网站' },
  '工信部': { name: '工信部电信用户申诉受理中心', url: 'https://yhssglxt.miit.gov.cn/', search: '工信部申诉受理' },
  '人民法院': { name: '人民法院在线服务', url: '', search: '人民法院在线服务' },
  '法院': { name: '人民法院在线服务', url: '', search: '人民法院在线服务' },
  '平台': { name: '', url: '', search: '' },
}

export function findChannelEntry(name: string): ChannelEntry | null {
  if (!name) return null
  for (const key of Object.keys(CHANNEL_LINKS)) {
    if (name.includes(key)) return CHANNEL_LINKS[key]
  }
  return null
}

export function buildChannelEntryText(name: string, entry: ChannelEntry): string {
  const lines = [`【${name}】`]
  if (entry.search) lines.push(`微信搜索「${entry.search}」`)
  if (entry.url) lines.push(`浏览器打开：${entry.url}`)
  return lines.join('；')
}
