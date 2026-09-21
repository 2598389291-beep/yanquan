import Taro from '@tarojs/taro'

// ============================================================
// 后端地址配置
// ------------------------------------------------------------
// 默认连接本机后端 http://127.0.0.1:8000（微信开发者工具、浏览器预览均可用）
// 真机调试时请改为电脑的局域网 IP，如 http://192.168.1.100:8000
// 正式上线前改为你的 HTTPS 域名（需在小程序后台配置 request 合法域名）：
//   export const BASE_URL = 'https://api.yanquan.example.com'
// ============================================================

export const BASE_URL = 'https://yanquan-backend-301468-10-1473499185.sh.run.tcloudbase.com'

// ============================================================
// 云调用配置（方案 B：免域名、免备案）
// ------------------------------------------------------------
// 小程序端通过 wx.cloud.callContainer 直连云托管后端，
// 不需要 request/uploadFile 合法域名。
// CLOUD_ENV：填云开发环境 ID（云开发控制台首页可见，形如 yanquan-xxxx）
// 留空则使用默认环境。H5 预览仍走 BASE_URL（仅供开发预览）。
// ============================================================
// 当前 AppID 名下实际关联的环境是 mianfei-d4g7c7ar072ed8f65（devtools 云环境列表确认）
// 之前填的 yanquan-d5g2at6al1211fff3 不在关联列表中，保留为自动尝试的后备
export const CLOUD_ENV = 'mianfei-d4g7c7ar072ed8f65'
export const CLOUD_ENV_FALLBACKS = ['yanquan-d5g2at6al1211fff3']

// 云托管服务名称（微信云托管控制台 → 服务管理 → 服务列表 → 服务名称）
// 按官方文档，callContainer 必须在 header 带 X-WX-SERVICE，否则网关报 -601031 INVALID_PATH
export const CLOUD_SERVICE = 'yanquan-backend'

let cloudReady = false
let cloudInitError = ''
let cloudService = '' // 缓存实际可用的云托管服务名
let cloudEnv = '' // 缓存实际可用的云开发环境 ID
export async function initCloud() {
  if (process.env.TARO_ENV === 'h5') return
  try {
    if (!Taro.cloud) {
      cloudInitError = 'Taro.cloud 不存在'
      console.warn('[Cloud] Taro.cloud 不存在')
      return
    }
    // 等待初始化完成再置位，避免启动首请求撞上“云未初始化”
    await Taro.cloud.init(CLOUD_ENV ? { env: CLOUD_ENV } : {})
    cloudReady = true
  } catch (e: any) {
    cloudInitError = e?.errMsg || e?.message || String(e)
    console.warn('[Cloud] 初始化失败，回退直连模式', e)
  }
}

const useCloud = (): boolean => process.env.TARO_ENV !== 'h5' && cloudReady

export interface ApiResp<T = any> {
  code: number
  data: T
  detail?: string
  message?: string
}

const getToken = (): string => Taro.getStorageSync('token') || ''
// 每个设备生成独立的匿名用户 ID（用于免费次数等按用户统计，无需登录）
const getUserId = (): string => {
  let uid = Taro.getStorageSync('user_id') || ''
  if (!uid) {
    uid = `dev_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
    Taro.setStorageSync('user_id', uid)
  }
  return uid
}

/** 业务/接口错误（后端已返回明确信息），与网络错误区分，避免重复弹窗 */
class ApiError extends Error {
  constructor(msg: string) {
    super(msg)
    this.name = 'ApiError'
  }
}

/** 请求可选参数：silent=true 用于后台加载/静默轮询，失败不打扰用户 */
export interface ReqOptions extends Partial<Taro.request.Option> {
  silent?: boolean
}

const CLOUD_TIMEOUT = 30000 // 云调用单次超时（冷启动较慢，放宽到 30s）
const isH5 = process.env.TARO_ENV === 'h5'
const isWeapp = process.env.TARO_ENV === 'weapp'

let lastToastAt = 0
/** 3 秒内最多弹一次错误，避免启动时多请求并发失败刷屏 */
function safeToast(title: string) {
  const now = Date.now()
  if (now - lastToastAt < 3000) return
  lastToastAt = now
  Taro.showToast({ title, icon: 'none', duration: 3000 })
}

/** 是否允许直连公网域名兜底：仅 H5 / 开发者工具。真机正式版一律走云调用，不再请求未备案域名 */
function canDirectFallback(): boolean {
  if (isH5) return true
  if (isWeapp) {
    try {
      return Taro.getSystemInfoSync().platform === 'devtools'
    } catch {
      return false
    }
  }
  return false
}

/** 判断是否瞬时网络错误（超时/断网等，重试一次有意义；带错误码的配置类错误不重试） */
function isTransientError(e: any): boolean {
  const reason = String(e?.errMsg || e?.message || e || '').toLowerCase()
  if (reason.includes('timeout') || reason.includes('abort') || reason.includes('econn') || reason.includes('enotfound') || reason.includes('getaddrinfo') || reason.includes('socket')) return true
  const code = Number(e?.errCode)
  if (code && code < 0) return false // 配置/权限类错误（如 INVALID_PATH），重试无意义
  return reason.includes('request:fail') || reason.includes('callcontainer:fail') || reason.includes('network') || reason.includes('500') || reason.includes('502') || reason.includes('503')
}

/** 云调用失败时给用户的提示：真机上不出现“开发者工具勾选”这类无效指引 */
function cloudFailTitle(e: any, directAllowed: boolean): string {
  const reason = String(e?.errMsg || e?.message || e || '')
  const code = e?.errCode ? `[${e.errCode}] ` : ''
  if (code && (reason.includes('invalid_path') || Number(e.errCode) === -601031)) {
    return '云调用路径配置有误，请检查云托管服务名与 X-WX-SERVICE'
  }
  if (reason.includes('url not in domain list')) {
    return directAllowed ? '域名被拦截：请在开发者工具勾选「不校验合法域名」后重新编译' : '网络请求被拦截，请稍后重试'
  }
  if (isTransientError(e)) return '网络连接不稳定，请稍后重试'
  const short = reason.replace(/^cloud\.callcontainer:fail\s*/i, '').replace(/^request:fail\s*/i, '').replace(/^errmsg\s*/i, '').slice(0, 40)
  return short ? `云服务暂时不可用（${short}），请稍后重试` : '云服务暂时不可用，请稍后重试'
}

/** 把请求失败原因转成用户能看懂的话 */
function friendlyNetworkError(reason: string): string {
  if (!reason) return '网络请求失败，请重试'
  if (reason.includes('url not in domain list')) {
    return '域名被拦截：请在开发者工具勾选「不校验合法域名」后重新编译'
  }
  if (reason.includes('timeout')) {
    return '请求超时：AI 生成较慢，请稍后重试'
  }
  if (reason.includes('refused') || reason.includes('ECONNREFUSED')) {
    return '无法连接后端：请先双击「启动演示.command」启动服务'
  }
  return '网络连接失败，请检查后端服务'
}

export async function request<T = any>(
  url: string,
  options: ReqOptions = {}
): Promise<T> {
  const silent = options.silent === true
  const reqOptions = { ...options } as any
  delete reqOptions.silent
  let fullUrl = ''
  try {
    if (useCloud()) {
      // 云调用（官方规则）：
      // 1) path 必须以 / 开头（根路径为 /，业务路径如 /api/meta）
      // 2) header 必须带 X-WX-SERVICE，值为云托管服务名称
      // 3) config.env 填云开发环境 ID
      // 查询参数原样保留在 path 中，data 作为请求体
      const cloudData: Record<string, any> = { ...((options.data || {}) as any) }
      const cloudPath = url.startsWith('/') ? url : `/${url}`
      // 候选组合：已记住的可用环境/服务优先，其余按官方配置与历史后备逐个尝试
      const allEnvs = [CLOUD_ENV, ...CLOUD_ENV_FALLBACKS]
      const allSvcs = [CLOUD_SERVICE, 'yanquan-backend-011']
      const pairs: Array<[string, string]> = []
      const pushPair = (env: string, svc: string) => {
        if (!pairs.some((p) => p[0] === env && p[1] === svc)) pairs.push([env, svc])
      }
      if (cloudEnv && cloudService) pushPair(cloudEnv, cloudService)
      for (const env of allEnvs) for (const svc of allSvcs) pushPair(env, svc)
      let lastErr: any = null
      // 超时/断网类错误自动重试一轮；配置类错误（带 errCode）不空转
      for (let round = 0; round < 2; round++) {
        let anyTransient = false
        for (const [env, svc] of pairs) {
          try {
            const res = await Taro.cloud.callContainer({
              config: { env } as any,
              path: cloudPath,
              method: (options.method || 'GET') as any,
              header: {
                ...(options.header || {}),
                'X-WX-SERVICE': svc,
                ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
              },
              data: cloudData,
              timeout: CLOUD_TIMEOUT,
            })
            const sc = (res as any).statusCode || 200
            const data = res.data as ApiResp<T>
            if (data && typeof data.code === 'number') {
              cloudEnv = env // 记住可用环境
              cloudService = svc // 记住可用服务名
              if (data.code === 0) return data.data
              const msg = data?.detail || data?.message || '请求失败'
              console.error('[API] 业务错误:', url, sc, msg)
              if (!silent) safeToast(msg)
              throw new ApiError(msg) // 业务错误：提示一次即止，不再重试其他组合
            }
            lastErr = new Error(`网关响应异常 status=${sc}`)
          } catch (e) {
            lastErr = e
            if (isTransientError(e)) anyTransient = true
            if (e instanceof ApiError) throw e
          }
        }
        if (!anyTransient) break // 无瞬时错误（如配置类）时不再空转第二轮
      }
      if (lastErr) {
        console.warn('[API] 云调用全部失败:', lastErr)
        // 真机正式版：云调用是唯一通道，不再请求未备案的公网域名（会被域名白名单拦截）
        if (!canDirectFallback()) {
          if (!silent) safeToast(cloudFailTitle(lastErr, false))
          ;(lastErr as any)._toasted = true
          throw lastErr
        }
        if (!silent) safeToast('云服务暂不可用，已切换直连模式')
      } else {
        throw new ApiError('云调用失败')
      }
    }

    fullUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`
    const res = await Taro.request({
      url: fullUrl,
      timeout: 120000,
      header: {
        'Content-Type': 'application/json',
        ...(options.header || {}),
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      },
      ...reqOptions,
    })
    const data = res.data as ApiResp<T>
    if (data.code === 0) {
      return data.data
    }
    const msg = data.detail || data.message || '请求失败'
    console.error('[API] 业务错误:', fullUrl, msg)
    if (!silent) safeToast(msg)
    throw new ApiError(msg)
  } catch (e: any) {
    const reason = e?.errMsg || e?.message || String(e)
    console.error('[API] 请求失败:', fullUrl || url, reason)
    // 业务错误只在抛出前提示过一次；网络错误在此按模式给友好提示
    if (!(e instanceof ApiError) && !silent && !(e as any)?._toasted) {
      const title = useCloud()
        ? cloudFailTitle(e, canDirectFallback())
        : cloudInitError
          ? `服务初始化失败：${friendlyNetworkError(reason)}`
          : friendlyNetworkError(reason)
      safeToast(title)
    }
    throw e
  }
}

// ---------- 认证 ----------

export interface LoginData {
  token: string
  phone: string
  email: string
  user_id: number
  nickname: string
  avatar: string
  expires_at: string
}

export const emailLogin = (email: string, password: string) =>
  request<LoginData>('/api/auth/email/login', {
    method: 'POST',
    data: { email, password },
  })

export const wechatLogin = (code: string, nickname: string = '', silentLogin: boolean = false) =>
  request<LoginData>('/api/auth/wechat/login', {
    method: 'POST',
    data: { code, nickname },
    silent: silentLogin === true,
  })

// 轻回访：提交最终处理结果（不打扰，一次即可）
export const submitOutcome = (complaintId: number, outcome: string) =>
  request<{ message: string }>(`/api/complaint/${complaintId}/outcome`, {
    method: 'POST',
    data: { outcome, user_id: getUserId() },
  })

// ---------- 系统 ----------

export interface MetaInfo {
  app_name: string
  slogan: string
  version: string
  demo_mode: boolean
  is_admin?: boolean
  features: { voice: boolean; ocr: boolean; wechat_login: boolean }
  stats?: { laws: number; scenarios: number; templates: number; cases: number }
}

export const getMeta = () => request<MetaInfo>('/api/meta', { method: 'GET', silent: true })

export interface UsageInfo {
  total: number
  used: number
  remaining: number
  unlimited?: boolean
}

export const getUsage = () =>
  request<UsageInfo>(`/api/usage?user_id=${encodeURIComponent(getUserId())}`, { method: 'GET', silent: true })

// ---------- 任务式生成（先出骨架，边生成边补全） ----------

export interface TaskInfo {
  task_id: string
  status: 'running' | 'done' | 'error'
  stage: string
  progress: number
  skeleton: string
  result?: ComplaintDetail
  error?: string
}

export const createTextTask = (text: string, orderInfo: Record<string, any>, evidence: any[]) =>
  request<{ task_id: string }>('/api/complaint/task', {
    method: 'POST',
    data: { text, user_id: getUserId(), order_info: orderInfo, evidence },
  })

export const createVoiceTaskByUrl = (audioUrl: string, audioName: string, orderInfo: Record<string, any>, evidence: any[]) =>
  request<{ task_id: string }>('/api/complaint/task/voice', {
    method: 'POST',
    data: { audio_url: audioUrl, audio_name: audioName, user_id: getUserId(), order_info: orderInfo, evidence },
  })

export const getTaskStatus = (taskId: string) =>
  request<TaskInfo>(`/api/complaint/task/${taskId}`, { method: 'GET', silent: true })

// 读取本地文件为 base64（语音兜底转写用）
export const readFileAsBase64 = (filePath: string): Promise<string> =>
  new Promise((resolve, reject) => {
    try {
      const fs = Taro.getFileSystemManager()
      fs.readFile({ filePath, encoding: 'base64', success: (r) => resolve(r.data), fail: reject })
    } catch (e) {
      reject(e)
    }
  })

// 仅语音转文字（不消耗免费次数）：转写后交用户确认修改再生成
export const transcribeVoiceByUrl = (audioUrl: string, audioName: string) =>
  request<{ text: string }>('/api/complaint/transcribe', {
    method: 'POST',
    data: { audio_url: audioUrl, audio_name: audioName },
  })

export const transcribeVoiceByBase64 = (audioBase64: string, audioName: string) =>
  request<{ text: string }>('/api/complaint/transcribe', {
    method: 'POST',
    data: { audio_base64: audioBase64, audio_name: audioName },
  })

// 上传到云存储并返回临时 https 链接（云调用 100KB 限制下传文件的正确姿势）
export const uploadFileToCloud = async (filePath: string, dir: string): Promise<string> => {
  const ext = (filePath.split('.').pop() || 'file').slice(0, 8)
  const cloudPath = `${dir}/${Date.now()}_${Math.random().toString(36).slice(2, 8)}.${ext}`
  const up = await Taro.cloud.uploadFile({ cloudPath, filePath })
  const tmp = await Taro.cloud.getTempFileURL({ fileList: [up.fileID] })
  const item = (tmp as any)?.fileList?.[0]
  if (!item?.tempFileURL) throw new Error('获取临时链接失败')
  return item.tempFileURL as string
}

// ---------- 投诉 ----------

export interface ActionStep {
  step: number
  action: string
  detail: string
}

export interface ChannelItem {
  channel: string
  type: string
  reason: string
  legal_basis: string
  priority: number
  action: string
}

export interface ChannelAdvice {
  channels: ChannelItem[]
  summary: string
}

export interface ScriptStep {
  step: number
  title: string
  scenario: string
  script: string
  target: string
  tips: string
}

export interface NegotiationScript {
  steps: ScriptStep[]
}

export interface QualificationItem {
  qualification: string
  how_to_check: string
  importance: string
  red_flag: string
}

export interface MerchantQualificationAdvice {
  merchant_name: string
  items: QualificationItem[]
  summary: string
}

export interface LegalDetail {
  law_name: string
  article: string
  content: string
  source_url: string
}

export interface EvidenceItem {
  file_name: string
  file_url: string
  file_base64?: string
  order_info: Record<string, string>
}

export interface ComplaintDetail extends ActionGuideFields {
  id: number
  raw_text: string
  complaint_letter: string
  legal_basis: string[]
  legal_details?: LegalDetail[]
  action_path: ActionStep[]
  category: string
  status: string
  status_label: string
  order_info?: Record<string, any>
  evidence?: EvidenceItem[]
  created_at: string
  suggestions?: string[]
  channel_advice?: ChannelAdvice
  negotiation_script?: NegotiationScript
  merchant_qualification_advice?: MerchantQualificationAdvice
}

export interface ComplaintListItem {
  id: number
  category: string
  raw_text: string
  status: string
  status_label: string
  created_at: string
}

export interface ComplaintListResp {
  items: ComplaintListItem[]
  total: number
  page: number
  page_size: number
}

export interface ComplaintStats {
  total: number
  categories: number
  in_progress: number
}

export const generateByText = (text: string, order_info?: Record<string, any>, evidence?: EvidenceItem[]) =>
  request<ComplaintDetail>('/api/complaint/text', {
    method: 'POST',
    data: { text, user_id: getUserId(), order_info, evidence },
  })

export const generateByVoice = async (filePath: string, order_info?: Record<string, any>, evidence?: EvidenceItem[]) => {
  try {
    Taro.showLoading({ title: '上传识别中...', mask: true })
    if (useCloud()) {
      const audioBase64 = await readFileBase64(filePath)
      const data = await request<ComplaintDetail>('/api/complaint/voice-json', {
        method: 'POST',
        data: {
          audio_base64: audioBase64,
          audio_name: filePath.split('/').pop() || 'voice.wav',
          user_id: getUserId(),
          order_info: order_info || {},
          evidence: evidence || [],
        },
      })
      return data
    }
    const fullUrl = `${BASE_URL}/api/complaint/voice`
    const uploadRes: any = await Taro.uploadFile({
      url: fullUrl,
      filePath,
      name: 'file',
      timeout: 120000,
      formData: {
        user_id: getUserId(),
        order_info: JSON.stringify(order_info || {}),
        evidence: JSON.stringify(evidence || []),
      },
      header: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    })
    const data: ApiResp<ComplaintDetail> = JSON.parse(uploadRes.data)
    if (data.code === 0) return data.data
    const msg = data.detail || '识别失败'
    Taro.showToast({ title: msg, icon: 'none' })
    throw new Error(msg)
  } catch (e: any) {
    const reason = e?.errMsg || e?.message || String(e)
    console.error('[Voice] 失败:', reason)
    if (e?.errMsg || e?.message) {
      Taro.showToast({ title: friendlyNetworkError(reason), icon: 'none' })
    }
    throw e
  } finally {
    Taro.hideLoading()
  }
}

// ---------- 文件读取（weapp，云调用传 Base64） ----------

function readFileBase64(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (process.env.TARO_ENV === 'h5') {
      reject(new Error('浏览器预览不支持文件上传'))
      return
    }
    try {
      const fs = Taro.getFileSystemManager()
      fs.readFile({ filePath, encoding: 'base64', success: (r) => resolve(r.data as string), fail: reject })
    } catch (e) {
      reject(e)
    }
  })
}

// ---------- 证据 ----------

export interface EvidenceUploadResp {
  items: EvidenceItem[]
}

/** 批量上传证据截图（每张自动 OCR 提取订单信息；云调用走 Base64 JSON） */
export const uploadEvidence = async (filePaths: string[]): Promise<EvidenceItem[]> => {
  if (!filePaths.length) return []
  const items: EvidenceItem[] = []
  Taro.showLoading({ title: `上传证据 1/${filePaths.length}...`, mask: true })
  try {
    if (useCloud()) {
      const files: { name: string; base64: string }[] = []
      for (let i = 0; i < filePaths.length; i++) {
        const base64 = await readFileBase64(filePaths[i])
        files.push({ name: filePaths[i].split('/').pop() || `evidence_${i + 1}.png`, base64 })
      }
      const resp = await request<EvidenceUploadResp>('/api/evidence/upload-json', {
        method: 'POST',
        data: { files, user_id: getUserId() },
      })
      if (resp?.items?.length) items.push(...resp.items)
      return items
    }

    for (let i = 0; i < filePaths.length; i++) {
      const uploadRes: any = await Taro.uploadFile({
        url: `${BASE_URL}/api/evidence/upload`,
        filePath: filePaths[i],
        name: 'files',
        formData: { user_id: getUserId() },
        header: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      })
      const data: ApiResp<EvidenceUploadResp> = JSON.parse(uploadRes.data)
      if (data.code === 0 && data.data?.items?.length) {
        items.push(...data.data.items)
      } else {
        Taro.showToast({ title: data.detail || `第${i + 1}张上传失败`, icon: 'none' })
      }
    }
  } catch (e: any) {
    const reason = e?.errMsg || e?.message || String(e)
    Taro.showToast({ title: friendlyNetworkError(reason), icon: 'none' })
  } finally {
    Taro.hideLoading()
  }
  return items
}

// ---------- 维权指南 ----------

export interface GuideScenario {
  key: string
  title: string
  icon: string
  summary: string
  laws: { law_name: string; article: string }[]
  steps: string[]
  tips: string[]
  channel: string
}

export const getGuideScenarios = () =>
  request<{ scenarios: GuideScenario[] }>('/api/guide/scenarios', { method: 'GET', silent: true })

export interface CommonTemplate {
  key: string
  title: string
  icon: string
  summary: string
  letter: string
  laws: string[]
  channel_name: string
  channel_url: string
  search_key: string
}

export const getCommonTemplates = () =>
  request<{ templates: CommonTemplate[] }>('/api/guide/templates', { method: 'GET', silent: true })

export interface ReferenceCase {
  key: string
  icon: string
  title: string
  summary: string
  scenario: string
  outcome: string
  duration: string
  channel: string
  points: string[]
}

export const getReferenceCases = () =>
  request<{ cases: ReferenceCase[] }>('/api/guide/cases', { method: 'GET', silent: true })

// ---------- 行动清单 / 证据清单 / 决策矩阵 ----------

export interface ActionStepItem {
  step: number
  action: string
  detail: string
  duration: string
}

export interface EvidenceItemCheck {
  item: string
  purpose: string
  how: string
}

export interface EvidenceChecklist {
  key: string
  title: string
  icon: string
  items: EvidenceItemCheck[]
}

export interface DecisionChannel {
  channel: string
  when: string
  duration: string
  cost: string
  next: string
}

export const getEvidenceChecklist = (scenario: string) =>
  request<EvidenceChecklist>(`/api/guide/evidence-checklist?scenario=${scenario}`, { method: 'GET', silent: true })

export const getEvidenceScenarios = () =>
  request<{ scenarios: { key: string; title: string; icon: string }[] }>('/api/guide/evidence-scenarios', { method: 'GET', silent: true })

export const getScenarioDecisions = () =>
  request<{ decisions: Record<string, DecisionChannel[]> }>('/api/guide/scenarios/decision', { method: 'GET', silent: true })

// 生成结果附加字段（后端 _build_response_data 自动挂载）
export interface ActionGuideFields {
  action_checklist?: ActionStepItem[]
  evidence_checklist?: EvidenceChecklist
  path_recommendation?: {
    recommended: string
    reason: string
    backup: string
    upgrade_plan: { step: number; action: string; detail: string }[]
  }
  matched_channels?: {
    name: string
    kind: string
    search: string
    url: string
    phone: string
    reason: string
  }[]
}

// ---------- 法律知识库 ----------

export interface LawItem {
  id: number
  law_name: string
  article: string
  content: string
  tags: string[]
  source_url: string
}

export const getLaws = () => request<{ laws: LawItem[] }>('/api/laws', { method: 'GET', silent: true })

// ---------- 反馈 ----------

export const submitFeedback = (complaint_id: number, rating: string, comment: string = '') =>
  request<{ id: number; rating: string }>('/api/feedback', {
    method: 'POST',
    data: { complaint_id, rating, comment, user_id: getUserId() },
  })

// ---------- 记录 ----------

export const getComplaintList = (page = 1, page_size = 20, status = 'all', opts: ReqOptions = {}) =>
  request<ComplaintListResp>(
    `/api/complaints?user_id=${getUserId()}&page=${page}&page_size=${page_size}&status=${status}`,
    { method: 'GET', silent: true, ...opts }
  )

export const getComplaintDetail = (id: number) =>
  request<ComplaintDetail>(`/api/complaint/${id}`, { method: 'GET' })

export const getComplaintStats = () =>
  request<ComplaintStats>(
    `/api/complaints/stats?user_id=${getUserId()}`,
    { method: 'GET' }
  )

export const updateComplaintStatus = (id: number, status: string) =>
  request<{ id: number; status: string; status_label: string }>(
    `/api/complaint/${id}/status`,
    { method: 'POST', data: { status, user_id: getUserId() } }
  )

export const deleteComplaint = (id: number) =>
  request<{ deleted: boolean }>(`/api/complaint/${id}/delete`, {
    method: 'POST',
    data: { user_id: getUserId() },
  })
