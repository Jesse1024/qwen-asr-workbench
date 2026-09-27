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


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[server] http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()
