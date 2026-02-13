"""
OpenClass 课堂管理模块
管理课堂会话、目录结构、材料文件
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from openclass.config import AppConfig

logger = logging.getLogger(__name__)


class ClassroomSession:
    """
    课堂会话管理
    每次课堂创建独立目录，管理输入材料和输出结果
    
    目录结构:
    classroom_data/
    ├── 2026-02-09_数学分析/
    │   ├── meta.json               # 课堂元信息
    │   ├── materials/              # 输入材料
    │   │   ├── lecture_slides.pptx
    │   │   └── reference.pdf
    │   ├── transcripts/            # 转录文本
    │   │   ├── realtime.jsonl      # 实时转录记录
    │   │   └── full_transcript.txt # 完整转录文本
    │   ├── analysis/               # AI分析结果
    │   │   ├── questions.json      # 检测到的问题与答案
    │   │   ├── summaries.json      # 定时总结
    │   │   ├── suggestions.json    # 建议提问
    │   │   └── ideas.json          # 创意想法
    │   └── audio/                  # 原始音频（可选保存）
    │       └── recording.pcm
    └── ...
    """

    def __init__(self, config: AppConfig, class_name: str, description: str = ""):
        self.config = config
        self.class_name = class_name
        self.description = description
        self.created_at = datetime.now()
        self.session_id = self.created_at.strftime("%Y%m%d_%H%M%S")

        # 创建目录
        dir_name = f"{self.created_at.strftime('%Y-%m-%d')}_{class_name}"
        self.root_dir = Path(config.classroom.data_dir) / dir_name
        self.materials_dir = self.root_dir / "materials"
        self.transcripts_dir = self.root_dir / "transcripts"
        self.analysis_dir = self.root_dir / "analysis"
        self.audio_dir = self.root_dir / "audio"

        self._create_directories()
        self._save_meta()

        # 运行时状态
        self.is_active = False
        self.task_id: Optional[str] = None
        self.meeting_join_url: Optional[str] = None
        self.transcript_lines: list[dict] = []
        self.detected_questions: list[dict] = []
        self.summaries: list[dict] = []
        self.suggestions: list[dict] = []
        self.ideas: list[dict] = []

    def _create_directories(self) -> None:
        """创建课堂目录结构"""
        for d in [self.materials_dir, self.transcripts_dir, self.analysis_dir, self.audio_dir]:
            d.mkdir(parents=True, exist_ok=True)
        logger.info(f"课堂目录已创建: {self.root_dir}")

    def _save_meta(self) -> None:
        """保存课堂元信息"""
        meta = {
            "session_id": self.session_id,
            "class_name": self.class_name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "source_language": self.config.tingwu.source_language,
            "output_language": self.config.classroom.output_language,
            "summary_interval_minutes": self.config.classroom.summary_interval_minutes,
        }
        meta_path = self.root_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def add_material(self, file_path: str) -> str:
        """添加课堂材料文件"""
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"材料文件不存在: {file_path}")

        dst = self.materials_dir / src.name
        shutil.copy2(src, dst)
        logger.info(f"材料已添加: {dst}")
        return str(dst)

    def append_transcript(self, sentence: dict) -> None:
        """追加转录句子"""
        self.transcript_lines.append(sentence)
        # 追加写入 JSONL 文件
        transcript_file = self.transcripts_dir / "realtime.jsonl"
        with open(transcript_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sentence, ensure_ascii=False) + "\n")

    def save_full_transcript(self) -> str:
        """保存完整转录文本"""
        txt_path = self.transcripts_dir / "full_transcript.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for line in self.transcript_lines:
                speaker = line.get("speaker", "")
                text = line.get("text", "")
                time_str = line.get("time", "")
                prefix = f"[{time_str}]" if time_str else ""
                if speaker:
                    prefix += f" {speaker}:"
                f.write(f"{prefix} {text}\n")
        logger.info(f"完整转录已保存: {txt_path}")
        return str(txt_path)

    def save_question(self, question_data: dict) -> None:
        """保存检测到的问题"""
        self.detected_questions.append(question_data)
        self._save_json(self.analysis_dir / "questions.json", self.detected_questions)

    def save_summary(self, summary_data: dict) -> None:
        """保存总结"""
        self.summaries.append(summary_data)
        self._save_json(self.analysis_dir / "summaries.json", self.summaries)

    def save_suggestion(self, suggestion_data: dict) -> None:
        """保存建议提问"""
        self.suggestions.append(suggestion_data)
        self._save_json(self.analysis_dir / "suggestions.json", self.suggestions)

    def save_idea(self, idea_data: dict) -> None:
        """保存创意想法"""
        self.ideas.append(idea_data)
        self._save_json(self.analysis_dir / "ideas.json", self.ideas)

    def _save_json(self, path: Path, data: list) -> None:
        """保存 JSON 数据"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_recent_transcript(self, minutes: int = 10) -> str:
        """获取最近N分钟的转录文本"""
        if not self.transcript_lines:
            return ""
        # 基于时间戳筛选
        cutoff_ms = minutes * 60 * 1000
        last_time = self.transcript_lines[-1].get("time_ms", 0)
        start_time = max(0, last_time - cutoff_ms)

        lines = []
        for line in self.transcript_lines:
            if line.get("time_ms", 0) >= start_time:
                lines.append(line.get("text", ""))
        return "\n".join(lines)

    def get_all_transcript_text(self) -> str:
        """获取所有转录文本"""
        return "\n".join(line.get("text", "") for line in self.transcript_lines)

    @staticmethod
    def list_sessions(data_dir: str) -> list[dict]:
        """列出所有课堂会话"""
        sessions = []
        root = Path(data_dir)
        if not root.exists():
            return sessions
        for d in sorted(root.iterdir()):
            if d.is_dir():
                meta_path = d / "meta.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["path"] = str(d)
                    sessions.append(meta)
        return sessions
