# Third-party notices — BiblioRef

BiblioRef is distributed under the GNU Affero General Public License v3.0 (see `LICENSE`). This file identifies third-party software used by BiblioRef. It does not change the license of BiblioRef's original code and does not grant rights beyond those provided by the applicable third-party licenses.

## Core dependency

| Component | Requirement in BiblioRef | Upstream license |
|---|---|---|
| pypdfium2 / PDFium | `pypdfium2>=5.13,<6.0` | Apache-2.0 or BSD-3-Clause (pypdfium2); BSD-3-Clause and Apache-2.0 (PDFium) |

## Optional dependencies

| Component | Extra | Upstream license |
|---|---|---|
| PyMuPDF / MuPDF | `pymupdf` | GNU AGPL-3.0 or commercial license from Artifex |
| FastAPI | `app` | MIT |
| Uvicorn | `app` | BSD-3-Clause |
| python-multipart | `app` | Apache-2.0 |
| openpyxl | `app`, `audit` | MIT |
| google-api-python-client | `app` | Apache-2.0 |
| google-auth-oauthlib | `app` | Apache-2.0 |
| google-auth-httplib2 | `app` | Apache-2.0 |
| pywebview | `desktop` | BSD-3-Clause |
| pandas | `audit` | BSD-3-Clause |
| sentence-transformers | `semantic` | Apache-2.0; downloaded models carry their own licenses |

## PyMuPDF / MuPDF

**Project:** https://pymupdf.readthedocs.io/  
**Licensing:** dual-licensed by Artifex Software, Inc. under the GNU AGPL and commercial license agreements.

BiblioRef uses PyMuPDF, when installed, for opening documents, extracting page text and layout data, reading page counts and rendering pages; otherwise the same operations are provided by PDFium. The Windows desktop build bundles PyMuPDF. Because BiblioRef itself is licensed under the AGPL-3.0, its source and binary distributions use PyMuPDF under the AGPL terms. Anyone redistributing a modified BiblioRef build that includes PyMuPDF must comply with those terms or obtain a commercial license from Artifex.

No part of this notice claims ownership of PyMuPDF or MuPDF.

## Binary distributions

This is an audit of **direct** dependencies. Before publishing a bundled binary (PyInstaller), generate an exact locked environment and include the license files and NOTICE requirements of every transitive package and native runtime component it contains.
