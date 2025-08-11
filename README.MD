Publish Pipeline — README

A Python pipeline to convert a manuscript into a validated EPUB and generate ebook and print-ready A8 covers. Produces artifacts ready for upload to ebook stores and print-on-demand services.

This repository contains:

- publish_pipeline.py — main pipeline script
- templates/ — CSS and optional cover template files
- sample metadata.json — example metadata format
- (optional) Dockerfile — to create a reproducible environment (if included)

Quick overview

- Input: manuscript (.docx, .md, .txt) plus optional front/legal/back snippets and metadata (JSON).
- Output: EPUB, ebook cover (JPEG), print-ready A8 wrap (PDF), epubcheck report, and a final publish_report.json.
- Tools used: Pandoc, ImageMagick, epubcheck, Pillow (Python), and standard system utilities.

Prerequisites

- Python 3.9+
- Pandoc (CLI)
- ImageMagick (convert, identify)
- Java (for epubcheck)
- epubcheck.jar (download from https://github.com/w3c/epubcheck/releases)
- Recommended: TTF font(s) installed, e.g., DejaVu Sans

Python dependencies
Install Python packages:
pip install -r requirements.txt
(If a requirements.txt is not present, run:)
pip install python-frontmatter markdownify python-docx PyYAML pillow

Usage

Prepare metadata.json (example)
{
  "title": "My Tiny A8 Book",
  "author": "Jane Doe",
  "page_count": 120
}

Run the pipeline
python publish_pipeline.py 
  --input manuscript.docx 
  --metadata metadata.json 
  --front front.md 
  --legal legal.md 
  --back back.md 
  --outdir ./output 
  --dpi 300 
  --font /path/to/font.ttf 
  --epubcheck_jar /path/to/epubcheck.jar

Outputs (in ./output)

- book.epub — generated EPUB
- cover_ebook.jpg — ebook cover (Amazon-friendly long side 1600 px, A8 aspect)
- cover_print.pdf — print-ready A8 full-wrap PDF (front+spine+back) with bleed
- epubcheck_report.json — validation report (if epubcheck available)
- publish_report.json — summary report referencing artifact paths

Options and flags

- --input: Manuscript file (.docx, .md, .txt)
- --metadata: JSON metadata file (title, author, page_count, etc.)
- --front / --legal / --back: Optional snippets (md/docx/txt)
- --outdir: Output directory (required)
- --dpi: DPI for print cover generation (default 300)
- --bleed: Bleed in mm (default 3 mm)
- --title / --author: Override metadata values
- --page_count: Page count for spine calculation (can override metadata)
- --font: Path to TTF font for covers
- --css: CSS file for EPUB styling
- --epubcheck_jar: Path to epubcheck jar (optional)
- --thickness_per_page: Paper thickness mm per page for spine calc (default small estimate)

A8 specifics

- A8 dimensions: 52 mm x 74 mm
- The script generates:- ebook cover at Amazon-recommended long side (1600 px) while keeping A8 aspect ratio
- print wrap PDF sized for A8 with configurable bleed and spine width calculation


- Note: Verify that your chosen POD provider (KDP or other) supports A8 trim. KDP may not support arbitrary custom sizes.

Validation and QA

- epubcheck (Java) is used for EPUB validation. Provide path to epubcheck.jar via --epubcheck_jar.
- Inspect generated cover_print.pdf in a PDF viewer or use a printed proof to confirm layout and legibility for A8 size.
- For ebook previews use an EPUB reader or Kindle Previewer if you convert to KPF.

Customization and extension points

- Professional covers: Replace the generated cover with a designer-generated image or integrate a template engine (Photoshop PSD, Canva API, or Inkscape SVG templates).
- Fixed-layout EPUB/KPF: For books that must preserve exact pagination at A8 size, implement fixed-layout EPUB or use publisher tools (InDesign → EPUB/KPF).
- EPUB → KPF: Integrate Kindle Previewer CLI or vendor tools to produce KPF if required by Kindle.
- CI/Docker: Use a Dockerfile to create a reproducible runner with Pandoc, ImageMagick, Java, and Python dependencies.

Docker (optional)
Create a Dockerfile that installs:

- pandoc
- imagemagick
- openjdk
- python and pip packages
- epubcheck
Mount your repository and run the script inside the container to ensure consistent environment.

Security & licensing notes

- Embed fonts only if licensing allows embedding for distribution.
- Confirm you have rights to use any images, fonts, and third-party content included in the book or cover.
- This script does not perform publishing to KDP or any store. Automating a publisher’s web UI may violate their terms of service — review terms before automating uploads.

Troubleshooting

- Pandoc conversion errors: ensure input file is valid; try converting to markdown manually to debug.
- epubcheck errors: open epubcheck_report.json to see details; fix issues in HTML/CSS or metadata.
- Cover text too small on print: increase font size in the print cover generation parameters or adjust DPI.
- Spine width zero or tiny: ensure --page_count is set correctly; small A8 books may have very thin spines where spine text is impractical.

Contributing

- Contributions welcome. Create issues or PRs to:- improve cover templates (SVG/Inkscape)
- add KPF conversion
- containerize the pipeline
- add unit tests and sample files

License

- Add your chosen license file (LICENSE) to the repository.

Contact

- For support or customizations, open an issue describing your input formats, desired outputs, and any specific design or printer requirements.


End of README.
