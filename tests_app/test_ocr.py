import threading
import time
from pathlib import Path

import pymupdf

from biblioref import ocr_jobs
from biblioref.metadata.cover_v05 import detect_cover_metadata
from biblioref.ocr import _as_picture, _spread_split, _unreadable_pages, _unreadable_text, ocr_available, ocr_pdf_pages, ocr_target_path, scan_ocr_needs


def _scanned_cover_pdf(path: Path) -> None:
    """Page 1: the cover as a picture only. Page 2: real text. Page 3: blank."""
    drawn = pymupdf.open()
    cover = drawn.new_page(width=595, height=842)
    for y, size, text in [
        (120, 20, "Universidad Nacional de Córdoba"),
        (150, 18, "Facultad de Psicología"),
        (300, 22, "El concepto de parlêtre en Lacan"),
        (500, 16, "Autor: Lic. Guido Coll"),
        (530, 16, "Director: Dra. Mariana Gómez"),
        (760, 16, "Córdoba, 2017"),
    ]:
        cover.insert_text((70, y), text, fontsize=size)
    image = cover.get_pixmap(dpi=200).tobytes("png")
    drawn.close()

    pdf = pymupdf.open()
    pdf.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=image)
    pdf.new_page(width=595, height=842).insert_text((70, 90), "Resumen: texto de la tesis con capa de texto real.", fontsize=12)
    pdf.new_page(width=595, height=842)
    pdf.save(path)
    pdf.close()


def test_scan_reports_only_image_pages_without_text(tmp_path):
    path = tmp_path / "tesis.pdf"
    _scanned_cover_pdf(path)
    scan = scan_ocr_needs(path)
    assert scan["pages"] == [1]
    assert scan["ranges"] == [[1, 1]]
    assert scan["frontmatter_pages"] == [1]
    assert scan["scanned_document"] is False
    assert ocr_target_path(path).name == "tesis.ocr.pdf"
    assert ocr_target_path(ocr_target_path(path)).name == "tesis.ocr.pdf"


def test_a_scanner_stamp_on_every_page_is_not_a_text_layer(tmp_path):
    drawn = pymupdf.open()
    sheet = drawn.new_page(width=595, height=842)
    sheet.insert_text((70, 120), "Capitulo 1. Una pagina escaneada sin capa de texto.", fontsize=14)
    image = sheet.get_pixmap(dpi=100).tobytes("png")
    drawn.close()
    pdf = pymupdf.open()
    for _ in range(4):
        page = pdf.new_page(width=595, height=842)
        page.insert_image(pymupdf.Rect(0, 0, 595, 842), stream=image)
        page.insert_text((400, 830), "Scanned by CamScanner", fontsize=8)
    page = pdf.new_page(width=595, height=842)
    page.insert_text((70, 90), "Resumen: una pagina con capa de texto propia y suficiente.", fontsize=12)
    page.insert_text((400, 830), "Scanned by CamScanner", fontsize=8)
    path = tmp_path / "tesis.pdf"
    pdf.save(path)
    pdf.close()
    scan = scan_ocr_needs(path)
    assert scan["pages"] == [1, 2, 3, 4]
    assert scan["scanned_document"] is True


def test_ocr_adds_invisible_text_that_metadata_reads(tmp_path):
    if not ocr_available()["available"]:
        return
    path = tmp_path / "tesis.pdf"
    _scanned_cover_pdf(path)
    assert "author" not in detect_cover_metadata(path)["metadata"]

    target = ocr_target_path(path)
    result = ocr_pdf_pages(path, target)
    assert result["pages"] == [1]
    assert scan_ocr_needs(target)["pages"] == []
    meta = detect_cover_metadata(target)["metadata"]
    assert meta["author"] == "Guido Coll"
    assert meta["director"] == "Mariana Gómez"
    assert meta["university"] == "Universidad Nacional de Córdoba"
    # The page still looks the same: the recognised text is invisible.
    with pymupdf.open(path) as before, pymupdf.open(target) as after:
        assert before[0].get_pixmap(dpi=40).samples == after[0].get_pixmap(dpi=40).samples


class _Store:
    def __init__(self, docs):
        self.lock = threading.RLock()
        self._docs = docs
        self.saves = 0

    def docs(self):
        return self._docs

    def save(self):
        self.saves += 1


class _App:
    def __init__(self, docs):
        self.STORE = _Store(docs)

    @staticmethod
    def _now():
        return 1.0


def test_ocr_job_switches_to_ocr_copy_keeps_original_and_rereads(tmp_path):
    if not ocr_available()["available"]:
        return
    path = tmp_path / "tesis.pdf"
    _scanned_cover_pdf(path)
    doc = {"id": "d1", "path": str(path), "ocr_scan": scan_ocr_needs(path), "n_references": 12}
    app = _App({"d1": doc})
    reread = []

    state = ocr_jobs._enqueue(app, lambda d: reread.append(d["path"]), "d1", ocr_jobs._pages_for_scope(doc, "frontmatter"))
    assert state["state"] == "queued" and state["pages"] == [1]
    for _ in range(120):
        if ocr_jobs.job_status("d1")["state"] in {"done", "error"}:
            break
        time.sleep(0.25)
    status = ocr_jobs.job_status("d1")
    assert status["state"] == "done", status
    assert doc["original_path"] == str(path) and path.exists()
    assert doc["path"].endswith("tesis.ocr.pdf")
    assert doc["ocr"]["pages"] == [1]
    # Only the cover was recognised, so the bibliography does not need reprocessing.
    assert doc["ocr"]["reprocess_suggested"] is False
    assert doc["ocr_scan"]["pages"] == []
    assert reread == [doc["path"]] and app.STORE.saves == 1


def test_ocr_need_counts_only_what_ocr_unlocks():
    scan = {"pages": [1, 5, 40, 190], "frontmatter_pages": [1, 5], "scanned_document": False}
    complete = {k: "x" for k in ocr_jobs._COVER_FIELDS}
    # Loose scanned pages and a scanned cover whose metadata is already complete: nothing to do.
    assert ocr_jobs.ocr_need({"ocr_scan": scan, "metadata": complete}) is None
    cover = ocr_jobs.ocr_need({"ocr_scan": scan, "metadata": {**complete, "author": ""}})
    assert cover["kind"] == "cover" and cover["pages"] == [1, 5]
    both = ocr_jobs.ocr_need({"ocr_scan": scan, "metadata": {}, "sections": [{"start_page": 180, "end_page": 200}]})
    assert both["kind"] == "cover_bibliography" and both["bibliography_pages"] == [190] and both["pages"] == [1, 5, 190]
    whole = ocr_jobs.ocr_need({"ocr_scan": {"pages": [1, 2, 3], "scanned_document": True}, "metadata": complete})
    assert whole["kind"] == "document" and whole["pages"] == [1, 2, 3]
    assert ocr_jobs._pages_for_scope({"ocr_scan": scan, "metadata": complete}, "needed") == []


class _ExtractingApp(_App):
    def __init__(self, docs):
        super().__init__(docs)
        self.ACTIVE_ANALYSES = set()
        self.extracted = []

    def process_pdf(self, path, **kwargs):
        return {"path": str(path)}

    def _analyze_document(self, doc, profile, *, prepared_result=None):
        self.extracted.append(prepared_result["path"])
        doc["ocr"]["reprocess_suggested"] = False


def test_ocr_past_the_cover_extracts_the_bibliography_again():
    doc = {"id": "d2", "path": "escaneada.ocr.pdf", "references": [],
           "ocr": {"pages": [1, 9], "reprocess_suggested": True}}
    app = _ExtractingApp({"d2": doc})
    ocr_jobs._reextract(app, "d2")
    assert app.extracted == [doc["path"]] and doc["ocr"]["reprocess_suggested"] is False
    assert app.ACTIVE_ANALYSES == set()


def test_reextraction_skips_theses_with_manual_reference_work():
    assert not ocr_jobs._has_reference_work({"references": [{"edited": False}], "sections": [{"source": "automatic"}]})
    assert ocr_jobs._has_reference_work({"references": [{"edited": True}]})
    assert ocr_jobs._has_reference_work({"references": [{"deleted": True}]})
    assert ocr_jobs._has_reference_work({"sections": [{"source": "manual"}]})
    assert ocr_jobs._has_reference_work({"corrections": [{"x": 1}]})

    doc = {"id": "d3", "path": "x.ocr.pdf", "ocr": {"reprocess_suggested": True}, "references": [{"edited": True}]}
    app = _ExtractingApp({"d3": doc})
    ocr_jobs._reextract(app, "d3")
    assert app.extracted == []


def _rotated_scan_pdf(path: Path) -> None:
    """The cover stored sideways in a portrait page with /Rotate 90, like T0137."""
    flat = path.with_name("flat.pdf")
    _scanned_cover_pdf(flat)
    out = pymupdf.open()
    page = out.new_page(width=595, height=842)
    page.show_pdf_page(page.rect, pymupdf.open(flat), 0, rotate=90)
    page.set_rotation(90)
    out.save(path)


def test_ocr_on_a_rotated_page_lays_text_where_it_is_seen(tmp_path):
    if not ocr_available()["available"]:
        return
    path = tmp_path / "girada.pdf"
    _rotated_scan_pdf(path)
    target = ocr_target_path(path)
    ocr_pdf_pages(path, target)
    with pymupdf.open(target) as pdf:
        page = pdf[0]
        assert page.rotation == 90
        spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
                 if "Guido" in s["text"]]
        assert spans
        # v1 measured the width on the unrotated box, so every line came out at 1 pt.
        assert spans[0]["size"] > 4
    assert detect_cover_metadata(target)["metadata"].get("author") == "Guido Coll"


def test_a_text_layer_of_control_characters_is_unreadable():
    # T0140: fonts without ToUnicode read as \x00\x01\x02... although the page looks fine.
    garbage = "".join(chr(i % 30) for i in range(200)) + " abc"
    assert _unreadable_text(garbage)
    assert not _unreadable_text("Resumen: texto de la tesis con una capa de texto real.")
    # T0037 p161: a few stray control characters in real text are not enough.
    assert not _unreadable_text("Paso 2 Intervención breve \x0c Derivación Asistida " * 3 + "\x01" * 5)


def test_an_unreadable_page_becomes_its_picture(tmp_path):
    path = tmp_path / "ilegible.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((70, 100), "Autor: Lic. Guido Coll", fontsize=16)
    fresh = _as_picture(pdf, 0)
    assert fresh.get_text().strip() == ""
    assert len(fresh.get_images()) == 1
    assert (fresh.rect.width, fresh.rect.height) == (595, 842)


class _FakePage:
    def __init__(self, text):
        self.text = text

    def get_text(self, *_):
        return self.text


def test_a_mostly_unreadable_file_takes_its_weakly_garbled_pages_too():
    strong = "".join(chr(i % 30) for i in range(100))
    weak = "abcdefghij" * 9 + chr(1) * 5          # about 5 % control characters
    clean = "Texto de la tesis con palabras normales y ninguna rareza."
    mostly = [_FakePage(strong)] * 6 + [_FakePage(weak)] * 3 + [_FakePage(clean)]
    assert _unreadable_pages(mostly) == set(range(1, 10))
    # One garbled page in a sound thesis stays alone; a weak page is left as it is.
    sound = [_FakePage(clean)] * 8 + [_FakePage(strong), _FakePage(weak)]
    assert _unreadable_pages(sound) == {9}


class _Sheet:
    """Just what _spread_split reads from a page."""
    def __init__(self, width, height):
        self.rect = pymupdf.Rect(0, 0, width, height)
        self.rotation_matrix = pymupdf.Matrix(1, 0, 0, 1, 0, 0)


def _lines(x0, x1, n, y=40):
    return [{"text": "renglón", "bbox": (x0, y + 14 * i, x1, y + 14 * i + 10)} for i in range(n)]


def test_a_photographed_open_book_is_cut_at_the_gutter():
    # T0137: two pages side by side in one landscape scan.
    lines = _lines(40, 390, 30) + _lines(440, 800, 30)
    cut = _spread_split(_Sheet(842, 595), lines)
    assert cut is not None and 390 <= cut <= 440
    # T0137 p42: the left page is blank, all text is on the right one.
    cut = _spread_split(_Sheet(842, 595), _lines(413, 728, 30))
    assert cut is not None and cut <= 413


def test_a_landscape_page_with_full_width_lines_is_left_whole():
    # A wide table or a landscape chapter page: lines cross the middle.
    assert _spread_split(_Sheet(842, 595), _lines(40, 800, 40)) is None
    # A portrait page is never a spread, whatever its columns.
    assert _spread_split(_Sheet(595, 842), _lines(40, 280, 30) + _lines(320, 560, 30)) is None
