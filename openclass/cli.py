"""
OpenClass CLI 命令行入口
"""

from __future__ import annotations

import asyncio
import logging
import sys

import click

from openclass import __version__


def setup_logging(level: str = "INFO") -> None:
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.version_option(version=__version__)
def main():
    """🎓 OpenClass - AI 智能课堂助手

    实时监控课堂提问、自动生成答案、智能总结课堂内容
    """
    pass


@main.command()
@click.option("--config", "-c", default=None, help="配置文件路径 (YAML)")
@click.option("--debug", is_flag=True, help="调试模式")
def start(config: str | None, debug: bool):
    """🎙️ 启动 OpenClass TUI 界面"""
    from openclass.config import AppConfig
    from openclass.tui import run_tui

    setup_logging("DEBUG" if debug else "INFO")

    app_config = AppConfig.load(config)
    if debug:
        app_config.debug = True

    run_tui(app_config)


@main.command()
@click.option("--config", "-c", default=None, help="配置文件路径")
@click.argument("class_name")
@click.option("--materials", "-m", multiple=True, help="课堂材料文件路径")
@click.option("--device", "-d", type=int, default=None, help="音频设备索引")
@click.option("--language", "-l", default="cn", help="输出语言 (cn/en/ja/ko)")
@click.option("--summary-interval", type=int, default=10, help="总结间隔（分钟）")
@click.option("--debug", is_flag=True, help="调试模式")
def listen(
    config: str | None,
    class_name: str,
    materials: tuple,
    device: int | None,
    language: str,
    summary_interval: int,
    debug: bool,
):
    """🎧 直接启动课堂监听（无TUI模式）

    CLASS_NAME: 课堂名称
    """
    from openclass.config import AppConfig
    from openclass.engine import OpenClassEngine

    setup_logging("DEBUG" if debug else "INFO")

    app_config = AppConfig.load(config)
    app_config.classroom.output_language = language
    app_config.classroom.summary_interval_minutes = summary_interval
    if debug:
        app_config.debug = True

    asyncio.run(_run_listen(app_config, class_name, list(materials), device))


async def _run_listen(config, class_name: str, materials: list[str], device: int | None):
    """运行监听模式"""
    from openclass.engine import OpenClassEngine

    engine = OpenClassEngine(config)
    await engine.initialize(
        class_name=class_name,
        materials=materials or None,
        audio_device_index=device,
    )

    print(f"\n🎓 OpenClass 已启动 - {class_name}")
    print(f"🎙️ 正在监听课堂语音...")
    print(f"⏱️  每{config.classroom.summary_interval_minutes}分钟自动总结")
    print(f"🔤 输出语言: {config.classroom.output_language}")
    print(f"\n按 Ctrl+C 结束课堂\n")

    await engine.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ 正在结束课堂...")
        await engine.stop()
        print("✅ 课堂已结束")


@main.command()
def devices():
    """🎤 列出所有可用的音频输入设备"""
    from openclass.audio import list_audio_devices

    devices = list_audio_devices()
    if not devices:
        click.echo("❌ 未检测到音频输入设备")
        click.echo("💡 提示: 请确保已安装 pyaudio")
        return

    click.echo("\n🎤 可用音频输入设备:\n")
    for d in devices:
        click.echo(
            f"  [{d['index']}] {d['name']}\n"
            f"      采样率: {d['sample_rate']}Hz | 通道数: {d['channels']} | API: {d['host_api']}\n"
        )


@main.command()
@click.option("--data-dir", "-d", default="./classroom_data", help="课堂数据目录")
def sessions(data_dir: str):
    """📋 列出所有历史课堂会话"""
    from openclass.classroom import ClassroomSession

    all_sessions = ClassroomSession.list_sessions(data_dir)
    if not all_sessions:
        click.echo("❌ 暂无课堂记录")
        return

    click.echo("\n📚 历史课堂记录:\n")
    for s in all_sessions:
        click.echo(
            f"  📖 {s.get('class_name', '未知')} ({s.get('created_at', '')})\n"
            f"     路径: {s.get('path', '')}\n"
            f"     语言: {s.get('source_language', '')} -> {s.get('output_language', '')}\n"
        )


@main.command()
@click.argument("file_path")
def parse(file_path: str):
    """📄 解析课堂材料文件"""
    from openclass.materials import MaterialParser

    try:
        text = MaterialParser.parse(file_path)
        click.echo(f"\n📄 文件: {file_path}")
        click.echo(f"📊 字符数: {len(text)}")
        click.echo(f"\n--- 内容预览（前500字）---\n")
        click.echo(text[:500])
        if len(text) > 500:
            click.echo(f"\n... (还有 {len(text) - 500} 字符)")
    except Exception as e:
        click.echo(f"❌ 解析失败: {e}")


if __name__ == "__main__":
    main()
