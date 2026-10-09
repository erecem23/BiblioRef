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

The demonstration in the software paper uses Martins, M. F. D. (2002), *Factores de riesgo para la calidad del ambiente en una población de niños nacidos en la ciudad de Pelotas, RS, Brasil*, Las tesis de Belgrano No. 9, Universidad de Belgrano (60 pages, SHA-256 `1e0054e50ada136a44645af790cf624ac9cc5fb312115ff097b3799842de5983`). The PDF and the extracted records are not redistributed here.

The demonstration shows that the software installs, runs and repeats its output. It does not estimate how often reference boundaries are correct.
