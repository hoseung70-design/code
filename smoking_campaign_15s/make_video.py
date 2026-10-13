# -*- coding: utf-8 -*-
"""
15초 금연 공익광고 자동 제작 스크립트

  python make_video.py           영상 제작 -> output/smoking_campaign_15s.mp4
  python make_video.py --check   설치 상태만 점검

연출 개요 (1080x1920, 30fps, 정확히 15초)
  장면 1  0~5초   완전한 어둠. 유일한 광원은 담뱃불. 담배는 자기 불빛에만 비친다.
                  연기는 노이즈 질감이 연기 기둥 모양을 따라 흘러 올라간다. 카메라는 천천히 다가간다.
  장면 2  5~10초  같은 자리의 불씨가 얇은 빛의 고리가 되어 조여 들며 꺼진다. 짧은 정적.
                  그 점에서 수평선 같은 빛이 그어지고, 위아래로 열리며 어둠을 밀어낸다.
  장면 3 10~15초  아침. 낮은 해와 아나모픽 플레어, 렌즈 앞의 흐린 잎, 빛망울.
  자막    가는 글씨 + 자간. 흐림에서 선명으로, 초점이 맞듯 나타난다.
  사운드  음향 파일이 없으면 저음 드론 -> 정적 -> 서브 저음 -> 따뜻한 화음을 자동 합성한다.
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
GEN = ASSETS / "generated"      # 자동 생성되는 그래픽 레이어
AUDIO_DIR = ASSETS / "audio"    # 선택: narration.*, music.*
FONT_DIR = ASSETS / "fonts"     # 선택: 직접 넣은 한글 폰트
BUILD = ROOT / "build"          # 중간 작업 파일 (지워도 됨)
OUTPUT = ROOT / "output"
OUT_FILE = OUTPUT / "smoking_campaign_15s.mp4"
PREVIEW_FILE = OUTPUT / "preview_contact_sheet.jpg"

W, H, FPS = 1080, 1920, 30
TOTAL = 15.0
TOTAL_FRAMES = int(TOTAL * FPS)  # 450
XFADE = 0.6

# 장면 길이는 전환 겹침을 포함한다: 5.3 + 5.6 + 5.3 - 0.6 * 2 = 15.0초
# (전환이 5초, 10초를 중심으로 일어난다)
SCENE_LEN = [5.3, 5.6, 5.3]
SCENE_START = [0.0, 4.7, 9.7]

SUB1 = ["한 모금의 습관,", "당신의 내일을 바꿉니다."]
SUB2 = ["오늘, 한 번의 선택부터."]
SUB3 = ["금연, 당신의 내일을", "지키는 시작입니다."]
CTA = "오늘부터 금연하세요."

# 비워 두면 맑은 고딕을 먼저 찾는다. 다른 폰트를 쓰려면 파일 경로를 적는다.
FONT_LIGHT_OVERRIDE = os.environ.get("CAMPAIGN_FONT_LIGHT", "")
FONT_BOLD_OVERRIDE = os.environ.get("CAMPAIGN_FONT_BOLD", "")

# 음향
AUDIO_EXTS = [".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"]
SOUND_DESIGN = True       # 배경음악 파일이 없을 때 사운드를 자동 합성 (False면 무음)
MUSIC_VOLUME = 0.45
NARRATION_VOLUME = 1.0
NARRATION_DELAY = 0.4

EMBER = (540, 1000)       # 담뱃불 위치 = 장면 2 고리의 중심 (매치 컷)
SUN = (760, 430)

# 자막 표시 검증: (이름, 레이아웃 키, 보여야 하는 시각, 없어야 하는 시각)
SUB_CHECKS = [
    ("장면1 자막", "sub1", 2.6, 0.3),
    ("장면2 자막", "sub2", 8.4, 5.6),
    ("장면3 메인 자막", "sub3", 12.0, 10.35),
    ("마지막 문구", "cta", 14.7, 12.0),
]
PREVIEW_TIMES = [1.2, 3.0, 5.6, 7.6, 11.8, 14.9]


# ---------------------------------------------------------------------------
# 공통 도우미
# ---------------------------------------------------------------------------
class UserError(Exception):
    def __init__(self, problem, fix=""):
        super().__init__(problem)
        self.problem, self.fix = problem, fix


def say(msg=""):
    print(msg, flush=True)


def step(msg):
    say("")
    say("▶ " + msg)


try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat
except ImportError:
    Image = None

if Image is not None:
    try:
        LANCZOS, BICUBIC, NEAREST = Image.Resampling.LANCZOS, Image.Resampling.BICUBIC, Image.Resampling.NEAREST
    except AttributeError:
        LANCZOS, BICUBIC, NEAREST = Image.LANCZOS, Image.BICUBIC, Image.NEAREST


def find_tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    local = ROOT / "ffmpeg" / "bin" / exe
    return str(local) if local.is_file() else shutil.which(name)


def run(cmd, what):
    """명령을 실행하고, 실패하면 원인과 해결 방법을 보여 준다."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise UserError(what + ": 실행 파일을 찾지 못했습니다 (" + str(cmd[0]) + ")",
                        "FFmpeg 설치와 PATH 설정을 README.md 안내대로 확인하세요.")
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", "replace").strip().splitlines()
        low = "\n".join(err).lower()
        fix = "위 오류 내용을 확인하세요."
        if "permission denied" in low:
            fix = "결과 영상이 동영상 플레이어 등에서 열려 있으면 닫고 다시 실행하세요."
        elif "no such filter" in low:
            fix = "FFmpeg가 오래되었거나 기능이 빠진 버전입니다. 최신 FFmpeg(6 이상)를 설치하세요."
        elif "no space left" in low:
            fix = "디스크 공간이 부족합니다. 1GB 이상 확보하세요."
        raise UserError(what + " 단계에서 FFmpeg가 실패했습니다.\n" +
                        "\n".join("    " + line for line in err[-15:]), fix)
    return res.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# 1) 환경 점검
# ---------------------------------------------------------------------------
def font_has_hangul(path):
    try:
        font = ImageFont.truetype(str(path), 48)

        def render(text):
            im = Image.new("L", (160, 80), 0)
            ImageDraw.Draw(im).text((4, 4), text, font=font, fill=255)
            return im

        han, missing = render("한글"), render("\U0010FFFD\U0010FFFD")  # 없는 글자는 빈 네모로 그려진다
        return bool(han.getbbox()) and han.tobytes() != missing.tobytes()
    except Exception:
        return False


def find_fonts():
    """(가는 글씨, 굵은 글씨) 한글 폰트. 맑은 고딕(Semilight/Bold)을 먼저 사용한다."""
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    user = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
    own = sorted(p for p in FONT_DIR.glob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc")) \
        if FONT_DIR.is_dir() else []
    others = [Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
              Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")]

    def pick(override, names, own_hint):
        cands = [Path(override)] if override else []
        cands += [win / n for n in names]
        cands += [p for p in own if own_hint in p.name.lower()] + own
        cands += [d / n for d in (win, user) for n in ("NanumGothic.ttf", "NanumBarunGothic.ttf", "gulim.ttc")]
        cands += others
        for p in cands:
            if p.is_file() and font_has_hangul(p):
                return p
        return None

    light = pick(FONT_LIGHT_OVERRIDE, ["malgunsl.ttf", "malgun.ttf"], "light")
    bold = pick(FONT_BOLD_OVERRIDE, ["malgunbd.ttf", "malgun.ttf"], "bold")
    if not light or not bold:
        raise UserError("한글을 표시할 수 있는 폰트를 찾지 못했습니다.",
                        "Windows에는 보통 맑은 고딕이 있습니다. 없다면 한글 폰트(.ttf)를 "
                        "assets/fonts 폴더에 넣고 다시 실행하세요.")
    return light, bold


def find_audio():
    found = {"narration": None, "music": None}
    if AUDIO_DIR.is_dir():
        for key in found:
            for ext in AUDIO_EXTS:
                p = AUDIO_DIR / (key + ext)
                if p.is_file() and p.stat().st_size > 0:
                    found[key] = p
                    break
    return found


def check_environment():
    step("1단계: 설치 상태 점검")
    say("  Python   : " + sys.version.split()[0] + "  (" + sys.executable + ")")
    if sys.version_info < (3, 8):
        raise UserError("Python 3.8 이상이 필요합니다.", "python.org에서 최신 Python 3를 설치하세요.")
    if Image is None:
        raise UserError("Pillow(그림 생성 라이브러리)가 설치되어 있지 않습니다.",
                        "make_video.bat을 실행하면 설치 여부를 물어봅니다.\n"
                        "    직접 설치하려면:  py -m pip install --user Pillow")
    import PIL
    say("  Pillow   : " + PIL.__version__)
    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        raise UserError("FFmpeg(또는 ffprobe)를 찾지 못했습니다.",
                        "README.md의 'FFmpeg 설치' 안내대로 설치한 뒤, 창을 새로 열고 다시 실행하세요.")
    ver = run([ffmpeg, "-hide_banner", "-version"], "FFmpeg 버전 확인").splitlines()[0]
    say("  FFmpeg   : " + ver.replace("ffmpeg version ", "").split(" Copyright")[0] + "  (" + ffmpeg + ")")
    filters = run([ffmpeg, "-hide_banner", "-filters"], "FFmpeg 필터 확인")
    need = ["zoompan", "xfade", "geq", "alphamerge", "blend", "overlay", "fade", "lut", "noise",
            "aevalsrc", "anoisesrc", "anullsrc", "amix", "aecho", "sidechaincompress", "alimiter"]
    missing = [f for f in need if (" " + f + " ") not in filters]
    if missing:
        raise UserError("FFmpeg에 필요한 기능이 없습니다: " + ", ".join(missing),
                        "gyan.dev의 최신 FFmpeg(essentials 또는 full)로 다시 설치하세요.")
    if "libx264" not in run([ffmpeg, "-hide_banner", "-encoders"], "FFmpeg 인코더 확인"):
        raise UserError("FFmpeg에 H.264(libx264) 인코더가 없습니다.",
                        "gyan.dev의 FFmpeg(essentials 또는 full)로 다시 설치하세요.")
    say("  FFmpeg 기능 : 정상 (줌, 전환, 합성, H.264, 사운드 합성)")
    light, bold = find_fonts()
    for label, p in (("가는 글씨", light), ("굵은 글씨", bold)):
        tag = "맑은 고딕" if "malgun" in p.name.lower() else "대체 폰트"
        say("  %s : %s  [%s]" % (label, p, tag))
    audio = find_audio()
    say("  내레이션 : " + (str(audio["narration"]) if audio["narration"] else "없음 (선택 사항)"))
    say("  배경음악 : " + (str(audio["music"]) if audio["music"] else
                         ("없음 → 사운드 자동 합성" if SOUND_DESIGN else "없음 → 무음")))
    return ffmpeg, ffprobe, light, bold


# ---------------------------------------------------------------------------
# 2) Pillow 그래픽 도우미
# ---------------------------------------------------------------------------
def vgradient(stops, size=(W, H)):
    """세로 그라데이션. stops = [(0~1 위치, (r,g,b)), ...]"""
    w, h = size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        p = y / (h - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= p <= p1:
                f = (p - p0) / (p1 - p0) if p1 > p0 else 0
                f = f * f * (3 - 2 * f)
                px[0, y] = tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
                break
    return col.resize((w, h), NEAREST)


def glow(size, color, power=2.0, strength=1.0):
    """원(타원) 가장자리에서 정확히 0이 되는 부드러운 빛 (RGBA)."""
    if isinstance(size, int):
        size = (size, size)
    # radial_gradient는 원 가장자리에서 약 181, 모서리에서 255이므로 181로 나눈다
    g = Image.radial_gradient("L").resize(size, BICUBIC)
    a = g.point(lambda v: int(255 * strength * max(0.0, 1 - v / 181.0) ** power))
    im = Image.new("RGBA", size, tuple(color) + (0,))
    im.putalpha(a)
    return im


def add_light(base, light, center):
    """빛을 screen 방식으로 더한다."""
    layer = Image.new("RGB", base.size, (0, 0, 0))
    layer.paste(light.convert("RGB"), (int(center[0] - light.width / 2), int(center[1] - light.height / 2)), light)
    return ImageChops.screen(base, layer)


def over(dst, src, xy=(0, 0)):
    tmp = Image.new("RGBA", dst.size, (0, 0, 0, 0))
    tmp.paste(src, (int(xy[0]), int(xy[1])))
    return Image.alpha_composite(dst, tmp)


def vignette(base, strength=0.85, color=(0, 0, 0)):
    v = Image.radial_gradient("L").resize((int(W * 1.3), int(H * 1.15)), BICUBIC)
    v = v.crop(((v.width - W) // 2, (v.height - H) // 2, (v.width - W) // 2 + W, (v.height - H) // 2 + H))
    a = v.point(lambda x: int(255 * strength * min(1.0, max(0.0, (x / 255 - 0.40) / 0.60)) ** 1.6))
    layer = Image.new("RGBA", (W, H), tuple(color) + (255,))
    layer.putalpha(a)
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def soft_blur(im, radius):
    """투명 레이어를 흐리게 한다. 투명 부분의 검은색이 섞여 가장자리에 어두운 테두리가
    생기지 않도록, 미리 곱한 알파(RGBa) 상태에서 흐린다."""
    if im.mode != "RGBA":
        return im.filter(ImageFilter.GaussianBlur(radius))
    return im.convert("RGBa").filter(ImageFilter.GaussianBlur(radius)).convert("RGBA")


def fractal_noise(size, seed, octaves):
    """세로로 늘어진 부드러운 노이즈 (연기 질감). octaves = [(가로칸, 세로칸, 비중), ...]"""
    rnd = random.Random(seed)
    out = None
    acc = 0.0
    for cw, ch, wgt in octaves:
        small = Image.frombytes("L", (cw, ch), bytes(rnd.getrandbits(8) for _ in range(cw * ch)))
        layer = small.resize(size, BICUBIC)
        acc += wgt
        out = layer if out is None else Image.blend(out, layer, wgt / acc)
    # 대비를 높여 가는 줄기와 빈 공간이 생기게 한다
    return out.point(lambda v: int(255 * min(1.0, max(0.0, (v / 255 - 0.40) / 0.32)) ** 1.35))


def tracked_width(font, text, tracking):
    return sum(font.getlength(c) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, cx, cy, text, font, tracking, fill):
    x = cx - tracked_width(font, text, tracking) / 2
    for c in text:
        draw.text((x, cy), c, font=font, fill=fill, anchor="lm")
        x += font.getlength(c) + tracking


def title(lines, font_path, size, center_y, color, shadow, tracking=0.06, line_gap=1.55, hairline=None):
    """자막 레이어 2장(선명 / 흐림)과 글자 영역을 만든다.
    hairline = (y, 길이, 투명도): 가는 가로선."""
    font = ImageFont.truetype(str(font_path), size)
    tr = size * tracking
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    gap = size * line_gap
    top = center_y - gap * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        draw_tracked(d, W / 2, top + i * gap, line, font, tr, 255)
    box = list(mask.getbbox())
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), shadow[:3] + (0,))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(size * 0.45)).point(lambda v: int(v * shadow[3] / 255)))
    sharp = over(sharp, sh, (0, size * 0.06))
    fg = Image.new("RGBA", (W, H), tuple(color) + (0,))
    fg.putalpha(mask)
    sharp = Image.alpha_composite(sharp, fg)
    if hairline:
        y, length, alpha = hairline
        ImageDraw.Draw(sharp).rectangle((W / 2 - length / 2, y - 1, W / 2 + length / 2, y), fill=tuple(color) + (alpha,))
    blur = soft_blur(sharp, size * 0.22)
    return sharp, blur, box


# ---------------------------------------------------------------------------
# 장면 1: 어둠, 담뱃불, 연기
# ---------------------------------------------------------------------------
SMOKE_H = EMBER[1] // 2          # 연기는 반 해상도로 계산 (연기는 원래 부드러우므로)
SMOKE_SPEED = (40, 22)           # 두 노이즈 층이 올라가는 속도 (반 해상도 px/초)


def draw_cigarette():
    """자기 불빛에만 비친 담배. 불에서 멀어질수록 어둠에 잠긴다."""
    SS, L, T, pad = 3, 760, 22, 30
    sw, sh = L * SS, T * SS
    rnd = random.Random(3)
    strip = Image.new("RGB", (sw, sh))
    px = strip.load()
    for x in range(sw):
        dist = L - x / SS                    # 불까지의 거리(px)
        lit = 0.07 + 0.93 * math.exp(-dist / 240.0)
        warm = math.exp(-dist / 70.0)
        if dist < 30:                        # 재
            heat = math.exp(-dist / 6.0)
            base = tuple(int((92, 88, 84)[i] * (1 - heat) + (255, 96, 36)[i] * heat) for i in range(3))
        elif dist < 34:                      # 탄 경계
            base = (70, 48, 34)
        else:                                # 종이
            base = (232, 226, 216)
        for y in range(sh):
            v = (y / (sh - 1)) * 2 - 1
            shade = 0.35 + 0.65 * math.cos(v * math.pi / 2) ** 0.8 + 0.28 * math.exp(-((v + 0.38) / 0.16) ** 2)
            if dist < 30:
                shade *= rnd.uniform(0.7, 1.15)
            px[x, y] = tuple(int(min(255, (base[i] * (1 - warm * 0.55) + (255, 168, 112)[i] * warm * 0.55)
                                     * lit * shade)) for i in range(3))
    strip = strip.resize((L, T), LANCZOS)
    canvas = Image.new("RGBA", (L + pad * 2, T + pad * 2), (0, 0, 0, 0))
    canvas.paste(strip, (pad, pad))
    tip = (pad + L, pad + T / 2)
    canvas = canvas.rotate(5.5, resample=BICUBIC, center=tip)
    return canvas, (EMBER[0] - tip[0], EMBER[1] - tip[1])


def ember_glow():
    """담뱃불의 빛: 넓은 붉은 빛 + 주황 코어 + 아나모픽 가로 플레어. (반 해상도로 저장)"""
    im = Image.new("RGBA", (1000, 700), (0, 0, 0, 0))
    for g in (glow((1000, 700), (170, 42, 12), 2.2, 0.55),
              glow((1000, 18), (255, 140, 70), 1.4, 0.45),
              glow(240, (255, 110, 36), 1.9, 0.85),
              glow((620, 6), (255, 214, 170), 1.2, 0.75),
              glow(52, (255, 226, 176), 1.1, 1.0)):
        im = over(im, g, (500 - g.width / 2, 350 - g.height / 2))
    return im.resize((500, 350), LANCZOS)


def make_scene1(light, bold):
    bg = vgradient([(0, (6, 6, 8)), (1, (3, 3, 4))])
    bg = add_light(bg, glow((1800, 1400), (64, 18, 7), 2.0, 0.55), EMBER)
    bg = vignette(bg, 0.9).convert("RGBA")
    cig, pos = draw_cigarette()
    bg = over(bg, cig, pos)
    bg.convert("RGB").save(GEN / "s1_background.png")
    ember_glow().save(GEN / "ember_glow.png")

    # 연기: (1) 위로 흐르는 노이즈 두 장 (2) 고정된 연기 기둥 모양 (3) 색
    hw = W // 2
    tall = lambda speed: SMOKE_H + int(speed * SCENE_LEN[0]) + 12
    fractal_noise((hw, tall(SMOKE_SPEED[0])), 41, [(5, 7, 0.45), (11, 16, 0.30), (26, 40, 0.25)]).save(GEN / "s1_noise_a.png")
    fractal_noise((hw + 60, tall(SMOKE_SPEED[1])), 77, [(4, 5, 0.6), (9, 11, 0.4)]).save(GEN / "s1_noise_b.png")
    rows = []
    for y in range(SMOKE_H):
        u = (SMOKE_H - y) / SMOKE_H          # 0: 불, 1: 화면 위
        xc = hw / 2 + 46 * u ** 1.3 * math.sin(u * 5.2 + 0.7) + 40 * u ** 2
        x2 = xc + 110 * u ** 2
        wd = 3 + 120 * u ** 1.35
        env = min(1.0, (SMOKE_H - y) / 70.0) ** 1.5 * (1 - 0.45 * u)
        row = bytearray(hw)
        for x in range(hw):
            a = math.exp(-((x - xc) / wd) ** 2) + 0.45 * u * math.exp(-((x - x2) / (wd * 0.7)) ** 2)
            row[x] = int(255 * min(1.0, a * env))
        rows.append(bytes(row))
    Image.frombytes("L", (hw, SMOKE_H), b"".join(rows)).save(GEN / "s1_smoke_shape.png")
    vgradient([(0, (150, 152, 160)), (0.6, (186, 182, 182)), (0.9, (200, 160, 136)), (1, (210, 140, 100))],
              (hw, SMOKE_H)).save(GEN / "s1_smoke_color.png")

    sharp, blur, box = title(SUB1, light, 54, 1400, (242, 238, 232), (0, 0, 0, 200))
    sharp.save(GEN / "s1_text.png")
    blur.save(GEN / "s1_text_blur.png")
    return {"sub1": box}


# ---------------------------------------------------------------------------
# 장면 2: 불씨가 고리가 되어 꺼지고, 빛이 열린다
# ---------------------------------------------------------------------------
def make_scene2(light, bold):
    bg = vgradient([(0, (5, 5, 7)), (1, (3, 3, 5))])
    bg = add_light(bg, glow((1500, 1200), (40, 14, 6), 2.0, 0.5), EMBER)
    vignette(bg, 0.9).save(GEN / "s2_background.png")
    sharp, blur, box = title(SUB2, light, 58, 1400, (246, 243, 236), (0, 0, 0, 220))
    sharp.save(GEN / "s2_text.png")
    blur.save(GEN / "s2_text_blur.png")
    return {"sub2": box}


# ---------------------------------------------------------------------------
# 장면 3: 아침
# ---------------------------------------------------------------------------
def leaf_shape(length, width):
    im = Image.new("L", (length + 20, width + 20), 0)
    cy = 10 + width / 2
    up = [(10 + length * t, cy - width / 2 * math.sin(math.pi * t) ** 0.8) for t in [i / 48 for i in range(49)]]
    ImageDraw.Draw(im).polygon(up + [(x, 2 * cy - y) for x, y in reversed(up)], fill=255)
    return im


def make_scene3(light, bold):
    rnd = random.Random(12)
    bg = vgradient([(0, (255, 234, 198)), (0.30, (246, 228, 192)), (0.50, (214, 214, 170)),
                    (0.64, (120, 154, 106)), (0.80, (40, 86, 58)), (1, (12, 38, 27))])
    # 멀리 보이는 숲: 아주 흐린 띠 (공기 원근감)
    for base_y, col, blur in ((1040, (150, 172, 128, 140), 26), (1150, (78, 118, 82, 170), 18)):
        ridge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pts = [(x, base_y - 26 * math.sin(x * 0.006 + base_y) - 14 * math.sin(x * 0.017 + 1.3))
               for x in range(-40, W + 41, 8)]
        ImageDraw.Draw(ridge).polygon(pts + [(W + 40, H), (-40, H)], fill=col)
        bg = Image.alpha_composite(bg.convert("RGBA"), soft_blur(ridge, blur))
    bg = bg.convert("RGB")
    bg = add_light(bg, glow((2200, 820), (255, 244, 220), 1.6, 0.42), (540, 1000))    # 아침 안개
    bg = add_light(bg, glow(1900, (255, 214, 150), 1.4, 0.85), SUN)
    bg = add_light(bg, glow(330, (255, 250, 236), 1.1, 1.0), SUN)
    bg = add_light(bg, glow((2600, 44), (255, 214, 160), 1.3, 0.50), SUN)              # 아나모픽 플레어
    bg = add_light(bg, glow((1500, 8), (255, 246, 228), 1.1, 0.80), SUN)
    vignette(bg, 0.45, (8, 30, 20)).save(GEN / "s3_background.png")

    # 햇살 줄기 (반 해상도)
    rays = Image.new("RGBA", (900, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(rays)
    ox, oy = 600, 100
    for i in range(7):
        ang = math.radians(108 + i * 8 + rnd.uniform(-2, 2))
        wd = math.radians(rnd.uniform(1.0, 2.4))
        d.polygon([(ox, oy), (ox + 1600 * math.cos(ang - wd), oy + 1600 * math.sin(ang - wd)),
                   (ox + 1600 * math.cos(ang + wd), oy + 1600 * math.sin(ang + wd))],
                  fill=(255, 248, 226, int(rnd.uniform(26, 46))))
    rays = soft_blur(rays, 14)
    fade = vgradient([(0, (255,) * 3), (0.45, (170,) * 3), (0.8, (0,) * 3), (1, (0,) * 3)], (900, 1200)).convert("L")
    rays.putalpha(ImageChops.multiply(rays.getchannel("A"), fade))
    rays.save(GEN / "s3_rays.png")

    # 렌즈 바로 앞의 잎 (초점이 맞지 않아 크게 흐림)
    fol = Image.new("RGBA", (W + 160, H), (0, 0, 0, 0))
    for (x, y, L, Wd, ang, col, blur) in ((-120, -60, 640, 230, -35, (38, 66, 34, 230), 34),
                                          (60, -140, 420, 150, -70, (64, 96, 48, 190), 26),
                                          (820, 1500, 700, 250, 160, (16, 36, 22, 240), 38),
                                          (-260, 1620, 640, 220, 15, (18, 40, 24, 235), 34),
                                          (980, 560, 380, 130, 205, (96, 124, 64, 140), 22)):
        m = leaf_shape(L, Wd).rotate(ang, resample=BICUBIC, expand=True)
        lf = Image.new("RGBA", m.size, col[:3] + (0,))
        lf.putalpha(m.point(lambda v: v * col[3] // 255))
        big = Image.new("RGBA", (m.width + blur * 6, m.height + blur * 6), (0, 0, 0, 0))
        big = soft_blur(over(big, lf, (blur * 3, blur * 3)), blur)
        fol = over(fol, big, (x + 80 - blur * 3, y - blur * 3))
    fol.save(GEN / "s3_foliage.png")

    # 빛망울 (가장자리가 살짝 밝은 실제 렌즈 보케)
    bok = Image.new("RGBA", (W, H + 120), (0, 0, 0, 0))
    for _ in range(12):
        r = int(rnd.uniform(16, 52))
        ang, dist = rnd.uniform(0, 6.28), rnd.uniform(80, 560)
        cx, cy = SUN[0] + math.cos(ang) * dist, SUN[1] + 80 + math.sin(ang) * dist * 0.8
        disc = Image.new("RGBA", (r * 2 + 16, r * 2 + 16), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((8, 8, 8 + r * 2, 8 + r * 2), fill=(255, 236, 196, int(255 * rnd.uniform(0.07, 0.16))))
        bok = over(bok, soft_blur(disc, 3.5), (cx - r - 8, cy - r - 8))
    bok.save(GEN / "s3_bokeh.png")

    s, b, box3 = title(SUB3, light, 56, 1300, (255, 255, 250), (4, 26, 16, 210))
    s.save(GEN / "s3_text.png")
    b.save(GEN / "s3_text_blur.png")
    s, b, box_cta = title([CTA], bold, 64, 1500, (255, 255, 250), (4, 26, 16, 210), tracking=0.03,
                          hairline=(1418, 72, 170))
    s.save(GEN / "s3_cta.png")
    b.save(GEN / "s3_cta_blur.png")
    return {"sub3": box3, "cta": box_cta}


def make_layers(light, bold):
    step("2단계: Pillow로 그래픽 레이어와 한글 자막 만들기")
    GEN.mkdir(parents=True, exist_ok=True)
    boxes = {}
    for i, fn in enumerate((make_scene1, make_scene2, make_scene3), 1):
        t0 = time.time()
        boxes.update(fn(light, bold))
        say("  장면 %d 레이어 완료 (%.1f초)" % (i, time.time() - t0))
    (GEN / "layout.json").write_text(json.dumps(boxes, ensure_ascii=False, indent=1), encoding="utf-8")
    say("  저장 위치: " + str(GEN))
    return boxes


# ---------------------------------------------------------------------------
# 3) FFmpeg: 장면별 움직임
# ---------------------------------------------------------------------------
def still(p):
    return ["-i", str(p)]


def looped(p, dur):
    return ["-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % dur, "-i", str(p)]


def blank(w, h, dur):
    return ["-f", "lavfi", "-i", "color=c=black@0.0:s=%dx%d:r=%d:d=%.3f" % (w, h, FPS, dur)]


def push(n, z, cx, cy):
    """카메라 푸시인. 2배로 키운 뒤 줌해서 떨림을 줄이고, (cx, cy)를 고정점으로 한다."""
    return ("scale=iw*2:ih*2,zoompan=z='%s':x='%d*(1-1/zoom)':y='%d*(1-1/zoom)':d=%d:s=%dx%d:fps=%d,format=rgba"
            % (z, cx * 2, cy * 2, n, W, H, FPS))


def fade_a(fin=None, fout=None):
    f = ""
    if fin:
        f += ",fade=t=in:st=%.2f:d=%.2f:alpha=1" % fin
    if fout:
        f += ",fade=t=out:st=%.2f:d=%.2f:alpha=1" % fout
    return f


def reveal(sharp_idx, blur_idx, label, t_in, t_out=None, dur=1.0):
    """초점이 맞듯 나타나는 자막: 흐린 글자가 먼저 오고 선명한 글자로 바뀐다."""
    return ("[%d:v]format=rgba%s[%s_s];" % (sharp_idx, fade_a((t_in + 0.25, dur), (t_out, 0.6) if t_out else None), label) +
            "[%d:v]format=rgba%s[%s_b];" % (blur_idx, fade_a((t_in, 0.35), (t_in + 0.35, dur * 0.9)), label))


def put_text(base, label, t_in, out):
    """흐림 → 선명 레이어를 겹치고 아주 조금 떠오르게 한다."""
    y = "'10*pow(1-clip((t-%.2f)/1.6,0,1),3)'" % t_in
    return ("[%s][%s_b]overlay=x=0:y=%s:format=rgb[%s_1];" % (base, label, y, label) +
            "[%s_1][%s_s]overlay=x=0:y=%s:format=rgb[%s];" % (label, label, y, out))


def render_scene(ffmpeg, idx, inputs, graph):
    dur = SCENE_LEN[idx - 1]
    n = int(round(dur * FPS))
    out = BUILD / ("scene%d.mp4" % idx)
    t0 = time.time()
    run([ffmpeg, "-hide_banner", "-y", *inputs, "-filter_complex", graph + ",format=yuv420p[out]",
         "-map", "[out]", "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "8", "-pix_fmt", "yuv420p", str(out)], "장면 %d 영상 만들기" % idx)
    say("  장면 %d 완료: %.1f초, %d프레임 (%.0f초 걸림)" % (idx, dur, n, time.time() - t0))
    return out


def build_scenes(ffmpeg):
    step("3단계: FFmpeg로 장면별 움직임(카메라, 빛, 연기, 전환) 만들기")
    BUILD.mkdir(parents=True, exist_ok=True)
    g = lambda name: str(GEN / name)
    clips = []
    ex, ey = EMBER
    flicker = "a='alpha(X,Y)*(0.84+0.10*sin(T*5.3)+0.06*sin(T*13.7+1.1))'"

    # --- 장면 1 -------------------------------------------------------------
    d = SCENE_LEN[0]
    n = int(round(d * FPS))
    inputs = (still(g("s1_background.png")) + looped(g("ember_glow.png"), d) +
              looped(g("s1_noise_a.png"), d) + looped(g("s1_noise_b.png"), d) +
              looped(g("s1_smoke_shape.png"), d) + looped(g("s1_smoke_color.png"), d) +
              looped(g("s1_text.png"), d) + looped(g("s1_text_blur.png"), d))
    graph = (
        "[0:v]" + push(n, "1+0.09*on/%d" % n, ex, ey) + "[bg];"
        # 연기: 노이즈 두 장이 서로 다른 속도로 올라가며 곱해지고, 연기 기둥 모양으로 걸러진다
        "[2:v]format=gray,crop=w=%d:h=%d:x=0:y='min(t*%d,ih-oh)'[na];" % (W // 2, SMOKE_H, SMOKE_SPEED[0]) +
        "[3:v]format=gray,crop=w=%d:h=%d:x='30+28*sin(t*0.45)':y='min(t*%d,ih-oh)'[nb];"
        % (W // 2, SMOKE_H, SMOKE_SPEED[1]) +
        "[na][nb]blend=all_mode=multiply,lut=c0='min(255,val*2.1)'[nn];"
        "[4:v]format=gray[shape];[nn][shape]blend=all_mode=multiply[salpha];"
        "[5:v]format=rgba[scolor];[scolor][salpha]alphamerge,scale=%d:%d[smoke];" % (W, SMOKE_H * 2) +
        "[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':" + flicker + ",scale=1000:700[glow];" +
        reveal(6, 7, "t1", 0.9, 4.3) +
        "[bg][smoke]overlay=x='6*sin(t*0.6)':y=0:format=rgb[v1];"
        "[v1][glow]overlay=x=%d:y=%d:format=rgb[v2];" % (ex - 500, ey - 350) +
        put_text("v2", "t1", 0.9, "v3") + "[v3]null")
    clips.append(render_scene(ffmpeg, 1, inputs, graph))

    # --- 장면 2 -------------------------------------------------------------
    d = SCENE_LEN[1]
    n = int(round(d * FPS))
    # 빛의 고리: 반지름 300에서 점으로 조여 들며 꺼진다 (0.7~2.2초)
    ring = ("st(0,hypot(X-360,Y-360));"
            "st(1,4+296*(1-pow(clip((T-0.7)/1.5,0,1),2)));"
            "st(2,clip((T-0.15)/0.5,0,1)*(1-clip((T-2.05)/0.2,0,1))*(0.75+0.25*clip((T-0.7)/1.5,0,1)));"
            "min(255,255*ld(2)*(0.95*exp(-pow((ld(0)-ld(1))/1.4,2))+0.30*exp(-pow((ld(0)-ld(1))/12,2))))")
    # 새벽의 수평선: 점에서 좌우로 그어지고(2.3~3.0초) 위아래로 열린다 (반 해상도로 계산)
    hz = ("st(0,abs(X-270));st(1,abs(Y-%d));" % (ey // 2) +
          "st(2,620*pow(clip((T-2.3)/0.7,0,1),0.6));"
          "st(3,1.0+3*clip((T-2.6)/1.5,0,1));"
          "st(4,3+560*pow(clip((T-2.7)/3.0,0,1),2.2));"
          "st(5,exp(-pow(max(0,ld(0)-ld(2))/18,2)));"
          "st(6,exp(-pow(ld(0)/(220+520*clip((T-2.7)/3.0,0,1)),2)));"
          "min(255,255*clip((T-2.3)/0.25,0,1)*ld(5)*(exp(-pow(ld(1)/ld(3),2))+0.9*ld(6)*exp(-pow(ld(1)/ld(4),2))))")
    inputs = (still(g("s2_background.png")) + looped(g("ember_glow.png"), d) + blank(720, 720, d) +
              blank(W // 2, H // 2, d) + looped(g("s2_text.png"), d) + looped(g("s2_text_blur.png"), d))
    graph = (
        "[0:v]" + push(n, "1+0.04*on/%d" % n, ex, ey) + "[bg];"
        "[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':" + flicker + ",scale=1000:700"
        + fade_a(None, (0.7, 1.5)) + "[ember];"
        "[2:v]format=rgba,geq=r='255':g='200':b='158':a='" + ring + "'[ring];"
        "[3:v]format=rgba,geq=r='255':g='238':b='210':a='" + hz + "',scale=%d:%d[dawn];" % (W, H) +
        reveal(4, 5, "t2", 2.2, 4.6) +
        "[bg][ember]overlay=x=%d:y=%d:format=rgb[v1];" % (ex - 500, ey - 350) +
        "[v1][ring]overlay=x=%d:y=%d:format=rgb[v2];" % (ex - 360, ey - 360) +
        "[v2][dawn]overlay=0:0:format=rgb[v3];" +
        put_text("v3", "t2", 2.2, "v4") + "[v4]null")
    clips.append(render_scene(ffmpeg, 2, inputs, graph))

    # --- 장면 3 -------------------------------------------------------------
    d = SCENE_LEN[2]
    n = int(round(d * FPS))
    inputs = (still(g("s3_background.png")) + looped(g("s3_rays.png"), d) + looped(g("s3_foliage.png"), d) +
              looped(g("s3_bokeh.png"), d) + looped(g("s3_text.png"), d) + looped(g("s3_text_blur.png"), d) +
              looped(g("s3_cta.png"), d) + looped(g("s3_cta_blur.png"), d))
    graph = (
        "[0:v]" + push(n, "1+0.05*on/%d" % n, SUN[0], SUN[1]) + "[bg];"
        "[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*(0.8+0.2*sin(T*1.7))',"
        "scale=1800:2400[rays];"
        "[2:v]format=rgba[fol];[3:v]format=rgba[bok];" +
        reveal(4, 5, "t3", 0.8) + reveal(6, 7, "t4", 2.6) +
        "[bg][rays]overlay=x='%d+22*t':y=%d:format=rgb[v1];" % (SUN[0] - 1200 - 60, SUN[1] - 200) +
        "[v1][bok]overlay=x='8*sin(t*0.5)':y='-14*t':format=rgb[v2];"
        "[v2][fol]overlay=x='-110+20*t':y='4*sin(t*0.7)':format=rgb[v3];" +
        put_text("v3", "t3", 0.8, "v4") + put_text("v4", "t4", 2.6, "v5") + "[v5]null")
    clips.append(render_scene(ffmpeg, 3, inputs, graph))
    return clips


# ---------------------------------------------------------------------------
# 4) 연결 + 사운드
# ---------------------------------------------------------------------------
def sound_design_inputs():
    """음향 파일이 없을 때의 사운드 디자인 (모두 FFmpeg로 합성).
    0~6.9초 저음 드론과 담배 타는 소리 → 정적 → 7.2초 서브 저음 → 따뜻한 화음."""
    drone = ("(0.16*sin(2*PI*55*t)+0.08*sin(2*PI*82.5*t)+0.05*sin(2*PI*110.3*t))"
             "*(0.85+0.15*sin(2*PI*0.25*t))*min(1,t/1.5)*clip((6.9-t)/1.0,0,1)")
    thump = "0.55*sin(2*PI*44*t)*exp(-3.2*(t-7.2))*gte(t,7.2)"
    env = "clip((t-7.2)/2.2,0,1)*clip((15-t)/1.4,0,1)"
    notes = [(110.0, .100), (164.81, .090), (220.0, .080), (277.18, .068), (329.63, .060), (493.88, .040)]
    pad = "+".join("%.3f*(sin(2*PI*%.2f*t)+sin(2*PI*%.2f*t))" % (a / 2, f - 0.35, f + 0.35) for f, a in notes)
    shimmer = "0.012*(sin(2*PI*659.25*t)+sin(2*PI*830.61*t))*clip((t-10)/2.5,0,1)"
    tone = "%s+%s+(%s+%s)*%s" % (drone, thump, pad, shimmer, env)
    return (["-f", "lavfi", "-t", "%.3f" % TOTAL, "-i", "aevalsrc=exprs='%s':s=48000" % tone,
             "-f", "lavfi", "-t", "%.3f" % TOTAL, "-i", "anoisesrc=color=pink:r=48000:a=0.5:seed=7"],
            "[{0}:a]aformat=channel_layouts=stereo,aecho=0.8:0.6:90|170:0.22|0.15[tone];"
            "[{1}:a]asplit[nz1][nz2];"
            "[nz1]highpass=f=3500,volume='0.05*min(1,t/1)*clip((5.8-t)/1.2,0,1)*(0.7+0.3*sin(t*23))':eval=frame[sizzle];"
            "[nz2]lowpass=f=900,volume='0.55*pow(clip((t-5.4)/1.5,0,1),2)*lt(t,6.9)':eval=frame[riser];"
            "[tone][sizzle][riser]amix=inputs=3:normalize=0,volume=2.0,aformat=channel_layouts=stereo[bed];")


def build_final(ffmpeg, clips):
    step("4단계: 장면 연결(크로스페이드)과 사운드")
    audio = find_audio()
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    v = ("[0:v]settb=AVTB,setpts=PTS-STARTPTS[c0];[1:v]settb=AVTB,setpts=PTS-STARTPTS[c1];"
         "[2:v]settb=AVTB,setpts=PTS-STARTPTS[c2];"
         "[c0][c1]xfade=transition=fade:duration=%.2f:offset=%.2f[x1];"
         "[x1][c2]xfade=transition=fade:duration=%.2f:offset=%.2f,"
         "fade=t=in:st=0:d=0.7,noise=alls=3:allf=t,format=yuv420p[v]"
         % (XFADE, SCENE_START[1], XFADE, SCENE_START[2]))

    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    end = "atrim=0:%.3f,asetpts=PTS-STARTPTS,afade=t=out:st=%.2f:d=1.2,alimiter=limit=0.9[a]" % (TOTAL, TOTAL - 1.2)
    k = len(clips)
    a = ""
    nar, mus = audio["narration"], audio["music"]
    if mus:
        inputs += ["-stream_loop", "-1", "-i", str(mus)]
        a += "[%d:a]%s,volume=%.2f,afade=t=in:d=0.6[bed];" % (k, fmt, MUSIC_VOLUME)
        k += 1
        bed_desc = "배경음악 파일"
    elif SOUND_DESIGN:
        extra, chain = sound_design_inputs()
        inputs += extra
        a += chain.format(k, k + 1)
        k += 2
        bed_desc = "자동 합성 사운드"
    else:
        inputs += ["-f", "lavfi", "-t", "%.3f" % TOTAL, "-i", "anullsrc=r=48000:cl=stereo"]
        a += "[%d:a]%s[bed];" % (k, fmt)
        k += 1
        bed_desc = "무음"
    if nar:
        inputs += ["-i", str(nar)]
        a += ("[%d:a]%s,volume=%.2f,adelay=%d:all=1,apad,asplit=2[nar][key];"
              "[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=500[duck];"
              "[nar][duck]amix=inputs=2:duration=longest:normalize=0,"
              % (k, fmt, NARRATION_VOLUME, int(NARRATION_DELAY * 1000))) + end
        say("  사운드: 내레이션 + " + bed_desc + " (내레이션이 나오면 배경이 자동으로 작아짐)")
    else:
        a += "[bed]apad," + end
        say("  사운드: " + bed_desc)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT / "_making.mp4"
    t0 = time.time()
    run([ffmpeg, "-hide_banner", "-y", *inputs, "-filter_complex", v + ";" + a,
         "-map", "[v]", "-map", "[a]", "-frames:v", str(TOTAL_FRAMES), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-tune", "film", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(tmp)], "최종 영상 합치기")
    try:
        os.replace(tmp, OUT_FILE)
    except PermissionError:
        raise UserError("기존 영상 파일을 덮어쓸 수 없습니다: " + str(OUT_FILE),
                        "영상이 플레이어에서 열려 있으면 닫고 다시 실행하세요. 새 영상은 " + str(tmp) + " 에 있습니다.")
    say("  완료 (%.0f초 걸림): %s" % (time.time() - t0, OUT_FILE))


# ---------------------------------------------------------------------------
# 5) 검증
# ---------------------------------------------------------------------------
def grab(ffmpeg, t):
    p = BUILD / ("check_%05.2f.png" % t)
    run([ffmpeg, "-hide_banner", "-y", "-ss", "%.3f" % t, "-i", str(OUT_FILE), "-frames:v", "1", str(p)],
        "검증용 화면 캡처")
    return Image.open(p).convert("RGB")


def verify(ffmpeg, ffprobe, boxes):
    step("5단계: 결과 검증")
    info = json.loads(run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                           "-count_frames", str(OUT_FILE)], "ffprobe 검사"))
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    fmt_dur = float(info["format"]["duration"])
    num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
    fps = num / den if den else 0
    frames = int(v.get("nb_read_frames", 0))
    v_dur = float(v.get("duration", frames / FPS))
    a_dur = float(a["duration"]) if a else 0.0
    checks = [
        ("전체 길이", "%.3f초" % fmt_dur, abs(fmt_dur - TOTAL) <= 0.05),
        ("영상 길이 / 프레임", "%.3f초 / %d프레임" % (v_dur, frames), abs(v_dur - TOTAL) <= 0.01 and frames == TOTAL_FRAMES),
        ("음향 길이", "%.3f초" % a_dur if a else "음향 트랙 없음", a is not None and abs(a_dur - TOTAL) <= 0.05),
        ("해상도", "%dx%d (세로 9:16)" % (v["width"], v["height"]), (v["width"], v["height"]) == (W, H)),
        ("프레임레이트", "%.2f fps" % fps, abs(fps - FPS) < 0.01),
        ("영상 코덱", "%s (%s)" % (v["codec_name"], v.get("pix_fmt", "")), v["codec_name"] == "h264"),
        ("파일", "MP4, %.1f MB" % (OUT_FILE.stat().st_size / 1e6), True),
    ]
    for label, key, t_on, t_off in SUB_CHECKS:
        box = boxes[key]
        on, off = grab(ffmpeg, t_on).crop(box), grab(ffmpeg, t_off).crop(box)
        diff = ImageStat.Stat(ImageChops.difference(on, off).convert("L")).mean[0]
        checks.append(("%s (%.1f초)" % (label, t_on), "자막 영역 밝기 차이 %.1f" % diff, diff >= 12))
    say("")
    ok_all = True
    for name, val, ok in checks:
        ok_all &= ok
        say("  %s %s : %s" % ("✓" if ok else "✗", name, val))

    tw, th = 270, 480
    sheet = Image.new("RGB", (tw * 3 + 40, th * 2 + 30), (16, 16, 16))
    for i, t in enumerate(PREVIEW_TIMES):
        sheet.paste(grab(ffmpeg, t).resize((tw, th), LANCZOS), (10 + (i % 3) * (tw + 10), 10 + (i // 3) * (th + 10)))
    sheet.save(PREVIEW_FILE, quality=90)
    say("\n  장면 미리보기: " + str(PREVIEW_FILE))
    return ok_all


def main():
    ap = argparse.ArgumentParser(description="15초 금연 공익광고 자동 제작")
    ap.add_argument("--check", action="store_true", help="설치 상태만 점검")
    args = ap.parse_args()
    started = time.time()
    try:
        ffmpeg, ffprobe, light, bold = check_environment()
        if args.check:
            say("\n모든 점검을 통과했습니다. make_video.bat을 실행하면 영상이 만들어집니다.")
            return 0
        boxes = make_layers(light, bold)
        clips = build_scenes(ffmpeg)
        build_final(ffmpeg, clips)
        ok = verify(ffmpeg, ffprobe, boxes)
    except UserError as e:
        say("\n[오류] " + e.problem)
        if e.fix:
            say("[해결 방법] " + e.fix)
        return 1
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        return 1
    say("")
    if ok:
        say("완성! (총 %.0f초) 영상 파일: %s" % (time.time() - started, OUT_FILE))
        return 0
    say("영상은 만들어졌지만 일부 검증 항목(✗)이 기준과 다릅니다. 위 목록을 확인하세요.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
