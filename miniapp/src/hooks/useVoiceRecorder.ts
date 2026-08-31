import { useEffect, useRef, useState } from 'react'
import Taro from '@tarojs/taro'

export interface VoiceRecorder {
  isRecording: boolean
  seconds: number
  supported: boolean
  start: () => Promise<void>
  stop: () => void
  reset: () => void
}

/**
 * 录音管理器是全局单例，若每个页面都注册一次回调，
 * 重新打开页面后会叠加多个监听导致状态错乱、录音异常。
 * 这里只在模块加载时注册一次，页面通过 hook 订阅状态。
 */

let rm: any = null
let listeners = new Set<() => void>()
let isRecording = false
let seconds = 0
let supported = true
let recordingLock = false // 正在录音
let busyLock = false      // 刚停止/出错，短暂防抖
let cancelRequested = false
let timer: any = null

function emit() {
  listeners.forEach((fn) => fn())
}

function clearTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function initRecorder() {
  try {
    if (rm) return
    rm = Taro.getRecorderManager()
    if (!rm) {
      supported = false
      return
    }

    rm.onStart(() => {
    recordingLock = true
    cancelRequested = false
    isRecording = true
    seconds = 0
    clearTimer()
    timer = setInterval(() => {
      seconds += 1
      emit()
    }, 1000)
    emit()
  })

  rm.onStop((res: any) => {
    recordingLock = false
    cancelRequested = false
    isRecording = false
    clearTimer()
    busyLock = true
    setTimeout(() => { busyLock = false }, 500)
    emit()
    if (!res?.tempFilePath) {
      Taro.showToast({ title: '录音失败，请重试', icon: 'none' })
      return
    }
    if (seconds < 1) {
      Taro.showToast({ title: '录音时间太短', icon: 'none' })
      return
    }
    // 派发给当前订阅页面
    onStopHandlers.forEach((fn) => { try { fn(res.tempFilePath) } catch (e) { /* ignore */ } })
  })

  rm.onError((err: any) => {
    recordingLock = false
    cancelRequested = false
    isRecording = false
    clearTimer()
    busyLock = true
    setTimeout(() => { busyLock = false }, 500)
    emit()
    const reason = (err && (err.errMsg || err.message)) || ''
    Taro.showToast({ title: reason ? `录音出错：${String(reason).slice(0, 30)}` : '录音出错，请重试', icon: 'none', duration: 3000 })
    console.warn('[Voice] 录音出错', err)
    })
  } catch (e) {
    console.warn('[Voice] 初始化录音管理器失败', e)
    supported = false
  }
}

let onStopHandlers = new Set<(filePath: string) => void>()

export function useVoiceRecorder(onStop: (filePath: string) => void): VoiceRecorder {
  const [state, setState] = useState({ isRecording, seconds })

  // 订阅模块级状态
  useEffect(() => {
    const fn = () => setState({ isRecording, seconds })
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])

  // 订阅录音完成回调；由各页面的回调自行判断自己是否当前页
  useEffect(() => {
    onStopHandlers.add(onStop)
    return () => {
      onStopHandlers.delete(onStop)
    }
  }, [onStop])

  const start = async () => {
    if (recordingLock || busyLock) return

    if (!supported) {
      Taro.showModal({
        title: '浏览器预览',
        content: '语音功能仅支持微信小程序内使用，浏览器预览请使用文字输入。',
        confirmText: '知道了',
        showCancel: false,
      })
      return
    }

    cancelRequested = false
    try {
      await Taro.authorize({ scope: 'scope.record' })
    } catch {
      Taro.showModal({
        title: '需要麦克风权限',
        content: '请在设置中允许「言权」使用麦克风，才能语音维权',
        confirmText: '去设置',
        success: (res) => {
          if (res.confirm) Taro.openSetting()
        },
      })
      return
    }

    if (cancelRequested) return

    try {
      rm?.start({
        duration: 300000, // 最长 5 分钟长语音
        sampleRate: 16000,
        numberOfChannels: 1,
        encodeBitRate: 48000,
        format: 'mp3',
        frameSize: 50,
      })
    } catch (e: any) {
      Taro.showToast({ title: `录音启动失败：${String(e?.errMsg || e?.message || '').slice(0, 30)}`, icon: 'none', duration: 3000 })
      console.warn('[Voice] 启动录音失败', e)
    }
  }

  const stop = () => {
    cancelRequested = true
    if (recordingLock && rm) {
      rm.stop()
    }
  }

  // 页面重新显示/重新打开时复位卡死状态（例如被切后台导致 onStop 未触发）
  const reset = () => {
    if (recordingLock && rm) {
      try { rm.stop() } catch (e) { /* ignore */ }
    }
    recordingLock = false
    cancelRequested = false
    isRecording = false
    busyLock = false
    clearTimer()
    emit()
  }

  return { isRecording: state.isRecording, seconds: state.seconds, supported, start, stop, reset }
}

initRecorder()
