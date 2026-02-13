"""
OpenClass 核心引擎
协调所有模块，管理课堂生命周期
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from openclass.ai_engine import AIEngine
from openclass.audio import AudioCapture
from openclass.classroom import ClassroomSession
from openclass.config import AppConfig
from openclass.events import Event, EventBus, EventType, event_bus
from openclass.materials import MaterialParser
from openclass.platforms import ConsolePlatform, PlatformManager
from openclass.speech import TingwuClient

logger = logging.getLogger(__name__)


class OpenClassEngine:
    """
    OpenClass 核心引擎
    管理课堂全生命周期：初始化 -> 采集音频 -> 推流识别 -> AI分析 -> 输出结果
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.event_bus: EventBus = event_bus

        # 子模块
        self.audio_capture: Optional[AudioCapture] = None
        self.tingwu_client: Optional[TingwuClient] = None
        self.ai_engine: Optional[AIEngine] = None
        self.platform_manager: Optional[PlatformManager] = None
        self.session: Optional[ClassroomSession] = None

        # 状态
        self._running = False
        self._audio_task: Optional[asyncio.Task] = None

        # 注册事件处理
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """注册全局事件处理"""
        self.event_bus.subscribe(EventType.TRANSCRIPTION_SENTENCE_END, self._on_transcript)
        self.event_bus.subscribe(EventType.QUESTION_DETECTED, self._on_question_detected)
        self.event_bus.subscribe(EventType.ANSWER_GENERATED, self._on_answer_generated)
        self.event_bus.subscribe(EventType.SUGGEST_QUESTION, self._on_suggest_question)
        self.event_bus.subscribe(EventType.PERIODIC_SUMMARY, self._on_periodic_summary)
        self.event_bus.subscribe(EventType.CREATIVE_IDEAS, self._on_creative_ideas)
        self.event_bus.subscribe(EventType.TRANSCRIPTION_ERROR, self._on_transcription_error)

    async def initialize(
        self,
        class_name: str,
        description: str = "",
        materials: list[str] | None = None,
        audio_device_index: int | None = None,
    ) -> None:
        """
        初始化课堂会话
        
        Args:
            class_name: 课堂名称
            description: 课堂描述
            materials: 课堂材料文件路径列表
            audio_device_index: 音频设备索引（None=系统默认）
        """
        logger.info(f"正在初始化课堂: {class_name}")

        # 1. 创建课堂会话
        self.session = ClassroomSession(self.config, class_name, description)

        # 2. 加载课堂材料
        if materials:
            material_text = ""
            for m in materials:
                self.session.add_material(m)
                text = MaterialParser.parse(m)
                if text:
                    material_text += f"\n\n=== {m} ===\n{text}"
            if material_text:
                # 传递给 AI 引擎
                pass  # 在 start 时设置

        # 3. 初始化音频采集
        device = audio_device_index if audio_device_index is not None else self.config.audio.device_index
        self.audio_capture = AudioCapture(
            device_index=device,
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            chunk_size=self.config.audio.chunk_size,
            format_bits=self.config.audio.format_bits,
        )

        # 4. 初始化通义听悟客户端
        self.tingwu_client = TingwuClient(self.config.tingwu, self.event_bus)

        # 5. 初始化 AI 引擎
        self.ai_engine = AIEngine(self.config, self.event_bus)
        if materials:
            all_text = MaterialParser.parse_multiple(materials)
            self.ai_engine.set_material_context(all_text)

        # 6. 初始化消息平台
        self.platform_manager = PlatformManager(self.event_bus)
        console = ConsolePlatform(self.event_bus)
        self.platform_manager.register(console)

        logger.info("课堂初始化完成")

    async def start(self) -> None:
        """开始上课"""
        if not self.session:
            raise RuntimeError("请先调用 initialize() 初始化课堂")

        self._running = True
        self.session.is_active = True

        # 启动消息平台
        await self.platform_manager.start_all()

        # 创建通义听悟任务
        try:
            task_data = await self.tingwu_client.create_task_with_sdk()
            self.session.task_id = task_data.get("TaskId")
            self.session.meeting_join_url = task_data.get("MeetingJoinUrl")
            logger.info(f"听悟任务已创建: {self.session.task_id}")
        except Exception as e:
            logger.error(f"创建听悟任务失败: {e}")
            await self.platform_manager.broadcast_alert(
                "错误", f"创建语音识别任务失败: {e}", "error"
            )
            raise

        # 连接 WebSocket 开始接收结果
        await self.tingwu_client.start_streaming()

        # 启动音频采集
        loop = asyncio.get_event_loop()
        self.audio_capture.start(loop)

        # 启动音频推流任务
        self._audio_task = asyncio.create_task(self._audio_stream_loop())

        # 启动 AI 引擎
        await self.ai_engine.start()

        await self.event_bus.publish(Event(
            type=EventType.CLASS_STARTED,
            data={"class_name": self.session.class_name, "session_id": self.session.session_id},
            source="engine",
        ))

        await self.platform_manager.broadcast_alert(
            "课堂已开始",
            f"📚 {self.session.class_name}\n🎙️ 正在监听课堂语音...\n⏱️ 每{self.config.classroom.summary_interval_minutes}分钟自动总结",
            "info",
        )

    async def _audio_stream_loop(self) -> None:
        """音频采集和推流循环"""
        try:
            async for audio_data in self.audio_capture.read_audio():
                if not self._running:
                    break
                await self.tingwu_client.send_audio(audio_data)
        except Exception as e:
            logger.error(f"音频推流异常: {e}", exc_info=True)

    async def stop(self) -> None:
        """结束课堂"""
        self._running = False

        # 停止音频采集
        if self.audio_capture:
            self.audio_capture.stop()

        # 停止音频推流任务
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass

        # 停止 WebSocket 推流
        if self.tingwu_client:
            await self.tingwu_client.stop_streaming()

        # 停止 AI 引擎
        if self.ai_engine:
            await self.ai_engine.stop()

        # 结束听悟任务
        if self.tingwu_client and self.tingwu_client.task_id:
            try:
                result = await self.tingwu_client.stop_realtime_task()
                logger.info(f"听悟任务已结束: {result}")
            except Exception as e:
                logger.error(f"结束听悟任务失败: {e}")

        # 保存转录文本
        if self.session:
            self.session.save_full_transcript()
            self.session.is_active = False

        # 生成最终创意想法
        if self.ai_engine and self.config.classroom.enable_creative_ideas:
            try:
                await self.ai_engine.generate_creative_ideas()
            except Exception as e:
                logger.error(f"生成创意想法失败: {e}")

        await self.event_bus.publish(Event(
            type=EventType.CLASS_ENDED,
            data={"session_id": self.session.session_id if self.session else ""},
            source="engine",
        ))

        await self.platform_manager.broadcast_alert(
            "课堂已结束",
            f"📊 课堂数据已保存到: {self.session.root_dir if self.session else 'N/A'}",
            "info",
        )

        # 停止消息平台
        if self.platform_manager:
            await self.platform_manager.stop_all()

    # ==================== 事件处理器 ====================

    async def _on_transcript(self, event: Event) -> None:
        """处理转录结果"""
        text = event.data.get("text", "")
        speaker = event.data.get("speaker_id", "")
        time_ms = event.data.get("time_ms", 0)

        if self.session:
            self.session.append_transcript({
                "text": text,
                "speaker": speaker,
                "time_ms": time_ms,
                "time": self._format_time(time_ms),
                "timestamp": datetime.now().isoformat(),
            })

    async def _on_question_detected(self, event: Event) -> None:
        """处理检测到的问题"""
        if not self.platform_manager:
            return

        question = event.data.get("question", "")
        answer = event.data.get("answer", "")
        q_type = event.data.get("question_type", "")
        confidence = event.data.get("confidence", 0)

        alert_content = (
            f"🎯 问题: {question}\n"
            f"💡 答案: {answer}\n"
            f"📋 类型: {q_type} | 置信度: {confidence:.0%}"
        )
        await self.platform_manager.broadcast_alert("⚡ 检测到老师提问!", alert_content, "question")

        if self.session:
            self.session.save_question({
                "question": question,
                "answer": answer,
                "type": q_type,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
            })

    async def _on_answer_generated(self, event: Event) -> None:
        """处理生成的答案"""
        pass  # 答案已在 question_detected 中输出

    async def _on_suggest_question(self, event: Event) -> None:
        """处理建议提问"""
        if not self.platform_manager:
            return

        suggestion = event.data.get("suggestion", {})
        question = suggestion.get("question", "")
        rationale = suggestion.get("rationale", "")
        timing = suggestion.get("timing", "")

        alert_content = (
            f"❓ 建议提问: {question}\n"
            f"💭 原因: {rationale}\n"
            f"⏰ 时机: {timing}"
        )
        await self.platform_manager.broadcast_alert("🙋 建议提出问题", alert_content, "idea")

        if self.session:
            self.session.save_suggestion({
                "suggestion": suggestion,
                "timestamp": datetime.now().isoformat(),
            })

    async def _on_periodic_summary(self, event: Event) -> None:
        """处理定时总结"""
        if not self.platform_manager:
            return

        summary = event.data.get("summary", {})
        minutes = event.data.get("minutes", 10)

        title_text = summary.get("title", "课堂内容")
        key_points = summary.get("key_points", [])
        important_concepts = summary.get("important_concepts", [])
        summary_text = summary.get("summary", "")

        points_str = "\n".join(f"  • {p}" for p in key_points)
        concepts_str = ", ".join(important_concepts) if important_concepts else "无"

        alert_content = (
            f"📖 主题: {title_text}\n"
            f"📌 要点:\n{points_str}\n"
            f"🔑 重要概念: {concepts_str}\n"
            f"📝 总结: {summary_text}"
        )
        await self.platform_manager.broadcast_alert(
            f"📊 最近{minutes}分钟课堂总结",
            alert_content,
            "summary",
        )

        if self.session:
            self.session.save_summary({
                "summary": summary,
                "minutes": minutes,
                "timestamp": datetime.now().isoformat(),
            })

    async def _on_creative_ideas(self, event: Event) -> None:
        """处理创意想法"""
        if not self.platform_manager:
            return

        ideas = event.data.get("ideas", {})
        creative = ideas.get("creative_ideas", [])
        deep = ideas.get("deep_learning", [])

        creative_str = "\n".join(f"  💡 {i.get('idea', '')}" for i in creative)
        deep_str = "\n".join(f"  📚 {d.get('topic', '')}: {d.get('reason', '')}" for d in deep)

        alert_content = f"✨ 创意想法:\n{creative_str}\n\n📖 深入学习方向:\n{deep_str}"
        await self.platform_manager.broadcast_alert("🧠 创意想法与学习建议", alert_content, "idea")

        if self.session:
            self.session.save_idea({
                "ideas": ideas,
                "timestamp": datetime.now().isoformat(),
            })

    async def _on_transcription_error(self, event: Event) -> None:
        """处理转录错误"""
        error = event.data.get("error", str(event.data))
        logger.error(f"转录错误: {error}")
        if self.platform_manager:
            await self.platform_manager.broadcast_alert("转录错误", str(error), "error")

    @staticmethod
    def _format_time(ms: int) -> str:
        """将毫秒格式化为 HH:MM:SS"""
        seconds = ms // 1000
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
