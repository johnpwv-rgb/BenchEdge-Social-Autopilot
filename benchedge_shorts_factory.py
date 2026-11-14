#!/usr/bin/env python3
"""
BenchEdge Systems — 9:16 Vertical Shorts & TikTok Video Factory
Generates 1080x1920 MP4 videos from BenchEdge diagnostic & manifest data using Pillow + FFmpeg.
"""

import argparse
import os
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
BG_DARK = (15, 23, 42)        # #0F172A Slate Navy
CARD_BG = (30, 41, 59)        # #1E293B Slate Card
TEAL = (20, 184, 166)         # #14B8A6 Precision Teal
AMBER = (245, 158, 11)        # #F59E0B Amber Alert
WHITE = (248, 250, 252)       # #F8FAFC Crisp White
MUTED = (148, 163, 184)       # #94A3B8 Slate Muted

DEFAULT_CAMPAIGNS = {
    "CAMP-02": {
        "tag": "60-SEC USB-C TRIAGE",
        "slides": [
            {
                "headline": "DEAD MACBOOK AIR?",
                "subhead": "8-Second Test (Zero Screws)",
                "metric": "5.02V @ 0.02A",
                "body": "Plug an FNIRSI FNB58 meter into an Anker 100W GaN brick. Stuck at 5V / 0.02A means a shorted CD3217 USB-C controller.",
                "accent": AMBER,
            },
            {
                "headline": "HEALTHY BOARD CHECK",
                "subhead": "Even With a Black Screen",
                "metric": "20.0V @ 2.15A",
                "body": "If the meter jumps to 20V / 2.15A (43W), the logic board is alive. Swap the display from MobileSentrix and pocket the margin.",
                "accent": TEAL,
            },
            {
                "headline": "STOP OVERBIDDING",
                "subhead": "BenchEdge Shovel Suite",
                "metric": "FREE FAULT SHEET",
                "body": "Grab our 60-Second USB-C Fault Lookup Sheet and Manifest Bid-Cap Calculator at the link in bio.",
                "accent": TEAL,
            },
        ],
    },
    "CAMP-06": {
        "tag": "MICRO-SOLDERING ROI",
        "slides": [
            {
                "headline": "$75 SALVAGE SWITCH",
                "subhead": "Why Buyers Walk Away",
                "metric": "5.0V @ 0.08A",
                "body": "Kids jam third-party docks into Switch OLED ports and short the $12.50 M92T36 power IC.",
                "accent": AMBER,
            },
            {
                "headline": "$25.99 PINECIL V2 FIX",
                "subhead": "35-Minute Bench Repair",
                "metric": "+$137 NET PROFIT",
                "body": "Reflow or swap the M92T36 IC and USB-C port with a PINE64 Pinecil V2 to turn a $75 brick into a $235 Grade A/B console.",
                "accent": TEAL,
            },
            {
                "headline": "TIER 2 REPAIR KIT",
                "subhead": "Code: FOUNDING15 (15% Off)",
                "metric": "LINK IN BIO",
                "body": "Get the FNIRSI FNB58, Anker 100W GaN, Pinecil V2, and 64-Bit Tool Roll pre-configured for pallet flipping.",
                "accent": TEAL,
            },
        ],
    },
}


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text(draw, text: str, font, max_width: int):
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def render_slide(tag: str, slide: dict, slide_idx: int, total_slides: int, out_png: str):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    f_tag = load_font(34, bold=True)
    f_head = load_font(74, bold=True)
    f_sub = load_font(44, bold=False)
    f_metric = load_font(86, bold=True)
    f_body = load_font(42, bold=False)
    f_footer = load_font(32, bold=True)

    accent = slide.get("accent", TEAL)

    # Top brand header bar
    draw.rectangle([70, 120, WIDTH - 70, 210], fill=CARD_BG, outline=accent, width=3)
    draw.text((105, 145), f"BENCHEDGE SYSTEMS  |  {tag}", font=f_tag, fill=accent)

    # Progress indicator
    draw.text((WIDTH - 220, 145), f"{slide_idx + 1} / {total_slides}", font=f_tag, fill=MUTED)

    # Headline
    y = 300
    for line in wrap_text(draw, slide["headline"], f_head, WIDTH - 140):
        draw.text((70, y), line, font=f_head, fill=WHITE)
        y += 92

    # Subhead
    y += 16
    draw.text((70, y), slide["subhead"], font=f_sub, fill=MUTED)
    y += 100

    # Big Metric Callout Box
    draw.rectangle([70, y, WIDTH - 70, y + 210], fill=CARD_BG, outline=accent, width=5)
    bbox = draw.textbbox((0, 0), slide["metric"], font=f_metric)
    mw = bbox[2] - bbox[0]
    draw.text(((WIDTH - mw) // 2, y + 55), slide["metric"], font=f_metric, fill=accent)
    y += 280

    # Body explanation
    for line in wrap_text(draw, slide["body"], f_body, WIDTH - 140):
        draw.text((70, y), line, font=f_body, fill=WHITE)
        y += 62

    # Bottom safe-zone CTA bar
    draw.rectangle([70, HEIGHT - 230, WIDTH - 70, HEIGHT - 140], fill=accent)
    cta = "BENCHEDGE.SYSTEMS  |  LINK IN BIO"
    cbbox = draw.textbbox((0, 0), cta, font=f_footer)
    cw = cbbox[2] - cbbox[0]
    draw.text(((WIDTH - cw) // 2, HEIGHT - 203), cta, font=f_footer, fill=BG_DARK)

    img.save(out_png)


def build_video(campaign_id: str, out_mp4: str, seconds_per_slide: int = 5):
    data = DEFAULT_CAMPAIGNS.get(campaign_id, DEFAULT_CAMPAIGNS["CAMP-02"])
    slides = data["slides"]
    with tempfile.TemporaryDirectory() as tmpdir:
        concat_file = os.path.join(tmpdir, "slides.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for idx, slide in enumerate(slides):
                png_path = os.path.join(tmpdir, f"slide_{idx}.png")
                render_slide(data["tag"], slide, idx, len(slides), png_path)
                f.write(f"file '{png_path}'\n")
                f.write(f"duration {seconds_per_slide}\n")
            f.write(f"file '{os.path.join(tmpdir, f'slide_{len(slides)-1}.png')}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
            "-crf", "20", "-movflags", "+faststart", out_mp4
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated 9:16 vertical video ({len(slides) * seconds_per_slide}s): {out_mp4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 9:16 vertical Shorts/TikTok MP4s for BenchEdge Systems.")
    parser.add_argument("--campaign", default="CAMP-02", help="Campaign ID (e.g., CAMP-02, CAMP-06)")
    parser.add_argument("--out", default="benchedge_short.mp4", help="Output MP4 file path")
    parser.add_argument("--duration", type=int, default=5, help="Seconds per slide")
    args = parser.parse_args()
    build_video(args.campaign, args.out, args.duration)