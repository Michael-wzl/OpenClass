"""
OpenClass TUI (Terminal User Interface)
基于 Textual 的终端用户界面
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, Log, RichLog, Static, Button, Input, Select

from openclass.audio import list_audio_devices
from openclass.config import AppConfig
from openclass.engine import OpenClassEngine
from openclass.events import Event, EventBus, EventType, event_bus

logger = logging.getLogger(__name__)


class TranscriptPanel(RichLog):
    """实时转录面板"""

    DEFAULT_CSS = """
    TranscriptPanel {
        border: solid green;
        height: 1fr;
        min-height: 10;
    }
    """

    def on_mount(self) -> None:
        self.border_title = "📝 实时转录"


class AlertPanel(RichLog):
    """AI 告警/提醒面板"""

    DEFAULT_CSS = """
    AlertPanel {
        border: solid yellow;
        height: 1fr;
        min-height: 10;
    }
    """

    def on_mount(self) -> None:
        self.border_title = "🤖 AI 助手"


class StatusBar(Static):
    """状态栏"""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    status_text = reactive("就绪")

    def render(self) -> str:
        return f" 状态: {self.status_text}"


class OpenClassTUI(App):
    """OpenClass 终端用户界面"""

    TITLE = "🎓 OpenClass - AI 智能课堂助手"

    CSS = """
    Screen {
        layout: vertical;
    }
    
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    
    #left-panel {
        width: 60%;
    }
    
    #right-panel {
        width: 40%;
    }
    
    #setup-container {
        layout: vertical;
        padding: 2;
        height: auto;
    }
    
    .setup-row {
        layout: horizontal;
        height: 3;
        margin: 0 0 1 0;
    }
    
    .setup-label {
        width: 20;
        padding: 1 1 0 0;
    }
    
    .setup-input {
        width: 1fr;
    }
    
    #btn-container {
        layout: horizontal;
        height: 3;
        margin: 1 0;
    }
    
    #btn-container Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
        Binding("s", "start_class", "开始上课", show=True),
        Binding("e", "end_class", "结束课堂", show=True),
        Binding("i", "creative_ideas", "创意想法", show=True),
        Binding("p", "pause_resume", "暂停/继续", show=True),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.engine: Optional[OpenClassEngine] = None
        self._is_class_active = False
        self._transcript_panel: Optional[TranscriptPanel] = None
        self._alert_panel: Optional[AlertPanel] = None
        self._status_bar: Optional[StatusBar] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="setup-container"):
            with Horizontal(classes="setup-row"):
                yield Label("课堂名称:", classes="setup-label")
                yield Input(placeholder="例如: 高等数学 第5讲", id="class-name", classes="setup-input")
            with Horizontal(classes="setup-row"):
                yield Label("材料文件:", classes="setup-label")
                yield Input(placeholder="可选，多个文件用逗号分隔", id="materials", classes="setup-input")
            with Horizontal(classes="setup-row"):
                yield Label("输出语言:", classes="setup-label")
                yield Select(
                    [("中文", "cn"), ("English", "en"), ("日本語", "ja"), ("한국어", "ko")],
                    value="cn",
                    id="output-lang",
                    classes="setup-input",
                )
            with Horizontal(id="btn-container"):
                yield Button("🎙️ 开始上课", id="btn-start", variant="success")
                yield Button("⏹️ 结束课堂", id="btn-stop", variant="error", disabled=True)
                yield Button("💡 创意想法", id="btn-ideas", variant="primary", disabled=True)
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield TranscriptPanel(id="transcript", wrap=True, highlight=True, markup=True)
            with Vertical(id="right-panel"):
                yield AlertPanel(id="alerts", wrap=True, highlight=True, markup=True)
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        self._transcript_panel = self.query_one("#transcript", TranscriptPanel)
        self._alert_panel = self.query_one("#alerts", AlertPanel)
        self._status_bar = self.query_one(StatusBar)

        # 注册 AI 事件处理
        self._register_event_handlers()

        # 显示音频设备列表
        self._show_audio_devices()

    def _show_audio_devices(self) -> None:
        """显示可用音频设备"""
        devices = list_audio_devices()
        if devices:
            self._alert_panel.write(Text("🎤 可用音频输入设备:", style="bold cyan"))
            for d in devices:
                self._alert_panel.write(
                    Text(f"  [{d['index']}] {d['name']} ({d['sample_rate']}Hz, {d['channels']}ch)", style="dim")
                )
            self._alert_panel.write(Text(f"\n当前使用: {'系统默认' if self.config.audio.device_index is None else f'设备 {self.config.audio.device_index}'}", style="green"))
        else:
            self._alert_panel.write(Text("⚠️ 未检测到音频输入设备 (需要安装 pyaudio)", style="yellow"))
        self._alert_panel.write(Text(""))

    def _register_event_handlers(self) -> None:
        """注册事件处理器到事件总线"""
        event_bus.subscribe(EventType.TRANSCRIPTION_SENTENCE_END, self._handle_transcript)
        event_bus.subscribe(EventType.TRANSCRIPTION_PARTIAL, self._handle_partial)
        event_bus.subscribe(EventType.QUESTION_DETECTED, self._handle_question)
        event_bus.subscribe(EventType.ANSWER_GENERATED, self._handle_answer)
        event_bus.subscribe(EventType.SUGGEST_QUESTION, self._handle_suggestion)
        event_bus.subscribe(EventType.PERIODIC_SUMMARY, self._handle_summary)
        event_bus.subscribe(EventType.CREATIVE_IDEAS, self._handle_ideas)
        event_bus.subscribe(EventType.TRANSCRIPTION_ERROR, self._handle_error)

    async def _handle_transcript(self, event: Event) -> None:
        """显示转录结果"""
        text = event.data.get("text", "")
        speaker = event.data.get("speaker_id", "")
        time_ms = event.data.get("time_ms", 0)

        time_str = OpenClassEngine._format_time(time_ms)
        prefix = f"[dim][{time_str}][/dim]"
        if speaker:
            prefix += f" [bold]{speaker}:[/bold]"
        self.call_from_thread(self._transcript_panel.write, Text.from_markup(f"{prefix} {text}"))

    async def _handle_partial(self, event: Event) -> None:
        """显示中间结果（可选）"""
        pass  # 中间结果更新太快，只显示完整句子

    async def _handle_question(self, event: Event) -> None:
        """显示检测到的问题"""
        question = event.data.get("question", "")
        answer = event.data.get("answer", "")
        q_type = event.data.get("question_type", "")
        confidence = event.data.get("confidence", 0)

        self.call_from_thread(self._alert_panel.write, Text(""))
        self.call_from_thread(
            self._alert_panel.write,
            Text("⚡⚡⚡ 检测到老师提问! ⚡⚡⚡", style="bold red on yellow"),
        )
        self.call_from_thread(self._alert_panel.write, Text(f"  ❓ 问题: {question}", style="bold white"))
        self.call_from_thread(self._alert_panel.write, Text(f"  ✅ 答案: {answer}", style="bold green"))
        self.call_from_thread(
            self._alert_panel.write,
            Text(f"  📋 类型: {q_type} | 置信度: {confidence:.0%}", style="dim"),
        )
        self.call_from_thread(self._alert_panel.write, Text(""))
        self.bell()  # 发出提示音

    async def _handle_answer(self, event: Event) -> None:
        pass

    async def _handle_suggestion(self, event: Event) -> None:
        """显示建议提问"""
        suggestion = event.data.get("suggestion", {})
        question = suggestion.get("question", "")
        rationale = suggestion.get("rationale", "")

        self.call_from_thread(self._alert_panel.write, Text(""))
        self.call_from_thread(
            self._alert_panel.write,
            Text("🙋 建议你向老师提问:", style="bold cyan"),
        )
        self.call_from_thread(self._alert_panel.write, Text(f"  ❓ {question}", style="bold white"))
        self.call_from_thread(self._alert_panel.write, Text(f"  💭 {rationale}", style="dim"))
        self.call_from_thread(self._alert_panel.write, Text(""))

    async def _handle_summary(self, event: Event) -> None:
        """显示定时总结"""
        summary = event.data.get("summary", {})
        minutes = event.data.get("minutes", 10)

        self.call_from_thread(self._alert_panel.write, Text(""))
        self.call_from_thread(
            self._alert_panel.write,
            Text(f"📊 最近{minutes}分钟课堂总结", style="bold magenta"),
        )
        self.call_from_thread(
            self._alert_panel.write,
            Text(f"  📖 主题: {summary.get('title', '')}", style="bold"),
        )
        for point in summary.get("key_points", []):
            self.call_from_thread(self._alert_panel.write, Text(f"  • {point}", style="white"))
        summary_text = summary.get("summary", "")
        if summary_text:
            self.call_from_thread(self._alert_panel.write, Text(f"  📝 {summary_text}", style="green"))
        self.call_from_thread(self._alert_panel.write, Text(""))

    async def _handle_ideas(self, event: Event) -> None:
        """显示创意想法"""
        ideas = event.data.get("ideas", {})

        self.call_from_thread(self._alert_panel.write, Text(""))
        self.call_from_thread(
            self._alert_panel.write,
            Text("🧠 创意想法与学习建议", style="bold yellow"),
        )
        for idea in ideas.get("creative_ideas", []):
            self.call_from_thread(self._alert_panel.write, Text(f"  💡 {idea.get('idea', '')}", style="white"))
        for deep in ideas.get("deep_learning", []):
            self.call_from_thread(
                self._alert_panel.write,
                Text(f"  📚 {deep.get('topic', '')}: {deep.get('reason', '')}", style="cyan"),
            )
        self.call_from_thread(self._alert_panel.write, Text(""))

    async def _handle_error(self, event: Event) -> None:
        """显示错误"""
        error = event.data.get("error", str(event.data))
        self.call_from_thread(self._alert_panel.write, Text(f"❌ 错误: {error}", style="bold red"))

    @on(Button.Pressed, "#btn-start")
    @work(thread=False)
    async def on_start_pressed(self) -> None:
        """开始上课按钮"""
        await self.action_start_class()

    @on(Button.Pressed, "#btn-stop")
    @work(thread=False)
    async def on_stop_pressed(self) -> None:
        """结束课堂按钮"""
        await self.action_end_class()

    @on(Button.Pressed, "#btn-ideas")
    @work(thread=False)
    async def on_ideas_pressed(self) -> None:
        """创意想法按钮"""
        await self.action_creative_ideas()

    async def action_start_class(self) -> None:
        """开始上课"""
        if self._is_class_active:
            return

        class_name = self.query_one("#class-name", Input).value.strip()
        if not class_name:
            class_name = f"课堂_{datetime.now().strftime('%H%M')}"

        materials_str = self.query_one("#materials", Input).value.strip()
        materials = [m.strip() for m in materials_str.split(",") if m.strip()] if materials_str else None

        output_lang = self.query_one("#output-lang", Select).value
        self.config.classroom.output_language = output_lang

        self._status_bar.status_text = "正在初始化..."
        self._alert_panel.write(Text(f"🚀 正在启动课堂: {class_name}...", style="bold green"))

        try:
            self.engine = OpenClassEngine(self.config)
            await self.engine.initialize(
                class_name=class_name,
                materials=materials,
            )
            await self.engine.start()

            self._is_class_active = True
            self._status_bar.status_text = f"🔴 录制中 - {class_name}"
            self.query_one("#btn-start", Button).disabled = True
            self.query_one("#btn-stop", Button).disabled = False
            self.query_one("#btn-ideas", Button).disabled = False

        except Exception as e:
            self._alert_panel.write(Text(f"❌ 启动失败: {e}", style="bold red"))
            self._status_bar.status_text = "启动失败"
            logger.error(f"启动课堂失败: {e}", exc_info=True)

    async def action_end_class(self) -> None:
        """结束课堂"""
        if not self._is_class_active or not self.engine:
            return

        self._status_bar.status_text = "正在结束课堂..."
        self._alert_panel.write(Text("⏹️ 正在结束课堂...", style="bold yellow"))

        try:
            await self.engine.stop()
            self._is_class_active = False
            self._status_bar.status_text = "课堂已结束"
            self.query_one("#btn-start", Button).disabled = False
            self.query_one("#btn-stop", Button).disabled = True
            self.query_one("#btn-ideas", Button).disabled = True
        except Exception as e:
            self._alert_panel.write(Text(f"❌ 结束失败: {e}", style="bold red"))

    async def action_creative_ideas(self) -> None:
        """手动触发生成创意想法"""
        if self.engine and self.engine.ai_engine:
            self._alert_panel.write(Text("🧠 正在生成创意想法...", style="dim"))
            await self.engine.ai_engine.generate_creative_ideas()

    async def action_pause_resume(self) -> None:
        """暂停/继续"""
        pass  # TODO: 实现暂停和继续


def run_tui(config: AppConfig) -> None:
    """启动 TUI 界面"""
    app = OpenClassTUI(config)
    app.run()
