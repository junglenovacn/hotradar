# -*- coding: utf-8 -*-
"""HotRadar OG 分享图生成器（1200x630 PNG，依赖 Pillow）"""
import os
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # noqa: BLE001
    Image = None

import config

W, H = 1200, 630
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def _load_font(size, bold=False):
    if Image is None:
        return None
    paths = (FONT_BOLD_CANDIDATES if bold else []) + config.FONT_CANDIDATES
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:  # noqa: BLE001
        return None


def _wrap(text, font, max_width, draw, max_lines=2):
    """按像素宽度换行（中英文混排）"""
    if not text:
        return [""]
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) > max_width and cur:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
        else:
            cur = trial
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1] + cur[:1], font=font) > max_width:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _top_item(snap):
    best = None
    for src in snap.get("sources", {}).values():
        for it in src.get("items", []):
            if best is None or it.get("score", 0) > best.get("score", 0):
                best = it
    return best


def generate(snap, out_dir, filename=None):
    """生成一张 OG 分享图，返回文件路径；Pillow 缺失时返回 None"""
    if Image is None:
        return None
    os.makedirs(out_dir, exist_ok=True)
    fname = filename or f"{snap['date']}.png"
    path = os.path.join(out_dir, fname)

    # 渐变背景
    img = Image.new("RGB", (W, H), "#1c1917")
    top_c, bot_c = (32, 26, 23), (94, 34, 12)
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), (
            int(top_c[0] + (bot_c[0] - top_c[0]) * t),
            int(top_c[1] + (bot_c[1] - top_c[1]) * t),
            int(top_c[2] + (bot_c[2] - top_c[2]) * t)))
    img = grad.resize((W, H))

    # 装饰光斑
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([W - 380, -200, W + 220, 420], fill=(232, 83, 47, 80))
    od.ellipse([-260, H - 240, 260, H + 260], fill=(232, 83, 47, 45))
    od.ellipse([W - 200, H - 160, W + 60, H + 100], fill=(255, 138, 76, 35))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 字体
    f_date = _load_font(40, bold=True)
    f_head = _load_font(58, bold=True)
    f_brand = _load_font(36, bold=True)
    f_sub = _load_font(28)
    f_badge = _load_font(26, bold=True)

    # 左上日期
    y, m, d = snap["date"].split("-")
    wd = "一二三四五六日"[datetime.strptime(snap["date"], "%Y-%m-%d").weekday()]
    draw.text((72, 66), f"{y}年{int(m)}月{int(d)}日 · 星期{wd}",
              font=f_date, fill="#fdba74")

    # 头条标题（最多两行）
    top = _top_item(snap)
    headline = top.get("title", "今日全球热点") if top else "今日全球热点"
    lines = _wrap(headline, f_head, W - 220, draw, max_lines=2)
    ly = 150
    for line in lines:
        draw.text((72, ly), line, font=f_head, fill="#fafaf9")
        ly += 78

    # 来源徽章
    if top:
        src_key = None
        for key, src in snap.get("sources", {}).items():
            if top in src.get("items", []):
                src_key = key
                break
        meta = config.SOURCE_META.get(src_key or "", {})
        label = f"TOP1 · {meta.get('name', '')}"
        if f_badge:
            tw = draw.textlength(label, font=f_badge)
            bw, bh = tw + 44, 52
            bx, by = 72, ly + 26
            draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=26,
                                   fill=meta.get("color", "#e8532f"))
            draw.text((bx + 22, by + 11), label, font=f_badge, fill="#ffffff")

    # 底部品牌区
    draw.line([(72, H - 118), (W - 72, H - 118)], fill=(255, 255, 255, ), width=2)
    draw.text((72, H - 96), f"{config.SITE_NAME} {config.SITE_NAME_EN}",
              font=f_brand, fill="#fafaf9")
    sub = f"六大热榜 · 每日 06:00 自动更新 · {config.SITE_DOMAIN.replace('https://', '')}"
    draw.text((72, H - 48), sub, font=f_sub, fill="#a8a29e")

    img.save(path, "PNG", optimize=True)
    return path
