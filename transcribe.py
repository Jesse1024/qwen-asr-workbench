# -*- coding: utf-8 -*-
"""Qwen3-ASR-1.7B 本地转写测试"""
import sys, time
from qwen_asr import Qwen3ASRModel

MODEL_DIR = r"E:/qwen3-asr/models/Qwen3-ASR-1.7B"

t0 = time.time()
model = Qwen3ASRModel.from_pretrained(MODEL_DIR, torch_dtype="bfloat16", device_map="cuda:0")
print(f"[load] {time.time()-t0:.1f}s", flush=True)

audios = sys.argv[1:] if len(sys.argv) > 1 else [r"E:/qwen3-asr/test_audio_16k.wav"]
for audio in audios:
    print(f"===== {audio}", flush=True)
    t0 = time.time()
    results = model.transcribe(audio)
    el = time.time() - t0
    print(f"[transcribe] {el:.2f}s", flush=True)

    for r in results:
        text = getattr(r, "text", None)
        if text is None:
            text = str(r)
        print("识别结果:", text)
        # 打印对象其他可用字段（时间戳等）
        extra = [a for a in dir(r) if not a.startswith("_") and a != "text"]
        for a in extra:
            try:
                v = getattr(r, a)
                if not callable(v):
                    print(f"  {a}: {v}")
            except Exception:
                pass
