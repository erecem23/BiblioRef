"""Build the demonstration figure from one run written by ``run_demo.py``.

(a) the PDF page where the bibliography zone starts, (b) the first extracted
reference records and (c) the zone-level diagnostics, all read from the run's
``result.json``. Requires matplotlib and pypdfium2.

    python examples/make_figure.py thesis.pdf demo_output/pdfium_run1 --out figure.png
"""
from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402

N_RECORDS = 5
ZONE_FIELDS = (
    ("heading", "Heading"),
    ("start_page", "Start page"),
    ("end_page", "End page"),
    ("style", "Style"),
    ("n_segments", "Records"),
    ("numeric_first_marker", "First marker"),
    ("numeric_last_marker", "Last marker"),
    ("hanging_indent_detected", "Hanging indent"),
    ("start_margin", "Start margin (pt)"),
    ("continuation_margin", "Continuation margin (pt)"),
    ("termination_reason", "Termination"),
    ("combined_confidence_label", "Confidence label"),
    ("zone_completeness", "Completeness"),
)


def clean(text: str) -> str:
    return " ".join(str(text).replace("­", "-").split())


def render_zone_start(pdf: Path, page_number: int, heading: str, height: float, scale: float = 2.0):
    """Render the page where the zone starts, cropped from its heading downwards."""
    document = pdfium.PdfDocument(str(pdf))
    try:
        page = document[page_number - 1]
        page_height = page.get_height()
        top = page_height
        textpage = page.get_textpage()
        searcher = textpage.search(heading.split()[-1][:8], match_case=False)
        found = searcher.get_next()
        if found:
            _, _, _, char_top = textpage.get_charbox(found[0])
            top = min(page_height, char_top + 18)
        image = page.render(scale=scale).to_pil()
    finally:
        document.close()
    y0 = int((page_height - top) * scale)
    y1 = min(image.height, y0 + int(page_height * height * scale))
    x0, x1 = int(image.width * 0.06), int(image.width * 0.92)
    return image.crop((x0, y0, x1, y1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("figure.png"))
    parser.add_argument("--crop", type=float, default=0.45, help="fraction of the page height shown in panel (a)")
    args = parser.parse_args(argv)

    result = json.loads((args.run_dir / "result.json").read_text(encoding="utf-8"))
    zone = result["zones"][0]
    records = [r for r in result["records"] if r.get("zone_id") == zone["zone_id"]][:N_RECORDS]

    page = render_zone_start(args.pdf, int(zone["start_page"]), clean(zone["heading"]), args.crop)

    fig = plt.figure(figsize=(12, 7.2))
    grid = fig.add_gridspec(2, 2, width_ratios=[1, 1.35], height_ratios=[1.45, 1], wspace=0.04, hspace=0.12)

    ax_page = fig.add_subplot(grid[:, 0])
    ax_page.imshow(page)
    ax_page.set_axis_off()
    ax_page.set_title(f"(a) Source PDF, page {zone['start_page']} (excerpt)", loc="left", fontsize=10)

    ax_records = fig.add_subplot(grid[0, 1])
    ax_records.set_axis_off()
    ax_records.set_title(f"(b) First {len(records)} of {zone['n_segments']} extracted records (references.csv)", loc="left", fontsize=10)
    lines = []
    for record in records:
        pages = record["reference_start_page"]
        if record["reference_end_page"] != pages:
            pages = f"{pages}-{record['reference_end_page']}"
        wrapped = textwrap.wrap(clean(record["reference_text"]), width=82)
        lines.append(f"#{record['ref_in_zone']}  p. {pages}")
        lines += [f"    {line}" for line in wrapped] + [""]
    ax_records.text(0, 1, "\n".join(lines).rstrip(), va="top", ha="left", fontsize=7.2,
                    family="monospace", transform=ax_records.transAxes)

    ax_zone = fig.add_subplot(grid[1, 1])
    ax_zone.set_axis_off()
    ax_zone.set_title("(c) Zone diagnostics (zones.csv)", loc="left", fontsize=10)
    zone_rows = [[label, clean(zone.get(key, ""))] for key, label in ZONE_FIELDS]
    zone_table = ax_zone.table(cellText=zone_rows, colWidths=[0.32, 0.68], cellLoc="left", loc="upper left")
    zone_table.auto_set_font_size(False)
    zone_table.set_fontsize(7.5)
    zone_table.scale(1, 1.25)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=300, bbox_inches="tight")
    if args.out.suffix.lower() != ".pdf":
        fig.savefig(args.out.with_suffix(".pdf"), bbox_inches="tight")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
