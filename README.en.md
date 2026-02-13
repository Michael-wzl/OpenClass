++ FileMode: 100644
```markdown
# 🎓 OpenClass - AI Classroom Assistant

An extremely helpful AI student: listens to lectures, detects teacher questions, suggests answers, and helps you engage more in class.

---

## ✨ Key Features

| Feature | Description |
|--------:|------------|
| 🎙️ Real-time audio monitoring | Uses Alibaba Tingwu for live audio capture and transcription |
| ⚡ Question detection & auto-answers | Detects teacher questions and generates suggested answers in real time |
| 🙋 Smart question suggestions | Suggests high-quality questions you can ask to gain interaction points |
| 📊 Periodic summaries | Configurable summaries (e.g., every 10 minutes) of key points |
| 💡 Creative ideas & learning tips | Offers ideas and deeper learning suggestions based on lecture content |
| 📁 Material management | Support for PPT/PDF/Word inputs to improve context understanding |
| 🌐 Multilingual support | Auto-detects languages and supports configurable output language |
| 🔌 Extensible messaging platforms | Hooks for WhatsApp/QQ/X were reserved for future integration |

## Architecture

```
┌──────────────────────────────────────────────────┐
│                    TUI / CLI                      │
│              (Textual terminal UI)                │
├──────────────────────────────────────────────────┤
│                 OpenClass Engine                  │
│            (core orchestrator - lifecycle)        │
├──────────┬──────────┬────────────┬───────────────┤
│ Audio    │ Speech   │  AI        │ Platform      │
│ Capture  │ (Tingwu) │  Engine    │  Manager      │
│ PyAudio  │ WebSocket│ QWen/GPT   │ Console       │
│ multi-dev│ stream   │ Q detection│ WhatsApp (ext)|
├──────────┴──────────┴────────────┴───────────────┤
│              Event Bus (pub/sub)                 │
├──────────────────────────────────────────────────┤
│   Classroom Session      │  Material Parser     │
└──────────────────────────────────────────────────┘
```

## Quick start

1) Prepare environment

```bash
git clone <your-repo-url>
cd OpenClass
python -m venv venv
source venv/bin/activate
pip install -e .

# On macOS you may need to install portaudio for PyAudio
brew install portaudio
pip install pyaudio
```

2) Configuration

```bash
cp .env.example .env
# edit .env and fill in your API keys
```

Required environment variables:
- `ALI_ACCESS_KEY_ID` / `ALI_ACCESS_KEY_SECRET` (or backward-compatible `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`)
- `TINGWU_APP_KEY` (Tingwu AppKey)
- `DASHSCOPE_API_KEY` (QWen / DashScope API Key)

3) Run

```bash
# Terminal UI (recommended)
openclass start

# Headless listen mode
openclass listen "Lecture #5" -m slides.pptx -m reference.pdf -l cn

# List audio devices
openclass devices

# List past sessions
openclass sessions

# Parse materials
openclass parse lecture.pptx
```

## TUI

When starting the TUI:
1. Enter class name (e.g., "Advanced Math")
2. Optionally add material file paths (comma separated)
3. Select output language
4. Click Start or press `S`

Shortcuts:
- `S`: Start
- `E`: End
- `I`: Generate creative ideas
- `P`: Pause/Resume
- `Q`: Quit

When a teacher question is detected, the right panel highlights the alert and produces a sound:

```
⚡⚡⚡ Question detected! ⚡⚡⚡
  ❓ Q: What is the geometric meaning of this theorem?
  ✅ A: The geometric meaning is ...
  📋 type: direct | confidence: 95%
```

## Data layout

Each class session creates a directory under `classroom_data/`:

```
classroom_data/
└── 2026-02-09_AdvancedMath/
    ├── meta.json
    ├── materials/
    ├── transcripts/
    │   ├── realtime.jsonl
    │   └── full_transcript.txt
    ├── analysis/
    │   ├── questions.json
    │   ├── summaries.json
    │   ├── suggestions.json
    │   └── ideas.json
    └── audio/
```

## Advanced configuration

Switch LLM provider via `openclass.yaml`:

```yaml
llm:
  provider: openai
  openai_model: gpt-4o
```

Custom LLM:

```yaml
llm:
  provider: custom
  custom_base_url: http://localhost:11434/v1
  custom_model: llama3
  custom_api_key: key
```

Multilingual mode (Tingwu):

```yaml
tingwu:
  source_language: multilingual
  enable_translation: true
  translation_target_languages: [cn, en]
```

Message platforms are extensible — implement `openclass.platforms.MessagePlatform` to add new integrations.

## Tech stack

| Component | Technology |
|-----------|-----------:|
| Speech recognition | Alibaba Tingwu (WebSocket) |
| LLMs | QWen / OpenAI / Custom |
| Audio capture | PyAudio (multi-device) |
| Terminal UI | Textual + Rich |
| Async | asyncio + aiohttp |
| Config | Pydantic Settings + YAML |
| CLI | Click |

## Requirements

- Python >= 3.10
- macOS / Linux / Windows
- Microphone or soundcard input
- Alibaba cloud account (Tingwu + DashScope)

## License

MIT

```
