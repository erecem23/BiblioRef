# Reproducible demonstration

`run_demo.py` runs the installed `biblioref` command on one PDF, twice with each available PDF backend, and writes the JSON and CSV exports of every run plus a `manifest.json` with the input hash, software versions, environment, invocations, exit codes, elapsed times and the SHA-256 of every output. Repeated runs with the same backend are expected to produce byte-identical exports.

```bash
pip install ".[pymupdf]"
python examples/run_demo.py thesis.pdf --out demo_output --expect-sha256 <sha256 of thesis.pdf>
```

`make_figure.py` builds the demonstration figure from one of those runs: the page where the bibliography starts, the first extracted records and the zone diagnostics. It needs `matplotlib`, which is not a BiblioRef dependency.

```bash
pip install matplotlib
python examples/make_figure.py thesis.pdf demo_output/pdfium_run1 --out figure.png
```

The demonstration in the software paper uses Cortell Fuster, C. (2024), *Desarrollo galénico e innovación terapéutica en farmacia hospitalaria: sirólimus tópico liposomal en el tratamiento de los angiofibromas faciales asociados a esclerosis tuberosa*, doctoral thesis, Universitat de València, archived on Zenodo under CC BY 4.0 (https://doi.org/10.5281/zenodo.15586789; 292 pages, SHA-256 `48a0d38ce6fadba8bd86e4d21c813ac155defa6d73ca34d173c70c13909f9acc`). It was selected by a rule fixed before running BiblioRef and is not part of the development corpus. The paper's figure shows zone 4 of the PDFium run:

```bash
python examples/make_figure.py thesis.pdf demo_output/pdfium_run1 --zone 4 --out figure.png
```

The demonstration shows that the software installs, runs and repeats its output. It does not estimate how often reference boundaries are correct.
