# -*- coding: utf-8 -*-
"""Qwen3-ASR 本地可视化服务：模型常驻 GPU，提供 HTTP API + 内置页面。

启动后浏览器访问 http://127.0.0.1:8321
"""
import os
import re
import json
import time
import uuid
import shutil
import html
import tempfile
import threading
import subprocess
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    """定位 ffmpeg：PATH → imageio-ffmpeg 自带 → 本机已知路径"""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    for cand in (r"D:/Hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe",):
        if os.path.exists(cand):
            return cand
    raise RuntimeError("未找到 ffmpeg，请安装或 pip install imageio-ffmpeg")


FFMPEG = find_ffmpeg()
MODEL_DIR = os.path.join(BASE, "models", "Qwen3-ASR-1.7B")
HIST_PATH = os.path.join(BASE, "history.json")
PORT = 8321

from qwen_asr import Qwen3ASRModel

import torch
if not os.path.isdir(MODEL_DIR):
    raise SystemExit(
        "[server] 未找到模型目录 models/Qwen3-ASR-1.7B，"
        "请先运行 install.bat 或 download-model.bat 下载模型（约 4.7GB）"
    )
DEV = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"[server] loading model on {DEV} ...", flush=True)
model = Qwen3ASRModel.from_pretrained(
    MODEL_DIR,
    torch_dtype="bfloat16" if DEV.startswith("cuda") else "float32",
    device_map=DEV,
)
print("[server] model ready", flush=True)

LANG = None  # None = 自动识别
TRANS_LOCK = threading.Lock()


def load_history():
    try:
        with open(HIST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(items):
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def render_page():
    with open(os.path.join(BASE, "app", "index.html"), encoding="utf-8") as f:
        return f.read()


TTS_URL = "http://127.0.0.1:9880"
TTS_UP = False
TTS_LOCK = threading.Lock()


def tts_health():
    global TTS_UP
    while True:
        try:
            with urllib.request.urlopen(TTS_URL + "/docs", timeout=3) as r:
                TTS_UP = (r.status == 200)
        except Exception:
            TTS_UP = False
        time.sleep(5)


threading.Thread(target=tts_health, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", render_page().encode("utf-8"))
        elif p == "/api/health":
            self._json(200, {"ok": True, "model": "Qwen3-ASR-1.7B", "lang": LANG})
        elif p == "/api/tts_health":
            self._json(200, {"ok": TTS_UP, "url": TTS_URL})
        elif p == "/api/tts":
            self._tts()
        elif p == "/api/history":
            self._json(200, {"items": load_history()})
        else:
            self._send(404, "text/plain", b"not found")

    def do_DELETE(self):
        if urlparse(self.path).path == "/api/history":
            save_history([])
            self._json(200, {"ok": True})
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        global LANG
        p = urlparse(self.path).path
        if p == "/api/lang":
            length = int(self.headers.get("Content-Length", 0))
            lang = self.rfile.read(length).decode("utf-8")
            LANG = None if (not lang or lang == "auto") else lang
            self._json(200, {"ok": True, "lang": LANG})
        elif p == "/api/transcribe":
            self._transcribe()
        elif p == "/api/tts":
            self._tts()
        else:
            self._send(404, "text/plain", b"not found")

    def _transcribe(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        # 解析 multipart：取 boundary，切出带 filename 的 part
        ct = self.headers.get("Content-Type", "")
        mb = re.search(r'boundary=([^;]+)', ct)
        if not mb:
            self._json(400, {"error": "请求格式错误"})
            return
        boundary = mb.group(1).encode()
        file_part, fname = None, "audio"
        for part in raw.split(b"--" + boundary):
            if b'filename="' in part:
                file_part = part
                break
        if file_part is None:
            self._json(400, {"error": "没有收到音频文件"})
            return
        head, _, content = file_part.partition(b"\r\n\r\n")
        content = content.rsplit(b"\r\n", 1)[0]
        fm = re.search(rb'filename="([^"]*)"', head)
        if fm:
            fname = fm.group(1).decode("utf-8", "replace") or fname
        # 热词 context 走 URL 查询参数
        qs = urlparse(self.path).query
        ctx = ""
        mq = re.search(r"(?:^|&)context=([^&]*)", qs)
        if mq:
            from urllib.parse import unquote_plus
            ctx = unquote_plus(mq.group(1))
        ext = os.path.splitext(fname)[1] or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(content)
        tmp.close()
        up = tmp.name
        wav = up + ".16k.wav"
        try:
            r = subprocess.run(
                [FFMPEG, "-y", "-i", up, "-ar", "16000", "-ac", "1", wav],
                capture_output=True, timeout=3600,
            )
            if r.returncode != 0:
                self._json(500, {"error": "ffmpeg 转码失败，可能不是音频文件"})
                return
            t0 = time.time()
            with TRANS_LOCK:
                results = model.transcribe(wav, context=ctx, language=LANG)
            el = round(time.time() - t0, 2)
            first = results[0]
            text = getattr(first, "text", None) or str(first)
            lang = getattr(first, "language", "") or ""
            item = {
                "id": uuid.uuid4().hex[:8],
                "name": fname,
                "text": text,
                "lang": lang,
                "seconds": el,
                "time": time.strftime("%Y-%m-%d %H:%M"),
            }
            items = load_history()
            items.insert(0, item)
            save_history(items[:200])
            self._json(200, item)
        except Exception as e:
            self._json(500, {"error": str(e)})
        finally:
            for f in (up, wav):
                try:
                    os.remove(f)
                except OSError:
                    pass



    def _tts(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        ct = self.headers.get("Content-Type", "")
        mb = re.search(r"boundary=([^;]+)", ct)
        if not mb:
            self._json(400, {"error": "请求格式错误"})
            return
        boundary = mb.group(1).encode()
        fields, file_bytes, file_name = {}, None, "ref.wav"
        for part in raw.split(b"--" + boundary):
            if b'filename="' in part:
                head, _, content = part.partition(b"\r\n\r\n")
                content = content.rsplit(b"\r\n", 1)[0]
                file_bytes = content
                fm = re.search(rb'filename="([^"]*)"', head)
                if fm:
                    file_name = fm.group(1).decode("utf-8", "replace") or file_name
            elif b'name="' in part:
                head, _, content = part.partition(b"\r\n\r\n")
                content = content.rsplit(b"\r\n", 1)[0]
                nm = re.search(rb'name="([^"]*)"', head)
                if nm:
                    fields[nm.group(1).decode()] = content.decode("utf-8", "replace")
        text = fields.get("text", "").strip()
        prompt_text = fields.get("prompt_text", "").strip()
        text_lang = fields.get("text_lang", "zh")
        prompt_lang = fields.get("prompt_lang", "zh")
        if not text:
            self._json(400, {"error": "没有要合成的文本"})
            return
        if not file_bytes:
            self._json(400, {"error": "没有收到参考音频"})
            return
        if not TTS_UP:
            self._json(503, {"error": "克隆服务未启动。请先双击 app\\克隆语音服务.bat，等窗口显示 Uvicorn running 后重试"})
            return
        # 存参考音频
        ref_dir = os.path.join(BASE, "refs")
        os.makedirs(ref_dir, exist_ok=True)
        ref_path = os.path.join(ref_dir, "ref_" + uuid.uuid4().hex[:6] + "_" + re.sub(r'[^\w.]', '_', file_name))
        with open(ref_path, "wb") as f:
            f.write(file_bytes)
        # 转码 32k 单声道（GPT-SoVITS 参考音频要求 3~10 秒）
        ref32 = ref_path + ".32k.wav"
        r = subprocess.run([FFMPEG, "-y", "-i", ref_path, "-t", "10", "-ar", "32000", "-ac", "1", ref32],
                           capture_output=True, timeout=120)
        if r.returncode != 0:
            self._json(400, {"error": "参考音频无法解码，请换 mp3/wav/m4a 格式"})
            return
        # 代理请求
        import urllib.parse
        payload = json.dumps({
            "text": text, "text_lang": text_lang,
            "ref_audio_path": ref32.replace("\\", "/"),
            "prompt_text": prompt_text, "prompt_lang": prompt_lang,
            "media_type": "wav", "streaming_mode": False,
        }).encode("utf-8")
        req = urllib.request.Request(TTS_URL + "/tts", data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with TTS_LOCK:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    audio = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            self._json(500, {"error": "合成失败: " + detail})
            return
        except Exception as e:
            self._json(500, {"error": "合成失败: " + str(e)[:200]})
            return
        finally:
            for f in (ref_path, ref32):
                try: os.remove(f)
                except OSError: pass
        if len(audio) < 1000:
            self._json(500, {"error": "合成结果为空，请检查参考音频时长（3~10秒）与提示文本是否匹配"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[server] http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
