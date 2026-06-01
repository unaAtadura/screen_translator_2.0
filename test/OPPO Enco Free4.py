import pyaudiowpatch as pyaudio
import wave

RECORD_SECONDS = 5
OUTPUT_FILENAME = "recorded_system_audio.wav"
CHUNK = 1024

with pyaudio.PyAudio() as p:
    try:
        # 1. 获取默认的 WASAPI 环回设备
        wasapi_loopback = p.get_default_wasapi_loopback()
        # 2. 从设备信息中读取其支持的默认采样率和最大声道数
        SAMPLE_RATE = int(wasapi_loopback["defaultSampleRate"])
        CHANNELS = wasapi_loopback["maxInputChannels"]

        print(f"录音设备: {wasapi_loopback['name']}")
        print(f"   -> 默认采样率: {SAMPLE_RATE} Hz")
        print(f"   -> 最大声道数: {CHANNELS}")

    except OSError as e:
        print("未找到 WASAPI 环回设备，请确保在 Windows 系统上运行。")
        raise e

    # 3. 打开流：参数全部动态获取，不再写死
    with p.open(format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=wasapi_loopback['index']) as stream:
        print(f"开始录音 ({RECORD_SECONDS} 秒)...")

        frames = []
        # 计算总读取次数，确保采样率变化时仍能录制准确时长
        total_frames_to_read = int(SAMPLE_RATE / CHUNK * RECORD_SECONDS)
        for _ in range(total_frames_to_read):
            data = stream.read(CHUNK)
            frames.append(data)

        print("录音结束，正在保存...")
        with wave.open(OUTPUT_FILENAME, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))

        print(f"文件已保存为: {OUTPUT_FILENAME}")