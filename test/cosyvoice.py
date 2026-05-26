# -*- coding: utf-8 -*-
import os
from dashscope.audio.http_tts.http_speech_synthesizer import HttpSpeechSynthesizer

# 未配置环境变量时，将下行替换为：api_key = "sk-xxx"，即替换为实际的API Key
api_key = ""

# 流式调用，逐段返回音频数据
stream_result = HttpSpeechSynthesizer.call(
    model="cosyvoice-v3-flash",  # 更换模型时，需同步更换为对应版本的音色
    text="Salut, Annie! Comment vas-tu?",
    voice="longanhuan",  # 该音色适用于cosyvoice-v3系列，cosyvoice-v2请使用longxiaochun_v2等v2音色
    format="wav",
    sample_rate=24000,
    stream=True,
    api_key=api_key,
)

# 遍历迭代器，逐段接收音频数据
audio_chunks = []
for chunk in stream_result:
    if not chunk.audio_url and chunk.audio_data:  # 过滤最后一个包含完整音频URL的chunk，避免音频重复
        audio_chunks.append(chunk.audio_data)
        print(f"收到音频数据块，大小: {len(chunk.audio_data)} bytes")

    if chunk.sentences:
        print(f"句子信息: {chunk.sentences}")
    
    if chunk.audio_id:
        print(f"Audio ID: {chunk.audio_id}")
        request_id = chunk.audio_id.removeprefix("audio_")
        print(f"请求 Id: {request_id}")

# 合并所有音频数据并保存
full_audio = b"".join(audio_chunks)
print(f"总音频大小: {len(full_audio)} bytes")

with open("output.wav", "wb") as f:
    f.write(full_audio)
print("音频已保存到 output.wav")