#!/usr/bin/env python3
"""生成「言权」品牌图标资源（tab bar 图标 / 功能图标 / App 图标）

用法：python3 scripts/generate_icons.py
输出：miniapp/src/assets/
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "miniapp", "src", "assets")
TABBAR = os.path.join(ASSETS, "tabbar")
ICONS = os.path.join(ASSETS, "icons")

# ---- 品牌色 ----
NAVY_DARK = (11, 31, 58)
NAVY = (15, 43, 76)
NAVY_MID = (27, 70, 128)
GOLD = (201, 162, 75)
GOLD_LIGHT = (217, 188, 120)
GRAY = (142, 142, 147)
WHITE = (255, 255, 255)

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _rrect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _line(draw, pts, width, fill, cap="round"):
    draw.line(pts, width=width, fill=fill, joint="curve")


# ============================================================
#  Tab bar 图标（81x81）
# ============================================================

def icon_home(color):
    im = Image.new("RGBA", (81, 81), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    # 屋顶
    d.polygon([(40.5, 18), (13, 38), (15.5, 38), (15.5, 61), (65.5, 61), (65.5, 38), (68, 38)], fill=color)
    # 门
    d.rounded_rectangle([33, 43, 48, 61], radius=6, fill=(0, 0, 0, 0), outline=color, width=w)
    return im


def icon_compose(color):
    im = Image.new("RGBA", (81, 81), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    # 文档
    d.rounded_rectangle([17, 12, 58, 69], radius=7, outline=color, width=w)
    # 行线
    for y in (28, 40, 52):
        d.line([25, y, 50, y], fill=color, width=4)
    # 笔
    d.polygon([(57, 24), (67, 14), (71, 18), (61, 28)], fill=color)
    return im


def icon_history(color):
    im = Image.new("RGBA", (81, 81), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.ellipse([15, 15, 66, 66], outline=color, width=w)
    # 指针
    d.line([40.5, 40.5, 40.5, 26], fill=color, width=5)
    d.line([40.5, 40.5, 53, 47], fill=color, width=5)
    return im


def icon_profile(color):
    im = Image.new("RGBA", (81, 81), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    # 头
    d.ellipse([28, 14, 53, 39], outline=color, width=w)
    # 肩
    d.arc([16, 42, 65, 78], 180, 360, fill=color, width=w)
    return im


def _gen_tabbar():
    os.makedirs(TABBAR, exist_ok=True)
    specs = {
        "home": icon_home,
        "compose": icon_compose,
        "history": icon_history,
        "profile": icon_profile,
    }
    for name, fn in specs.items():
        fn(GRAY).save(os.path.join(TABBAR, f"{name}.png"))
        fn(GOLD).save(os.path.join(TABBAR, f"{name}-selected.png"))
    print("tabbar icons:", sorted(os.listdir(TABBAR)))


# ============================================================
#  功能图标（96x96，线性风格）
# ============================================================

def _canvas():
    return Image.new("RGBA", (96, 96), (0, 0, 0, 0)), ImageDraw.Draw(Image.new("RGBA", (96, 96)))


def icon_mic(fill=WHITE, bg=NAVY_MID):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([4, 4, 92, 92], fill=bg)
    w = 6
    d.rounded_rectangle([38, 18, 58, 52], radius=10, outline=fill, width=w)
    d.arc([30, 38, 66, 66], 180, 360, fill=fill, width=w)
    d.line([48, 62, 48, 72], fill=fill, width=w)
    d.line([36, 72, 60, 72], fill=fill, width=w)
    return im


def icon_keyboard(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([12, 26, 84, 70], radius=10, outline=color, width=w)
    for x in (24, 40, 56, 72):
        for y in (36, 52):
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)
    return im


def icon_camera(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([14, 28, 82, 70], radius=10, outline=color, width=w)
    d.polygon([(34, 28), (40, 20), (56, 20), (62, 28)], fill=color)
    d.ellipse([37, 38, 59, 60], outline=color, width=w)
    return im


def icon_letter(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([14, 18, 82, 78], radius=8, outline=color, width=w)
    d.line([16, 26, 48, 50, 80, 26], fill=color, width=w)
    return im


def icon_scale(color=GOLD):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    # 底座
    d.line([20, 76, 76, 76], fill=color, width=w)
    d.polygon([(42, 76), (54, 76), (48, 70)], fill=color)
    # 立柱
    d.line([48, 70, 48, 34], fill=color, width=w)
    # 横梁
    d.line([28, 34, 68, 34], fill=color, width=w)
    d.line([28, 34, 28, 28], fill=color, width=w)
    d.line([68, 34, 68, 28], fill=color, width=w)
    # 托盘
    d.line([20, 28, 36, 28], fill=color, width=w)
    d.line([60, 28, 76, 28], fill=color, width=w)
    d.line([24, 28, 32, 52], fill=color, width=w)
    d.line([72, 28, 64, 52], fill=color, width=w)
    return im


def icon_check(color=(30, 158, 106)):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 8
    d.ellipse([10, 10, 86, 86], outline=color, width=w)
    d.line([30, 48, 43, 62, 68, 34], fill=color, width=w)
    return im


def icon_chevron(color=(139, 152, 171)):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([34, 30, 58, 48, 34, 66], fill=color, width=7)
    return im


def icon_copy(color=WHITE):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([28, 16, 78, 66], radius=6, outline=color, width=w)
    d.rounded_rectangle([18, 26, 68, 80], radius=6, outline=color, width=w)
    return im


def icon_share(color=WHITE):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.line([38, 44, 58, 34], fill=color, width=w)
    d.line([38, 52, 58, 62], fill=color, width=w)
    d.ellipse([14, 34, 30, 50], outline=color, width=w)
    d.ellipse([58, 20, 74, 36], outline=color, width=w)
    d.ellipse([58, 60, 74, 76], outline=color, width=w)
    return im


def icon_edit(color=WHITE):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([30, 66, 36, 58, 66, 28, 72, 34, 42, 64, 30, 66], fill=color, width=5)
    d.line([60, 24, 72, 36], fill=color, width=5)
    return im


def icon_trash(color=(224, 91, 91)):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([30, 30, 66, 78], radius=6, outline=color, width=w)
    d.line([22, 30, 74, 30], fill=color, width=w)
    d.line([38, 30, 38, 22, 58, 22, 58, 30], fill=color, width=w)
    d.line([42, 40, 42, 68], fill=color, width=w)
    d.line([54, 40, 54, 68], fill=color, width=w)
    return im


def icon_arrow(color=WHITE):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([26, 48, 70, 48], fill=color, width=6)
    d.line([58, 36, 70, 48, 58, 60], fill=color, width=6)
    return im


def icon_lock(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([26, 42, 70, 76], radius=8, outline=color, width=w)
    d.arc([32, 20, 64, 52], 180, 360, fill=color, width=w)
    d.ellipse([44, 54, 52, 62], fill=color)
    return im


def icon_doc(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([22, 14, 74, 82], radius=6, outline=color, width=w)
    for y in (30, 44, 58):
        d.line([32, y, 64, y], fill=color, width=4)
    return im


def icon_shield(color=GOLD):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.polygon([(48, 14), (76, 26), (76, 48), (48, 84), (20, 48), (20, 26)], outline=color, width=w)
    d.line([34, 46, 44, 56, 62, 36], fill=color, width=w)
    return im


def icon_chat(color=NAVY):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5
    d.rounded_rectangle([14, 18, 82, 66], radius=12, outline=color, width=w)
    d.polygon([(30, 66), (30, 82), (48, 66)], fill=color)
    return im


def icon_spark(color=GOLD):
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(48, 14), (56, 38), (82, 48), (56, 58), (48, 82), (40, 58), (14, 48), (40, 38)], fill=color)
    return im


def _gen_icons():
    os.makedirs(ICONS, exist_ok=True)
    icons = {
        "mic": icon_mic(),
        "keyboard": icon_keyboard(),
        "camera": icon_camera(),
        "letter": icon_letter(),
        "scale": icon_scale(),
        "check": icon_check(),
        "chevron": icon_chevron(),
        "copy": icon_copy(),
        "share": icon_share(),
        "edit": icon_edit(),
        "trash": icon_trash(),
        "arrow": icon_arrow(),
        "lock": icon_lock(),
        "doc": icon_doc(),
        "shield": icon_shield(),
        "chat": icon_chat(),
        "spark": icon_spark(),
    }
    for name, im in icons.items():
        im.save(os.path.join(ICONS, f"{name}.png"))
    print("feature icons:", len(icons))


# ============================================================
#  App 图标（1024x1024）
# ============================================================

def app_icon():
    size = 1024
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # 深蓝渐变底（逐行插值）
    top = NAVY_DARK
    bottom = (36, 84, 146)
    for y in range(size):
        t = y / size
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=color)

    # 圆角裁切
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size, size], radius=200, fill=255)
    im.putalpha(mask)

    # 外圈金色光环
    d.ellipse([170, 170, 854, 854], outline=(GOLD_LIGHT + (255,)), width=14)

    # 天平（中间偏上）
    d.line([(512, 620), (512, 330)], fill=GOLD_LIGHT, width=28)
    d.line([(250, 330), (774, 330)], fill=GOLD_LIGHT, width=28)
    d.line([(250, 330), (250, 300)], fill=GOLD_LIGHT, width=22)
    d.line([(774, 330), (774, 300)], fill=GOLD_LIGHT, width=22)
    d.line([(180, 300), (320, 300)], fill=GOLD_LIGHT, width=22)
    d.line([(704, 300), (844, 300)], fill=GOLD_LIGHT, width=22)
    d.line([(210, 300), (300, 560)], fill=GOLD_LIGHT, width=22)
    d.line([(814, 300), (724, 560)], fill=GOLD_LIGHT, width=22)
    d.line([(512, 620), (430, 720)], fill=GOLD_LIGHT, width=24)
    d.line([(512, 620), (594, 720)], fill=GOLD_LIGHT, width=24)
    d.line([(400, 720), (624, 720)], fill=GOLD_LIGHT, width=24)

    # 底部品牌名
    font = _font(92)
    text = "言权"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((size - tw) / 2, 780), text, font=font, fill=WHITE)

    # 渐变遮罩下的金色小徽章：右上角声波
    d.arc([640, 130, 900, 390], 200, 340, fill=GOLD, width=24)
    d.arc([670, 160, 870, 360], 210, 330, fill=GOLD, width=20)
    return im


def main():
    _gen_tabbar()
    _gen_icons()
    os.makedirs(ASSETS, exist_ok=True)
    app_icon().save(os.path.join(ASSETS, "app-icon.png"))
    print("app icon saved")
    print("done ->", ASSETS)


if __name__ == "__main__":
    main()
