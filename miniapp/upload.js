// 言权小程序代码上传脚本（miniprogram-ci）
//
// 用法：
//   1. 在微信公众平台「开发管理 → 开发设置 → 小程序代码上传」下载代码上传密钥
//   2. 将密钥文件放到 miniapp/.auth/private.key（.auth 已被 gitignore）
//   3. 执行：
//      WECHAT_APPID=wx1234567890 \
//      MINIPROGRAM_KEY_PATH=./.auth/private.key \
//      VERSION=1.0.0 \
//      node upload.js
//
// 说明：上传前请先执行 npm run build:weapp 生成最新 dist。

const ci = require('miniprogram-ci')
const path = require('path')

const appid = process.env.WECHAT_APPID || 'wx360e831558773730'
const projectDir = __dirname
const privateKeyPath = process.env.MINIPROGRAM_KEY_PATH
  ? path.resolve(projectDir, process.env.MINIPROGRAM_KEY_PATH)
  : path.join(projectDir, '.auth', 'private.key')
const version = process.env.VERSION || '1.0.0'
const desc = process.env.DESC || '言权 · AI 消费者维权助手'

async function upload() {
  if (!require('fs').existsSync(privateKeyPath)) {
    console.error(`未找到代码上传密钥：${privateKeyPath}`)
    console.error('请在微信公众平台下载密钥后放到 miniapp/.auth/private.key')
    process.exit(1)
  }

  const project = new ci.Project({
    appid,
    type: 'miniProgram',
    projectPath: path.join(projectDir, 'dist'),
    privateKeyPath,
    ignores: ['node_modules/**/*'],
  })

  console.log(`正在上传版本 ${version} ...`)
  const result = await ci.upload({
    project,
    version,
    desc,
    setting: { es6: false, minify: false },
    onProgressUpdate: (u) => {
      if (typeof u === 'object' && u.message) console.log(u.message)
    },
  })
  console.log('上传成功！请在微信公众平台「版本管理」中提交审核。')
  console.log(JSON.stringify(result, null, 2))
}

upload().catch((e) => {
  console.error('上传失败：', e)
  process.exit(1)
})
