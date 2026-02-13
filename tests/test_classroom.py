"""
测试课堂会话管理
"""

import json
import tempfile
from pathlib import Path

import pytest

from openclass.classroom import ClassroomSession
from openclass.config import AppConfig


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def config(temp_dir):
    cfg = AppConfig()
    cfg.classroom.data_dir = temp_dir
    return cfg


def test_session_creation(config):
    """测试课堂会话创建"""
    session = ClassroomSession(config, "数学分析", "第5讲 极限理论")
    assert session.class_name == "数学分析"
    assert session.root_dir.exists()
    assert session.materials_dir.exists()
    assert session.transcripts_dir.exists()
    assert session.analysis_dir.exists()

    # 检查 meta.json
    meta_path = session.root_dir / "meta.json"
    assert meta_path.exists()
    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["class_name"] == "数学分析"


def test_append_transcript(config):
    """测试追加转录"""
    session = ClassroomSession(config, "测试课堂")
    session.append_transcript({"text": "今天我们来讲极限", "time_ms": 1000, "time": "00:01"})
    session.append_transcript({"text": "极限的定义是这样的", "time_ms": 5000, "time": "00:05"})

    assert len(session.transcript_lines) == 2

    # 检查 JSONL 文件
    jsonl_path = session.transcripts_dir / "realtime.jsonl"
    assert jsonl_path.exists()
    with open(jsonl_path) as f:
        lines = f.readlines()
    assert len(lines) == 2


def test_save_full_transcript(config):
    """测试保存完整转录"""
    session = ClassroomSession(config, "测试课堂")
    session.append_transcript({"text": "第一句话", "time_ms": 0, "time": "00:00"})
    session.append_transcript({"text": "第二句话", "time_ms": 5000, "time": "00:05"})

    path = session.save_full_transcript()
    assert Path(path).exists()


def test_save_question(config):
    """测试保存检测到的问题"""
    session = ClassroomSession(config, "测试课堂")
    session.save_question({
        "question": "什么是极限？",
        "answer": "极限是一种趋近的概念...",
        "type": "direct",
        "confidence": 0.95,
    })

    questions_path = session.analysis_dir / "questions.json"
    assert questions_path.exists()
    with open(questions_path) as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["question"] == "什么是极限？"


def test_get_recent_transcript(config):
    """测试获取最近转录"""
    session = ClassroomSession(config, "测试课堂")
    for i in range(10):
        session.append_transcript({"text": f"第{i}句话", "time_ms": i * 60000})

    recent = session.get_recent_transcript(minutes=5)
    assert "第9句话" in recent


def test_list_sessions(config, temp_dir):
    """测试列出所有会话"""
    ClassroomSession(config, "课堂A")
    ClassroomSession(config, "课堂B")

    sessions = ClassroomSession.list_sessions(temp_dir)
    assert len(sessions) == 2
