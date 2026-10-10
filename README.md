# BiblioRef

BiblioRef identifies the bibliography regions of a doctoral thesis (or any long scholarly PDF) and segments them into individual reference records. It combines page geometry (line-start margins, hanging indents, columns) with bibliographic signals (author–date patterns, numbering, repeated-author markers), and applies structural repairs only when they pass explicit acceptance checks. Every record keeps its page span and boundary evidence so extraction decisions can be inspected.

Segmentation is kept separate from bibliographic parsing: an optional downstream parser can split each extracted string into authors, year, title, document type and source, but it never changes where a reference begins or ends.

- Software version: `0.9.10-rc2`
- Extraction algorithm: `0.6.20`
- License: [AGPL-3.0](LICENSE)

## Installation

Requires Python 3.11 or later.

```bash
pip install "git+https://github.com/erecem23/BiblioRef.git"
```

From a source checkout:

```bash
pip install .
```

The default PDF backend is PDFium (`pypdfium2`). PyMuPDF can be installed as an alternative backend; when present it is selected automatically:

```bash
pip install ".[pymupdf]"
```

Scanned PDFs without a text layer need OCR before extraction; the local application (below) includes an OCR path, which requires the `pymupdf` extra.

## Command-line use

```bash
biblioref thesis.pdf --json result.json --csv references.csv --zones-csv zones.csv
```

`python -m biblioref` is equivalent. Main options:

| Option | Output |
|---|---|
| `--json` | Full result: records, zones, duplicate groups, extraction decision and diagnostics |
| `--csv` | One row per extracted reference |
| `--zones-csv` | One row per detected bibliography zone |
| `--parsed-csv` | References plus fields from the optional downstream parser |
| `--scope` | `all_reference_sections` (default), `final_reference_section` or `unique_references` |

Run `biblioref --help` for the remaining diagnostic options.

## Python use

```python
from biblioref import process_pdf

result = process_pdf("thesis.pdf")
for record in result["records"]:
    print(record["reference_text"])
```

## Local application

The repository also contains a local web application for reviewing extractions page by page, with projects, OCR, export to XLSX and metadata resolution. It runs from a source checkout:

```bash
pip install ".[app]"
python run_biblioref.py
```

`pip install ".[desktop]"` adds the pywebview desktop window (`run_biblioref_desktop.py`).

## Scope and limitations

BiblioRef reports what it extracted and why; it does not report a calibrated accuracy. Review flags and audit counts are processing signals, not probabilities of correctness. Reading order in scanned files, multi-column pages and unusual bibliographic conventions can still produce missed, merged or split references.

## Citation

See [CITATION.cff](CITATION.cff).

## License

BiblioRef is distributed under the GNU Affero General Public License v3.0. Third-party components are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
