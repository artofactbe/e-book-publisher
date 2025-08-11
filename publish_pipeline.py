#!/usr/bin/env python3
"""
publish_pipeline.py

Usage example:
  python publish_pipeline.py \
    --input manuscript.docx \
    --metadata metadata.json \
    --front front.md \
    --legal legal.md \
    --back back.md \
    --outdir output \
    --format A8 \
    --dpi 300

Produces:
  output/
    book.epub
    cover_ebook.jpg
    cover_print.pdf
    validation_report.json
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ---------- Configuration defaults ----------
DEFAULT_DPI = 300
AMAZON_LONG_SIDE_PX = 1600  # recommended min long side for ebook cover
A8_MM = (52.0, 74.0)  # width x height in mm
DEFAULT_BLEED_MM = 3.0
# paper thickness (mm per page) for spine - approximate; adjust per printer spec
DEFAULT_PAPER_THICKNESS_MM_PER_PAGE = 0.0025

# Paths to external tools and jars (adjust if installed in custom locations)
PANDOC_CMD = "pandoc"
EPUBCHECK_JAR = "epubcheck.jar"  # put path to epubcheck jar or leave to skip validation
IMAGEMAGICK_CONVERT = "convert"
IMAGEMAGICK_IDENTIFY = "identify"

# Default font for cover generation; change to a path to a TTF if needed
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ---------- Utility functions ----------
def run_cmd(cmd, capture_output=False, check=True):
    print("RUN:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=capture_output, text=True)
    if check and res.returncode != 0:
        print("Command failed (exit {}). stdout:".format(res.returncode))
        print(res.stdout)
        print("stderr:")
        print(res.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return res


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def compute_spine_width_mm(page_count: int, thickness_per_page_mm: float) -> float:
    return page_count * thickness_per_page_mm


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ---------- Content merging ----------
def convert_to_markdown_if_needed(input_path: Path, out_md: Path):
    """
    Convert DOCX/TXT to Markdown using pandoc if needed. If input already .md, copy.
    """
    ext = input_path.suffix.lower()
    if ext == ".md":
        out_md.write_bytes(input_path.read_bytes())
        return
    if ext in (".docx", ".doc", ".odt", ".txt"):
        cmd = [PANDOC_CMD, str(input_path), "-f", ext.lstrip("."), "-t", "markdown", "-o", str(out_md)]
        run_cmd(cmd)
        return
    raise ValueError(f"Unsupported manuscript extension: {ext}")


def merge_markdown(parts: list, out_md: Path):
    """
    Concatenate markdown parts with page break markers for print where appropriate.
    """
    with out_md.open("w", encoding="utf-8") as f:
        for i, p in enumerate(parts):
            if p and p.exists():
                f.write(p.read_text(encoding="utf-8"))
                f.write("\n\n<div style=\"page-break-after: always;\"></div>\n\n")
    print("Merged markdown into", out_md)


# ---------- Cover generation ----------
def generate_ebook_cover(title: str, author: str, aspect_w: int, aspect_h: int, long_side_px: int,
                         out_path: Path, font_path: Optional[str] = None):
    """
    Generate ebook cover JPEG maintaining aspect ratio but scaling long side to long_side_px.
    aspect_w/aspect_h define aspect ratio (e.g., A8 mm ratio).
    """
    # compute target pixel dimensions using aspect ratio and long side px
    if aspect_h >= aspect_w:
        # height is long side
        height = long_side_px
        width = int(round(height * (aspect_w / aspect_h)))
    else:
        width = long_side_px
        height = int(round(width * (aspect_h / aspect_w)))

    print(f"Generating ebook cover at {width}x{height}px -> {out_path}")

    img = Image.new("RGB", (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Title text
    font_title = ImageFont.truetype(font_path or DEFAULT_FONT, size=max(28, int(height * 0.08)))
    font_author = ImageFont.truetype(font_path or DEFAULT_FONT, size=max(18, int(height * 0.04)))

    # Draw simple centered layout
    title_lines = title.strip().split("\n")
    y = int(height * 0.30)
    for line in title_lines:
        w, h = draw.textsize(line, font=font_title)
        draw.text(((width - w) / 2, y), line, font=font_title, fill=(20, 20, 20))
        y += h + 10

    # Author near bottom
    author_text = f"By {author}"
    w, h = draw.textsize(author_text, font=font_author)
    draw.text(((width - w) / 2, height - int(height * 0.12)), author_text, font=font_author, fill=(60, 60, 60))

    # Save as JPEG high quality
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="JPEG", quality=90)
    print("Ebook cover saved to", out_path)


def generate_print_wrap_cover_a8(title: str, author: str, page_count: int, out_pdf: Path,
                                  width_mm: float = A8_MM[0], height_mm: float = A8_MM[1],
                                  bleed_mm: float = DEFAULT_BLEED_MM, dpi: int = DEFAULT_DPI,
                                  thickness_per_page_mm: float = DEFAULT_PAPER_THICKNESS_MM_PER_PAGE,
                                  font_path: Optional[str] = None):
    """
    Generate a simple front+back+spine wrap for A8 in a single PDF page (print-ready).
    This is a simplified generator: spine has solid color and title vertically.
    """
    # compute spine width
    spine_mm = compute_spine_width_mm(page_count, thickness_per_page_mm)
    print(f"Computed spine width: {spine_mm:.3f} mm for {page_count} pages")

    # full cover dimensions (mm)
    full_w_mm = width_mm * 2 + spine_mm + 2 * bleed_mm
    full_h_mm = height_mm + 2 * bleed_mm

    # convert to pixels
    full_w_px = mm_to_px(full_w_mm, dpi)
    full_h_px = mm_to_px(full_h_mm, dpi)

    print(f"Creating print cover canvas {full_w_px}px x {full_h_px}px (dpi {dpi}) -> {out_pdf}")

    img = Image.new("RGB", (full_w_px, full_h_px), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # calculate regions
    left_x = 0
    back_x = left_x + mm_to_px(bleed_mm, dpi)
    back_x += 0  # we will compute front/back start precisely
    # We'll compute offsets precisely:
    bleed_px = mm_to_px(bleed_mm, dpi)
    page_w_px = mm_to_px(width_mm, dpi)
    page_h_px = mm_to_px(height_mm, dpi)
    spine_px = mm_to_px(spine_mm, dpi)

    # positions: left to right -> back cover, spine, front cover (including bleed around)
    back_cover_x = 0 + bleed_px
    spine_x = back_cover_x + page_w_px
    front_cover_x = spine_x + spine_px

    # fill back cover
    draw.rectangle([back_cover_x, bleed_px, back_cover_x + page_w_px, bleed_px + page_h_px], fill=(230, 230, 250))
    # spine
    draw.rectangle([spine_x, bleed_px, spine_x + spine_px, bleed_px + page_h_px], fill=(200, 200, 200))
    # front cover
    draw.rectangle([front_cover_x, bleed_px, front_cover_x + page_w_px, bleed_px + page_h_px], fill=(245, 245, 245))

    # Add text on front cover
    font_title = ImageFont.truetype(font_path or DEFAULT_FONT, size=max(12, int(page_h_px * 0.12)))
    font_author = ImageFont.truetype(font_path or DEFAULT_FONT, size=max(10, int(page_h_px * 0.07)))

    # Title centered on front cover
    title_lines = title.strip().split("\n")
    y_start = bleed_px + int(page_h_px * 0.18)
    for line in title_lines:
        w, h = draw.textsize(line, font=font_title)
        x = front_cover_x + (page_w_px - w) / 2
        draw.text((x, y_start), line, font=font_title, fill=(20, 20, 20))
        y_start += h + 6

    # Author near bottom of front cover
    author_text = f"By {author}"
    w, h = draw.textsize(author_text, font=font_author)
    ax = front_cover_x + (page_w_px - w) / 2
    ay = bleed_px + page_h_px - int(page_h_px * 0.12)
    draw.text((ax, ay), author_text, font=font_author, fill=(60, 60, 60))

    # Add spine text vertically (simple)
    spine_font = ImageFont.truetype(font_path or DEFAULT_FONT, size=max(8, int(spine_px * 0.7)))
    spine_text = title.strip()
    # rotate spine text and draw centered
    spine_img = Image.new("RGBA", (spine_px, page_h_px), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spine_img)
    sw, sh = sd.textsize(spine_text, font=spine_font)
    sd.text(((spine_px - sw) / 2, (page_h_px - sh) / 2), spine_text, font=spine_font, fill=(20, 20, 20))
    spine_img = spine_img.rotate(90, expand=1)
    # paste rotated spine into spine area
    sx = spine_x
    sy = bleed_px
    img.paste(spine_img.crop((0, 0, spine_px, page_h_px)), (sx, sy), spine_img.crop((0, 0, spine_px, page_h_px)))

    # Save as PDF
    out_dir = out_pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_png = out_dir / "temp_print_cover.png"
    img.save(temp_png, format="PNG")
    # Convert PNG -> PDF at correct DPI using ImageMagick to ensure PDF size matches
    cmd = [IMAGEMAGICK_CONVERT, str(temp_png), "-density", str(dpi), str(out_pdf)]
    run_cmd(cmd)
    temp_png.unlink(missing_ok=True)
    print("Print cover generated:", out_pdf)


# ---------- Conversion to EPUB ----------
def generate_epub_from_markdown(md_path: Path, cover_path: Path, metadata_path: Path, css_path: Optional[Path],
                                out_epub: Path):
    """
    Use pandoc to generate EPUB from merged markdown.
    metadata_path is JSON or YAML accepted by pandoc --metadata-file
    """
    cmd = [PANDOC_CMD, str(md_path), "-o", str(out_epub), "--to", "epub3"]
    if cover_path and cover_path.exists():
        cmd += ["--epub-cover-image", str(cover_path)]
    if css_path and css_path.exists():
        cmd += ["--css", str(css_path)]
    if metadata_path and metadata_path.exists():
        cmd += ["--metadata-file", str(metadata_path)]
    # Add toc
    cmd += ["--toc", "--toc-depth=2"]
    run_cmd(cmd)
    print("EPUB generated:", out_epub)


# ---------- EPUB validation ----------
def validate_epub(epub_path: Path, epubcheck_jar: Optional[str], report_out: Path):
    """
    Validate EPUB using epubcheck; writes JSON report.
    If epubcheck_jar is not provided or missing, skip validation.
    """
    report = {"epub": str(epub_path), "validated": False, "errors": None}
    if not epubcheck_jar or not Path(epubcheck_jar).exists():
        print("epubcheck.jar not found; skipping validation. Set EPUBCHECK_JAR path to enable.")
        report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return

    cmd = ["java", "-jar", epubcheck_jar, str(epub_path), "-mode", "expensive", "-out", str(report_out)]
    run_cmd(cmd)
    # epubcheck wrote report_out; attempt to read it
    try:
        j = json.loads(report_out.read_text(encoding="utf-8"))
        j["validated"] = True
        report_out.write_text(json.dumps(j, indent=2), encoding="utf-8")
        print("epubcheck report written to", report_out)
    except Exception as ex:
        print("Could not parse epubcheck output:", ex)
        report_out.write_text(json.dumps({"epub": str(epub_path), "validated": True, "raw_output": None}, indent=2),
                              encoding="utf-8")


# ---------- Helpers ----------
def count_pages_in_epub(epub_path: Path) -> int:
    # Not exact; EPUB is reflowable. For print paperback page count you should use source doc pagination.
    # As a fallback return an approximate page count based on word count.
    # Here we return 0 as placeholder to require page_count param for print.
    return 0


# ---------- Main pipeline ----------
def run_pipeline(args):
    in_path = Path(args.input).resolve()
    out_dir = Path(args.outdir).resolve()
    ensure_dir(out_dir)
    tmp = Path(tempfile.mkdtemp(prefix="publish_"))
    print("Working dir:", tmp)

    # convert inputs to markdown
    manuscript_md = tmp / "manuscript.md"
    convert_to_markdown_if_needed(in_path, manuscript_md)

    # optional parts
    front_md = Path(args.front).resolve() if args.front else None
    legal_md = Path(args.legal).resolve() if args.legal else None
    back_md = Path(args.back).resolve() if args.back else None

    # merge
    merged_md = tmp / "full_book.md"
    parts = []
    # front
    parts.append(front_md if front_md and front_md.exists() else None)
    parts.append(manuscript_md)
    parts.append(legal_md if legal_md and legal_md.exists() else None)
    parts.append(back_md if back_md and back_md.exists() else None)
    # filter None
    parts = [p for p in parts if p]
    merge_markdown(parts, merged_md)

    # load metadata
    metadata = {}
    if args.metadata:
        metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    title = metadata.get("title", args.title or "Untitled")
    author = metadata.get("author", args.author or "Unknown Author")
    page_count = int(metadata.get("page_count", args.page_count or 0))

    # compute A8 aspect ratio (use mm)
    aspect_w_mm, aspect_h_mm = A8_MM
    # generate ebook cover using A8 aspect but scaled to AMAZON_LONG_SIDE_PX
    ebook_cover = out_dir / "cover_ebook.jpg"
    generate_ebook_cover(title=title, author=author, aspect_w=int(aspect_w_mm), aspect_h=int(aspect_h_mm),
                         long_side_px=AMAZON_LONG_SIDE_PX, out_path=ebook_cover, font_path=args.font)

    # generate print cover PDF for A8
    print_cover_pdf = out_dir / "cover_print.pdf"
    generate_print_wrap_cover_a8(title=title, author=author, page_count=page_count, out_pdf=print_cover_pdf,
                                 width_mm=aspect_w_mm, height_mm=aspect_h_mm, bleed_mm=args.bleed, dpi=args.dpi,
                                 thickness_per_page_mm=args.thickness_per_page, font_path=args.font)

    # generate epub via pandoc
    epub_out = out_dir / "book.epub"
    css_path = Path(args.css).resolve() if args.css else None
    metadata_path = Path(args.metadata).resolve() if args.metadata else None
    generate_epub_from_markdown(merged_md, ebook_cover, metadata_path, css_path, epub_out)

    # validate epub
    report_out = out_dir / "epubcheck_report.json"
    validate_epub(epub_out, args.epubcheck_jar, report_out)

    # finalize
    result = {
        "epub": str(epub_out),
        "ebook_cover": str(ebook_cover),
        "print_cover_pdf": str(print_cover_pdf),
        "validation_report": str(report_out)
    }
    final_report = out_dir / "publish_report.json"
    final_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Pipeline finished. Report:", final_report)


# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Pipeline: manuscript -> EPUB + covers (A8-aware)")
    p.add_argument("--input", required=True, help="Manuscript file: .docx, .md, or .txt")
    p.add_argument("--metadata", required=False, help="JSON metadata file (title, author, page_count, etc.)")
    p.add_argument("--front", required=False, help="Front matter snippet (md/docx/txt)")
    p.add_argument("--legal", required=False, help="Legal/copyright snippet (md/docx/txt)")
    p.add_argument("--back", required=False, help="Back matter snippet (md/docx/txt)")
    p.add_argument("--outdir", required=True, help="Output directory")
    p.add_argument("--dpi", default=DEFAULT_DPI, type=int, help="DPI for print cover generation (default 300)")
    p.add_argument("--bleed", default=DEFAULT_BLEED_MM, type=float, help="Bleed in mm (default 3 mm)")
    p.add_argument("--title", default=None, help="Title override")
    p.add_argument("--author", default=None, help="Author override")
    p.add_argument("--page_count", default=0, type=int, help="Page count for spine calculation")
    p.add_argument("--font", default=None, help="Path to TTF font for covers")
    p.add_argument("--css", default=None, help="Path to CSS file for EPUB styling")
    p.add_argument("--epubcheck_jar", default=EPUBCHECK_JAR, help="Path to epubcheck jar (optional)")
    p.add_argument("--thickness_per_page", default=DEFAULT_PAPER_THICKNESS_MM_PER_PAGE, type=float,
                   help="Paper thickness mm per page for spine calc (default small estimate)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run_pipeline(args)
    except Exception as e:
        print("ERROR:", e)
        sys.exit(2)
