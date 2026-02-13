++ FileMode: 100644
````markdown
# 🎓 OpenClass - AI 智能课堂助手

<p align="center">
  <strong>一个极其优秀的 AI 学生，帮你听课、抢答、互动拿高分</strong>
</p>

---

## ✨ 核心功能

| 功能 | 描述 |
|------|------|
| 🎙️ **实时语音监控** | 基于阿里通义听悟，实时采集和转录课堂语音 |
| ⚡ **提问检测 & 自动答案** | 第一时间检测老师提问，瞬间生成答案提醒你 |
| 🙋 **智能提问建议** | 在合适时机建议你提出高质量问题，赢得课堂互动分 |
| 📊 **定时课堂总结** | 可配置间隔（如每10分钟）自动总结课堂重点内容 |
| 💡 **创意想法 & 学习建议** | 基于课堂内容提出创新想法和深入学习方向 |
| 📁 **课堂材料管理** | 支持导入 PPT/PDF/Word 等材料，增强 AI 理解上下文 |
| 🌐 **多语言支持** | 自动检测中文、英文等语言，输出语言可选 |
| 🔌 **可扩展消息平台** | 预留 WhatsApp/QQ/X 等社交媒体接口 |

## 🏗️ 架构设计

```
┌──────────────────────────────────────────────────┐
│                    TUI / CLI                      │
│              (Textual 终端界面)                    │
├──────────────────────────────────────────────────┤
│                 OpenClass Engine                  │
│            (核心引擎 - 生命周期管理)               │
├──────────┬──────────┬────────────┬───────────────┤
│ 🎙️ Audio │ 🗣️ Speech│  🤖 AI     │ 📨 Platform   │
│ Capture  │ (Tingwu) │  Engine    │  Manager      │
│          │          │            │               │
│ PyAudio  │ WebSocket│ QWen/GPT   │ Console       │
│ 多声卡   │ 实时推流  │ 问题检测   │ WhatsApp(预留)│
│ PCM采集  │ 实时转写  │ 答案生成   │ QQ(预留)      │
│          │          │ 内容总结   │ X(预留)       │
│          │          │ 创意建议   │               │
├──────────┴──────────┴────────────┴───────────────┤
│              📋 Event Bus (事件总线)              │
│           发布-订阅模式 · 模块解耦通信             │
├──────────────────────────────────────────────────┤
│   📂 Classroom Session    │  📄 Material Parser  │
│   课堂目录管理 · 数据持久化 │  PPT/PDF/Word 解析   │
└──────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <your-repo-url>
cd OpenClass

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -e .

# macOS 安装 pyaudio 可能需要先安装 portaudio
brew install portaudio
pip install pyaudio
```

### 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的 API 密钥
```

**必需配置：**
- `ALI_ACCESS_KEY_ID` / `ALI_ACCESS_KEY_SECRET` - [阿里云 AccessKey](https://ram.console.aliyun.com/manage/ak)
- (向后兼容：同样支持 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`)
- `TINGWU_APP_KEY` - [通义听悟 AppKey](https://tingwu.console.aliyun.com/)
- `DASHSCOPE_API_KEY` - [通义千问 API Key](https://dashscope.console.aliyuncs.com/)

### 3. 启动

```bash
# 🎨 TUI 交互式界面（推荐）
openclass start

# 🎧 命令行直接监听模式
openclass listen "高等数学第5讲" -m slides.pptx -m reference.pdf -l cn

# 🎤 查看可用音频设备
openclass devices

# 📋 查看历史课堂
openclass sessions

# 📄 解析材料文件
openclass parse lecture.pptx
```

## 📖 使用指南

### TUI 界面

启动 TUI 后：

1. **填写课堂名称**（如"高等数学"）
2. **可选：添加材料文件路径**（PPT/PDF/Word，逗号分隔）
3. **选择输出语言**
4. **点击"开始上课"按钮**或按 `S` 键

**快捷键：**
- `S` - 开始上课
- `E` - 结束课堂
- `I` - 手动生成创意想法
- `P` - 暂停/继续
- `Q` - 退出

### 关键事件

当 AI 检测到老师提问时，会在右侧面板**高亮显示**并**发出提示音**：

```
⚡⚡⚡ 检测到老师提问! ⚡⚡⚡
  ❓ 问题: 这个定理的几何意义是什么？
  ✅ 答案: 这个定理的几何意义在于...
  📋 类型: direct | 置信度: 95%
```

### 音频设备选择

```bash
# 列出所有音频设备
openclass devices

# 在配置文件中指定设备
# openclass.yaml
audio:
  device_index: 2  # 使用设备 [2]
```

## 📂 课堂数据目录

每次课堂会自动创建独立目录：

```
classroom_data/
└── 2026-02-09_高等数学/
    ├── meta.json               # 课堂元信息
    ├── materials/              # 输入材料
    │   ├── lecture_slides.pptx
    │   └── reference.pdf
    ├── transcripts/            # 转录文本
    │   ├── realtime.jsonl      # 实时转录（JSONL）
    │   └── full_transcript.txt # 完整文本
    ├── analysis/               # AI 分析结果
    │   ├── questions.json      # 问题与答案
    │   ├── summaries.json      # 课堂总结
    │   ├── suggestions.json    # 建议提问
    │   └── ideas.json          # 创意想法
    └── audio/                  # 原始音频
```

## 🔧 高级配置

### 大模型切换

```yaml
# openclass.yaml
llm:
  provider: openai          # 切换到 OpenAI
  openai_model: gpt-4o
```

```yaml
llm:
  provider: custom          # 使用自定义 API
  custom_base_url: http://localhost:11434/v1
  custom_model: llama3
  custom_api_key: ollama
```

### 多语言模式

```yaml
tingwu:
  source_language: multilingual  # 多语种自动识别
  enable_translation: true
  translation_target_languages:
    - cn
    - en
```

### 消息平台扩展

项目预留了社交媒体平台接口，未来可直接集成：

```python
from openclass.platforms import MessagePlatform

class TelegramPlatform(MessagePlatform):
    platform_name = "telegram"
    
    async def send_message(self, message: str, **kwargs):
        # 实现 Telegram Bot API
        ...
```

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 语音识别 | 阿里通义听悟 (WebSocket 实时推流) |
| 大模型 | 通义千问 QWen / OpenAI / 自定义 |
| 音频采集 | PyAudio (支持多声卡) |
| 终端界面 | Textual + Rich |
| 异步框架 | asyncio + aiohttp |
| 配置管理 | Pydantic Settings + YAML |
| CLI | Click |

## 📋 环境要求

- Python >= 3.10
- macOS / Linux / Windows
- 麦克风或声卡输入设备
- 阿里云账号（通义听悟 + DashScope）

## 📄 License

MIT License

````
