# -*- coding: utf-8 -*-
import asyncio
import os
from pathlib import Path

try:
    from shazamio import Shazam
except ImportError:
    print("错误: 未安装 shazamio 库")
    print("请运行: pip install shazamio")
    exit(1)

AUDIO_FILE = Path(__file__).parent / "test.ogg"


async def recognize_song(audio_path: Path):
    if not audio_path.exists():
        print(f"错误: 音频文件不存在: {audio_path}")
        return

    print(f"正在识别音频文件: {audio_path}")
    print(f"文件大小: {audio_path.stat().st_size} bytes")

    shazam = Shazam()

    try:
        out = await shazam.recognize(audio_path.as_posix())
    except Exception as e:
        print(f"识别过程中发生错误: {e}")
        return

    if not out:
        print("未识别到歌曲")
        return

    track = out.get("track")
    if not track:
        print("未识别到歌曲信息")
        print(f"完整响应: {out}")
        return

    title = track.get("title", "未知")
    subtitle = track.get("subtitle", "未知")

    print("\n" + "=" * 50)
    print("识别结果:")
    print("=" * 50)
    print(f"歌曲名: {title}")
    print(f"艺术家: {subtitle}")

    if "images" in track:
        images = track["images"]
        if "coverart" in images:
            print(f"封面: {images['coverart']}")

    if "share" in track:
        share = track["share"]
        if "href" in share:
            print(f"链接: {share['href']}")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(recognize_song(AUDIO_FILE))
