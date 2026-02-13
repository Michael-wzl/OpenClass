"""
OpenClass AI 分析引擎
核心智能模块：问题检测、答案生成、内容总结、创意建议、智能提问建议
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from openclass.config import AppConfig
from openclass.events import Event, EventBus, EventType
from openclass.llm import BaseLLM, create_llm

logger = logging.getLogger(__name__)

# ==================== Prompt 模板 ====================

SYSTEM_PROMPT_CN = """你是OpenClass智能课堂助手，一个极其优秀的学生。你正在帮助用户实时听课。
你的任务是分析课堂语音转录内容，为用户提供实时帮助。

关键能力：
1. 精准识别老师的提问（包括直接提问、反问、引导性问题）
2. 快速生成高质量答案
3. 建议适当的课堂互动问题
4. 定期总结课堂重点内容
5. 提出创意想法和深入学习方向

回复规范：
- 简洁明了，直击要点
- 答案要准确、完整
- 建议问题要有深度、能展示思考
- 用{output_language}回复"""

SYSTEM_PROMPT_EN = """You are OpenClass AI Classroom Assistant, an exceptionally brilliant student. 
You are helping the user attend a live class in real-time.
Your task is to analyze the real-time class transcript and provide instant help.

Key capabilities:
1. Precisely detect teacher's questions (direct, rhetorical, guiding questions)
2. Quickly generate high-quality answers
3. Suggest appropriate classroom interaction questions
4. Periodically summarize key lecture content
5. Propose creative ideas and deeper learning directions

Response guidelines:
- Concise and to the point
- Answers must be accurate and complete
- Suggested questions should demonstrate depth of thinking
- Reply in {output_language}"""

QUESTION_DETECTION_PROMPT = """分析以下课堂转录文本，判断老师是否在提问。

转录文本（最近内容）：
---
{transcript}
---

请严格按照以下JSON格式回复（不要有其他文字）：
{{
    "is_question": true/false,
    "question_text": "老师的原始提问内容",
    "question_type": "direct/rhetorical/guiding/exercise",
    "answer": "你认为最佳的答案（完整、准确、简洁）",
    "confidence": 0.0-1.0,
    "explanation": "简要解释为什么这是一个问题，以及答案的推理过程"
}}

注意：
- direct: 直接提问，期望学生回答
- rhetorical: 反问/修辞性问题
- guiding: 引导性问题，引导学生思考
- exercise: 练习题/作业相关问题
- confidence: 是提问的置信度
- 只有当确信是老师在提问时才设置 is_question 为 true"""

SUGGEST_QUESTION_PROMPT = """基于以下课堂内容，生成一个有深度的、适合学生在课堂上提出的好问题。
这个问题应该：
1. 展示你对课堂内容的深入理解
2. 引发进一步的思考和讨论
3. 可能获得老师的认可和高分课堂互动评价
4. 与当前讨论主题紧密相关

课堂内容（最近{minutes}分钟）：
---
{transcript}
---

{material_context}

请按以下JSON格式回复（不要有其他文字）：
{{
    "question": "建议提出的问题",
    "rationale": "为什么这是一个好问题",
    "timing": "建议在什么时候提出",
    "expected_impact": "预期会带来什么样的课堂讨论"
}}"""

PERIODIC_SUMMARY_PROMPT = """请总结以下课堂内容的要点。

课堂转录（最近{minutes}分钟）：
---
{transcript}
---

{material_context}

请按以下JSON格式回复（不要有其他文字）：
{{
    "title": "本段课堂主题",
    "key_points": ["要点1", "要点2", ...],
    "important_concepts": ["重要概念1", "重要概念2", ...],
    "teacher_emphasis": ["老师强调的内容1", ...],
    "summary": "一段话概括总结"
}}"""

CREATIVE_IDEAS_PROMPT = """基于以下课堂内容，提出一些创意想法和可以继续深入学习的方向。

课堂内容：
---
{transcript}
---

{material_context}

请按以下JSON格式回复（不要有其他文字）：
{{
    "creative_ideas": [
        {{
            "idea": "创意想法描述",
            "connection": "与课堂内容的联系",
            "potential": "这个想法的潜在价值"
        }}
    ],
    "deep_learning": [
        {{
            "topic": "深入学习主题",
            "reason": "为什么值得深入",
            "resources": "建议的学习资源或方向"
        }}
    ],
    "cross_discipline": [
        {{
            "field": "跨学科领域",
            "connection": "与当前课程的关联"
        }}
    ]
}}"""


class AIEngine:
    """
    AI 分析引擎
    监听语音转录事件，实时进行智能分析
    """

    def __init__(self, config: AppConfig, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.llm: BaseLLM = create_llm(config.llm)

        # 转录缓冲区
        self._transcript_buffer: list[dict] = []
        self._sentence_buffer: list[str] = []  # 完整句子缓存
        self._last_analysis_time: float = 0
        self._last_summary_time: float = 0
        self._last_suggest_time: float = 0
        
        # 去重：记录最近检测过的问题，防止重复分析同一句话
        self._recent_detected_questions: set[str] = set()  # 存储最近检测过的问题文本（用于去重）
        self._last_detected_question: str = ""  # 最近一次检测到的问题

        # 上下文信息
        self._material_text: str = ""  # 课堂材料内容
        self._output_language = config.classroom.output_language
        self._summary_interval = config.classroom.summary_interval_minutes * 60  # 秒
        self._suggest_interval = 300  # 5分钟建议一次提问

        # 分析控制
        self._analysis_lock = asyncio.Lock()
        self._running = False
        self._periodic_task: Optional[asyncio.Task] = None

    def set_material_context(self, text: str) -> None:
        """设置课堂材料上下文"""
        self._material_text = text
        logger.info(f"已加载课堂材料 ({len(text)} 字符)")

    async def start(self) -> None:
        """启动 AI 引擎，注册事件处理器"""
        self._running = True

        # 订阅转录事件
        self.event_bus.subscribe(EventType.TRANSCRIPTION_SENTENCE_END, self._on_sentence_end)
        self.event_bus.subscribe(EventType.TRANSCRIPTION_PARTIAL, self._on_partial_result)

        # 启动定时任务
        self._periodic_task = asyncio.create_task(self._periodic_loop())
        logger.info("AI 分析引擎已启动")

    async def stop(self) -> None:
        """停止 AI 引擎"""
        self._running = False
        if self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
        logger.info("AI 分析引擎已停止")

    async def _on_sentence_end(self, event: Event) -> None:
        """处理完整句子事件"""
        text = event.data.get("text", "")
        if not text.strip():
            return

        sentence = {
            "text": text,
            "time_ms": event.data.get("time_ms", 0),
            "speaker_id": event.data.get("speaker_id", ""),
            "stash_text": event.data.get("stash_text", ""),
            "timestamp": datetime.now().isoformat(),
        }
        self._transcript_buffer.append(sentence)
        self._sentence_buffer.append(text)

        # 检测问题（每收到完整句子就检测）
        if self.config.classroom.enable_question_detection:
            asyncio.create_task(self._detect_question())

    async def _on_partial_result(self, event: Event) -> None:
        """处理中间结果（可用于更即时的检测）"""
        pass  # 当前主要依赖完整句子做分析

    async def _periodic_loop(self) -> None:
        """定时任务循环"""
        while self._running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                now = time.time()

                # 定时总结
                if (self.config.classroom.enable_periodic_summary
                        and now - self._last_summary_time >= self._summary_interval
                        and len(self._sentence_buffer) > 5):
                    asyncio.create_task(self._generate_summary())
                    self._last_summary_time = now

                # 定时建议提问
                if (self.config.classroom.enable_suggest_questions
                        and now - self._last_suggest_time >= self._suggest_interval
                        and len(self._sentence_buffer) > 10):
                    asyncio.create_task(self._suggest_question())
                    self._last_suggest_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时任务异常: {e}", exc_info=True)

    async def _detect_question(self) -> None:
        """检测老师是否在提问"""
        async with self._analysis_lock:
            # 取最近几句做分析
            recent = self._sentence_buffer[-5:] if len(self._sentence_buffer) >= 5 else self._sentence_buffer
            transcript = "\n".join(recent)
            
            # 去重检查：如果转录内容与上次完全相同，跳过（防止听悟多次发送同一句）
            if transcript == getattr(self, '_last_transcript_for_detection', ''):
                return
            self._last_transcript_for_detection = transcript

            system = self._get_system_prompt()
            prompt = QUESTION_DETECTION_PROMPT.format(transcript=transcript)

            try:
                response = await self.llm.chat(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1024,
                )

                result = self._parse_json_response(response)
                if result and result.get("is_question") and result.get("confidence", 0) >= 0.7:
                    question_text = result.get("question_text", "")
                    
                    # 去重：检查是否与最近检测到的问题重复（编辑距离或完全匹配）
                    if question_text and question_text == self._last_detected_question:
                        logger.debug(f"跳过重复问题: {question_text[:50]}...")
                        return
                    
                    self._last_detected_question = question_text
                    
                    await self.event_bus.publish(Event(
                        type=EventType.QUESTION_DETECTED,
                        data={
                            "question": question_text,
                            "question_type": result.get("question_type", ""),
                            "answer": result.get("answer", ""),
                            "confidence": result.get("confidence", 0),
                            "explanation": result.get("explanation", ""),
                        },
                        source="ai_engine",
                    ))

                    await self.event_bus.publish(Event(
                        type=EventType.ANSWER_GENERATED,
                        data={
                            "question": question_text,
                            "answer": result.get("answer", ""),
                            "question_type": result.get("question_type", ""),
                        },
                        source="ai_engine",
                    ))

            except Exception as e:
                logger.error(f"问题检测失败: {e}", exc_info=True)

    async def _generate_summary(self) -> None:
        """生成课堂内容定时总结"""
        minutes = self.config.classroom.summary_interval_minutes
        recent = self._sentence_buffer[-50:]  # 最近50句
        transcript = "\n".join(recent)

        material_ctx = ""
        if self._material_text:
            material_ctx = f"课堂参考材料：\n{self._material_text[:2000]}"

        system = self._get_system_prompt()
        prompt = PERIODIC_SUMMARY_PROMPT.format(
            minutes=minutes,
            transcript=transcript,
            material_context=material_ctx,
        )

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=2048,
            )

            result = self._parse_json_response(response)
            if result:
                await self.event_bus.publish(Event(
                    type=EventType.PERIODIC_SUMMARY,
                    data={
                        "summary": result,
                        "minutes": minutes,
                        "sentence_count": len(recent),
                    },
                    source="ai_engine",
                ))
        except Exception as e:
            logger.error(f"总结生成失败: {e}", exc_info=True)

    async def _suggest_question(self) -> None:
        """生成建议提问"""
        minutes = 5
        recent = self._sentence_buffer[-30:]
        transcript = "\n".join(recent)

        material_ctx = ""
        if self._material_text:
            material_ctx = f"课堂参考材料：\n{self._material_text[:2000]}"

        system = self._get_system_prompt()
        prompt = SUGGEST_QUESTION_PROMPT.format(
            minutes=minutes,
            transcript=transcript,
            material_context=material_ctx,
        )

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=1024,
            )

            result = self._parse_json_response(response)
            if result:
                await self.event_bus.publish(Event(
                    type=EventType.SUGGEST_QUESTION,
                    data={"suggestion": result},
                    source="ai_engine",
                ))
        except Exception as e:
            logger.error(f"建议提问生成失败: {e}", exc_info=True)

    async def generate_creative_ideas(self) -> None:
        """生成创意想法和深入学习建议（可手动触发）"""
        transcript = "\n".join(self._sentence_buffer[-60:])

        material_ctx = ""
        if self._material_text:
            material_ctx = f"课堂参考材料：\n{self._material_text[:2000]}"

        system = self._get_system_prompt()
        prompt = CREATIVE_IDEAS_PROMPT.format(
            transcript=transcript,
            material_context=material_ctx,
        )

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=2048,
            )

            result = self._parse_json_response(response)
            if result:
                await self.event_bus.publish(Event(
                    type=EventType.CREATIVE_IDEAS,
                    data={"ideas": result},
                    source="ai_engine",
                ))
        except Exception as e:
            logger.error(f"创意想法生成失败: {e}", exc_info=True)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        lang = self._output_language
        if lang in ("cn", "zh", "chinese"):
            return SYSTEM_PROMPT_CN.format(output_language="中文")
        elif lang in ("en", "english"):
            return SYSTEM_PROMPT_EN.format(output_language="English")
        else:
            return SYSTEM_PROMPT_CN.format(output_language=lang)

    @staticmethod
    def _parse_json_response(text: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON"""
        import json
        # 清理可能的 markdown 代码块标记
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试查找 JSON 部分
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"无法解析 JSON 响应: {text[:200]}")
            return None
