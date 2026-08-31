"""语音识别服务（DashScope ASR；演示模式直接提示使用文字输入）"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from ..config import settings


class _ASRCallback(RecognitionCallback):
    """简单的 ASR 回调，收集识别结果"""

    def __init__(self):
        super().__init__()
        self.sentences = []
        self.error = None

    def on_event(self, result) -> None:
        sentence = result.get_sentence()
        if sentence:
            self.sentences.extend(sentence if isinstance(sentence, list) else [sentence])

    def on_error(self, result) -> None:
        self.error = result.message


def _convert_to_wav(input_path: str) -> str:
    """
    将音频文件转换为标准 WAV 格式（16kHz, mono, 16bit PCM）

    iOS 录制的 M4A/AAC 格式不被 DashScope ASR 直接支持，需要先转换。
    优先使用 afconvert（macOS 内置），fallback 到 ffmpeg。
    """
    output_path = tempfile.mktemp(suffix=".wav")
    src_ext = Path(input_path).suffix.lower().lstrip(".")
    af_err = None

    # 尝试 afconvert（macOS 内置）
    try:
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", "-c", "1", input_path, output_path],
            check=True, capture_output=True, timeout=30,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return _fix_wav_header(output_path)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        af_err = e
        logger.warning("afconvert 转换失败：%s", e)

    # fallback: 尝试 ffmpeg（支持 PATH 与 conda 等常见安装位置）
    ffmpeg = shutil.which("ffmpeg") or "/opt/anaconda3/envs/rag_env/bin/ffmpeg"
    if not os.path.exists(ffmpeg):
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    try:
        if os.path.exists(ffmpeg):
            subprocess.run(
                [ffmpeg, "-y", "-i", input_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_path],
                check=True, capture_output=True, timeout=60,
            )
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("ffmpeg 转换失败：%s", e)

    err = "未知原因"
    if isinstance(af_err, subprocess.CalledProcessError) and af_err.stderr:
        err = af_err.stderr.decode("utf-8", errors="ignore")[:200]
    raise RuntimeError(f"无法转换音频格式（{src_ext}→wav）：{err}")


def _fix_wav_header(wav_path: str) -> str:
    """
    修复 afconvert 产生的 WAVE_FORMAT_EXTENSIBLE 头为标准 PCM WAV 头

    macOS 的 afconvert 默认输出 WAVE_FORMAT_EXTENSIBLE (format tag 65534)，
    而 DashScope ASR 只认标准 PCM (format tag 1)。
    """
    import struct

    with open(wav_path, "rb") as f:
        data = bytearray(f.read())

    pos = 12
    if data[pos:pos + 4] != b"fmt ":
        return wav_path

    old_fmt_size = struct.unpack_from("<I", data, pos + 4)[0]
    if old_fmt_size == 16:
        return wav_path

    struct.pack_into("<H", data, pos + 8, 1)   # format_tag = PCM
    struct.pack_into("<I", data, pos + 4, 16)  # fmt chunk size = 16

    fmt_end = pos + 8 + old_fmt_size
    new_fmt_end = pos + 8 + 16
    del data[new_fmt_end:fmt_end]

    new_file_size = len(data) - 8
    struct.pack_into("<I", data, 4, new_file_size)

    with open(wav_path, "wb") as f:
        f.write(data)
    return wav_path


def _detect_container(path: str) -> str:
    """按文件头检测真实音频容器（模拟器录音的扩展名不可信，内容可能是 WebM）"""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return "unknown"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head[:4] == b"OggS":
        return "ogg"
    return "unknown"


def transcribe_audio(audio_path: str) -> str:
    """
    将音频文件转写为文字

    Args:
        audio_path: 音频文件路径

    Returns:
        转写后的文本

    Raises:
        FileNotFoundError: 音频文件不存在
        ValueError: 不支持的音频格式 / 演示模式
        RuntimeError: 语音识别失败
    """
    if settings.demo_mode:
        raise ValueError("当前为演示模式（未配置语音识别服务），请使用文字输入")

    dashscope.api_key = settings.dashscope_api_key

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    ext = Path(audio_path).suffix.lower().lstrip(".")
    real_fmt = _detect_container(audio_path)
    logger.info("收到语音文件：%s（扩展名=%s，实际格式=%s，大小=%s）", audio_path, ext, real_fmt, os.path.getsize(audio_path))
    # mp3 直接透传（阿里云 paraformer 支持 mp3，无需本地转码）
    # m4a/aac 等使用 afconvert（macOS 内置）或 ffmpeg 转成 wav
    # 按真实容器决定：wav/mp3 透传；其余（m4a/aac/webm/ogg 等）转成 wav
    if real_fmt in ("wav", "mp3"):
        asr_path = audio_path
        asr_format = real_fmt
    elif real_fmt in ("m4a", "aac"):
        # 真机 m4a：afconvert 可处理；失败自动走 ffmpeg
        asr_path = _convert_to_wav(audio_path)
        asr_format = "wav"
    else:
        # webm/ogg/opus/flac/aiff 及未知格式：优先 ffmpeg，afconvert 兜底
        asr_path = _convert_to_wav(audio_path)
        asr_format = "wav"

    callback = _ASRCallback()
    recognition = Recognition(
        model=settings.asr_model,
        callback=callback,
        format=asr_format,
        sample_rate=16000,
    )

    result = recognition.call(file=asr_path)

    if asr_path != audio_path and asr_path.endswith('.wav'):
        try:
            os.remove(asr_path)
        except OSError:
            pass

    if result.status_code != 200:
        error_msg = callback.error or result.message or "未知错误"
        raise RuntimeError(f"语音识别失败: {error_msg}")

    output = result.output
    if output and "sentence" in output:
        sentences = output["sentence"]
        if sentences:
            return "".join(s.get("text", "") for s in sentences).strip()

    if callback.sentences:
        return "".join(s.get("text", "") for s in callback.sentences).strip()

    return ""
