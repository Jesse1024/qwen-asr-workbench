# -*- coding: utf-8 -*-
"""生成 ASR 工作台图标 + 桌面快捷方式"""
from PIL import Image, ImageDraw, ImageFont
import subprocess, os

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ACCENT = (47, 111, 237, 255)      # 与页面主色一致
FG = (255, 255, 255, 255)


def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=ACCENT)
    if size >= 40:
        # 大尺寸：声波纹样（几何图形，无斜线文字糊字问题）
        cx = size / 2
        heights = [0.22, 0.40, 0.58, 0.40, 0.22]
        w = max(2, size // 18)
        gap = size * 0.055
        total = len(heights) * w + (len(heights) - 1) * gap
        x = cx - total / 2
        for h in heights:
            bh = size * h
            d.rounded_rectangle(
                [x, (size - bh) / 2, x + w, (size + bh) / 2],
                radius=w / 2, fill=FG,
            )
            x += w + gap
    else:
        # 小尺寸：极简麦克风胶囊（无文字）
        w = max(2, size // 5)
        bh = size * 0.45
        d.rounded_rectangle(
            [(size - w) / 2, size * 0.18, (size + w) / 2, size * 0.18 + bh],
            radius=w / 2, fill=FG,
        )
        aw = max(2, size // 16)
        d.arc([size * 0.26, size * 0.42, size * 0.74, size * 0.82],
              start=0, end=180, fill=FG, width=aw)
    return img


out = r"E:\qwen3-asr\app"
imgs = [make_icon(s) for s in SIZES]
imgs[-1].save(os.path.join(out, "icon.ico"),
              format="ICO", sizes=[(s, s) for s in SIZES], append_images=imgs[:-1])
print("icon saved")

# 快捷方式（UTF-16LE base64 防中文乱码）
ps = r'''
$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath('Desktop')
$lnk = $ws.CreateShortcut("$desk\语音转写工作台.lnk")
$lnk.TargetPath = 'E:\qwen3-asr\app\工作台.bat'
$lnk.WorkingDirectory = 'E:\qwen3-asr\app'
$lnk.IconLocation = 'E:\qwen3-asr\app\icon.ico'
$lnk.Description = 'Qwen3-ASR 本地语音转写'
$lnk.Save()
Write-Output "lnk saved: $desk\语音转写工作台.lnk"
'''
import base64
enc = base64.b64encode(ps.encode("utf-16-le")).decode()
r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc],
                   capture_output=True, text=True)
print(r.stdout, r.stderr)
