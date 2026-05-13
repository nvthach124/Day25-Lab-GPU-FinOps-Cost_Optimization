import base64
import io
import json
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "Nguyễn Văn Thạch_GPU_FinOps_Submission" / "notebook" / "gpu_finops_lab.ipynb"
OUTPUT_DIR = ROOT / "Nguyễn Văn Thạch_GPU_FinOps_Submission" / "screenshots"

WIDTH = 1600
MARGIN = 40
BG = "#f5f7fb"
TEXT = "#172033"
MUTED = "#5d6b82"
CARD = "#ffffff"
BORDER = "#d9e1ef"


def load_notebook():
    return json.loads(NOTEBOOK_PATH.read_text())


def get_font(size, mono=False, bold=False):
    candidates = []
    if mono:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
            ]
        )
    elif bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
        )

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


TITLE_FONT = get_font(34, bold=True)
SUBTITLE_FONT = get_font(22)
BODY_FONT = get_font(22)
MONO_FONT = get_font(22, mono=True)
SMALL_FONT = get_font(18)


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def wrap_block(text, width_chars=100):
    wrapped = []
    for line in text.splitlines():
        if not line.strip():
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=width_chars, replace_whitespace=False) or [""])
    return "\n".join(wrapped)


def cell_title(cell):
    src = "".join(cell.get("source", []))
    return src.splitlines()[0].replace("# ", "").strip() if src else "Notebook Output"


def output_text(cell, include_indices=None, exclude_patterns=None):
    exclude_patterns = exclude_patterns or []
    chunks = []
    outputs = cell.get("outputs", [])
    indices = include_indices if include_indices is not None else range(len(outputs))
    for idx in indices:
        if idx >= len(outputs):
            continue
        out = outputs[idx]
        text = ""
        if "text" in out:
            text = "".join(out["text"])
        elif out.get("data", {}).get("text/plain"):
            text = "".join(out["data"]["text/plain"])
        text = strip_ansi(text).strip()
        if not text:
            continue
        if any(pat in text for pat in exclude_patterns):
            continue
        chunks.append(text)
    return "\n\n".join(chunks)


def output_image(cell, image_output_index=None):
    image_outputs = []
    for out in cell.get("outputs", []):
        data = out.get("data", {})
        if "image/png" in data:
            image_outputs.append(data["image/png"])

    if not image_outputs:
        return None

    if image_output_index is None:
        encoded = image_outputs[0]
    else:
        if image_output_index >= len(image_outputs):
            return None
        encoded = image_outputs[image_output_index]

    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")


def multiline_height(draw, text, font, spacing=8):
    if not text:
        return 0
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def resize_to_width(image, max_width):
    if image.width <= max_width:
        return image
    ratio = max_width / image.width
    return image.resize((int(image.width * ratio), int(image.height * ratio)))


def build_snapshot(student_name, student_id, section_title, main_text="", figure=None, footer_note=""):
    dummy = Image.new("RGB", (WIDTH, 400), BG)
    draw = ImageDraw.Draw(dummy)

    header_h = 150
    title_text = section_title
    wrapped_main = wrap_block(main_text, width_chars=100)
    wrapped_footer = wrap_block(footer_note, width_chars=110)

    content_h = 0
    if title_text:
        content_h += multiline_height(draw, title_text, TITLE_FONT, spacing=6) + 20
    if wrapped_main:
        content_h += multiline_height(draw, wrapped_main, MONO_FONT, spacing=10) + 30
    if figure is not None:
        fig = resize_to_width(figure, WIDTH - 2 * MARGIN - 40)
        content_h += fig.height + 30
    else:
        fig = None
    if wrapped_footer:
        content_h += multiline_height(draw, wrapped_footer, SUBTITLE_FONT, spacing=8) + 20

    total_h = header_h + content_h + 120
    image = Image.new("RGB", (WIDTH, total_h), BG)
    draw = ImageDraw.Draw(image)

    for y in range(header_h):
        ratio = y / max(header_h - 1, 1)
        r = int(102 * (1 - ratio) + 118 * ratio)
        g = int(126 * (1 - ratio) + 75 * ratio)
        b = int(234 * (1 - ratio) + 162 * ratio)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))

    draw.text((MARGIN, 28), "GPU FinOps Lab - Student Information", font=TITLE_FONT, fill="white")
    draw.text(
        (MARGIN, 84),
        f"Ho va ten: {student_name} | MSSV: {student_id}",
        font=SUBTITLE_FONT,
        fill="white",
    )

    card_x0 = MARGIN
    card_x1 = WIDTH - MARGIN
    card_y0 = header_h - 26
    card_y1 = total_h - MARGIN
    draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=24, fill=CARD, outline=BORDER, width=2)

    x = card_x0 + 30
    y = card_y0 + 26
    draw.text((x, y), title_text, font=TITLE_FONT, fill=TEXT)
    y += multiline_height(draw, title_text, TITLE_FONT, spacing=6) + 20

    if wrapped_main:
        draw.multiline_text((x, y), wrapped_main, font=MONO_FONT, fill=TEXT, spacing=10)
        y += multiline_height(draw, wrapped_main, MONO_FONT, spacing=10) + 30

    if fig is not None:
        image.paste(fig, (x, y))
        y += fig.height + 30

    if wrapped_footer:
        draw.multiline_text((x, y), wrapped_footer, font=SUBTITLE_FONT, fill=MUTED, spacing=8)

    return image


def main():
    nb = load_notebook()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    student_src = "".join(nb["cells"][2]["source"])
    name_match = re.search(r'STUDENT_NAME\s*=\s*"([^"]+)"', student_src)
    id_match = re.search(r'STUDENT_ID\s*=\s*"([^"]+)"', student_src)
    student_name = name_match.group(1) if name_match else "Nguyen Van A"
    student_id = id_match.group(1) if id_match else "MSSV123456"

    shots = [
        ("part1_cluster_monitoring.png", 5, None, None, None),
        ("part1_cluster_metrics.png", 6, None, None, None),
        ("part2_workload_submission.png", 8, None, None, None),
        ("part2_billing_summary.png", 9, None, None, None),
        ("part3_spot_pricing.png", 11, None, None, None),
        ("part3_spot_request.png", 12, None, None, None),
        ("part3_spot_preemption.png", 13, None, None, None),
        ("part4_autoscaler_policy.png", 15, None, None, None),
        ("part4_autoscaler_evaluation.png", 16, None, None, None),
        ("part5_cost_snapshots.png", 18, None, None, None),
        ("part5_waste_report.png", 19, None, None, None),
        ("part5_recommendations.png", 20, None, None, None),
        ("part5_dashboard.png", 21, None, None, None),
        ("part6_cost_breakdown_viz.png", 23, [1], None, "Visualization output saved as finops_cost_breakdown.png."),
        ("part6_timeseries_viz.png", 24, [], None, "Time-series visualization from cost snapshots."),
        ("part7_full_workflow.png", 26, None, None, None),
        ("part8_gpu_detection.png", 28, None, None, None),
        ("part8_gpu_metrics_diagnostic.png", 29, None, None, None),
        ("part8_fp32_summary.png", 31, None, None, None),
        ("part8_amp_summary.png", 32, [0, 2], None, None),
        ("part8_fp32_vs_amp_comparison.png", 33, [0], None, "Comparison chart saved as real_gpu_comparison.png."),
        ("part8_real_gpu_cost_report.png", 34, None, None, None),
        ("part85_multi_gpu_analysis.png", 37, [0, 2], None, "Chart saved as multi_gpu_scaling.png."),
        ("part85_project_forecast.png", 38, [0, 2], None, "Chart saved as project_forecast.png."),
        ("part85_optimization_analysis.png", 39, [0, 2], None, "Chart saved as optimization_roadmap.png."),
        ("part85_integrated_dashboard.png", 40, [0, 2], None, "Chart saved as advanced_finops_dashboard.png."),
        ("part85_challenge_strategy.png", 41, None, None, None),
    ]

    for filename, cell_idx, text_indices, image_idx, footer in shots:
        cell = nb["cells"][cell_idx]
        title = cell_title(cell)
        text = output_text(cell, include_indices=text_indices)
        figure = output_image(cell, image_output_index=image_idx)
        shot = build_snapshot(
            student_name=student_name,
            student_id=student_id,
            section_title=title,
            main_text=text,
            figure=figure,
            footer_note=footer or "",
        )
        shot.save(OUTPUT_DIR / filename, quality=95)


if __name__ == "__main__":
    main()
