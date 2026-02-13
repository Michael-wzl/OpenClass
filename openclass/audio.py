"""
OpenClass 音频采集模块
支持多声卡选择，实时采集 PCM 音频流
"""

from __future__ import annotations

import asyncio
import logging
import struct
import threading
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


def list_audio_devices() -> list[dict]:
    """
    列出所有可用的音频输入设备
    返回: [{"index": 0, "name": "Built-in Microphone", "channels": 1, "sample_rate": 44100}, ...]
    """
    try:
        import pyaudio
    except ImportError:
        logger.error("pyaudio 未安装，请执行: pip install pyaudio")
        return []

    pa = pyaudio.PyAudio()
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            devices.append({
                "index": i,
                "name": info["name"],
                "channels": int(info["maxInputChannels"]),
                "sample_rate": int(info["defaultSampleRate"]),
                "host_api": pa.get_host_api_info_by_index(info["hostApi"])["name"],
            })
    pa.terminate()
    return devices


class AudioCapture:
    """
    音频采集器
    从指定声卡实时采集 PCM 音频数据
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 3200,
        format_bits: int = 16,
    ):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.format_bits = format_bits

        self._running = False
        self._pa = None
        self._stream = None
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        self._capture_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """开始音频采集"""
        if self._running:
            logger.warning("音频采集已在运行中")
            return

        self._loop = loop or asyncio.get_event_loop()
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        logger.info(f"音频采集已启动 (device={self.device_index}, rate={self.sample_rate})")

    def stop(self) -> None:
        """停止音频采集"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=3)
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._pa:
            self._pa.terminate()
        self._stream = None
        self._pa = None
        logger.info("音频采集已停止")

    def _capture_loop(self) -> None:
        """音频采集线程（阻塞IO，运行在独立线程）"""
        try:
            import pyaudio

            self._pa = pyaudio.PyAudio()

            format_map = {8: pyaudio.paInt8, 16: pyaudio.paInt16, 32: pyaudio.paInt32}
            pa_format = format_map.get(self.format_bits, pyaudio.paInt16)

            kwargs = {
                "format": pa_format,
                "channels": self.channels,
                "rate": self.sample_rate,
                "input": True,
                "frames_per_buffer": self.chunk_size // (self.format_bits // 8),
            }
            if self.device_index is not None:
                kwargs["input_device_index"] = self.device_index

            self._stream = self._pa.open(**kwargs)
            logger.info("PyAudio 流已打开")

            while self._running:
                try:
                    data = self._stream.read(
                        self.chunk_size // (self.format_bits // 8),
                        exception_on_overflow=False,
                    )
                    if self._loop and self._loop.is_running():
                        self._loop.call_soon_threadsafe(self._enqueue, data)
                except IOError as e:
                    logger.warning(f"音频读取异常: {e}")
                    continue
        except Exception as e:
            logger.error(f"音频采集线程异常: {e}", exc_info=True)
        finally:
            self._running = False

    def _enqueue(self, data: bytes) -> None:
        """将音频数据放入异步队列"""
        try:
            self._audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            # 丢弃最旧的数据
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._audio_queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def read_audio(self) -> AsyncIterator[bytes]:
        """异步读取音频数据流"""
        while self._running or not self._audio_queue.empty():
            try:
                data = await asyncio.wait_for(self._audio_queue.get(), timeout=1.0)
                yield data
            except asyncio.TimeoutError:
                continue

    @property
    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def compute_rms(audio_data: bytes) -> float:
        """计算音频 RMS 值（用于检测静音）"""
        if len(audio_data) < 2:
            return 0.0
        count = len(audio_data) // 2
        shorts = struct.unpack(f"<{count}h", audio_data[:count * 2])
        rms = (sum(s * s for s in shorts) / count) ** 0.5
        return rms
