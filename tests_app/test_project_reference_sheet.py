from pathlib import Path


def _js():
    return Path("static/project-reference-sheet.js").read_text(encoding="utf-8")


def test_summary_offers_thesis_and_reference_views():
    js = _js()
    assert 'data-view="tesis"' in js
    assert 'data-view="refs"' in js


def test_thesis_view_has_one_row_per_thesis_with_metadata_columns():
    js = _js()

    for key in ("author", "year", "degree_level", "program", "faculty", "university", "director", "codirector"):
        assert f"key:'{key}'" in js

    for header in (
        "Código",
        "Título de la tesis",
        "Autor/a",
        "Año",
        "Nivel",
        "Programa",
        "Facultad",
        "Universidad",
        "Director/a",
        "Codirector/a",
    ):
        assert header in js


def test_reference_view_groups_references_under_each_thesis():
    js = _js()

    # Thesis metadata lives once in the group header, not on every reference row.
    assert 'class="rs-group"' in js
    assert "thesisAuthor" not in js
    for header in ("Autor", "Tipo", "Revista / editorial", "DOI", "Pág.", "Referencia original"):
        assert header in js

    # References are fetched only when a thesis block is expanded.
    assert "ensureExpanded();" in js


def test_reference_sheet_asset_revision_is_current():
    loader = Path("static/projects.js").read_text(encoding="utf-8")
    assert 'project-reference-sheet.js?v=16' in loader


def test_thesis_view_mentions_what_ocr_would_unlock():
    js = _js()
    # One banner above the sheet, a grey tag under each affected code, "falta · OCR" on fillable cells.
    assert 'class="rs-ocrbar"' in js and "OCR pendiente" in js
    assert "Aplicar OCR…" in js and "data-ocr-filter" in js
    for tag in ("OCR · tesis completa", "OCR · portada", "OCR · bibliografía", "OCR hecho · falta reprocesar"):
        assert tag in js
    assert "missOcr('falta')" in js
    # OCR only runs when asked, on what it unlocks.
    assert "scope:'needed'" in js


def test_inference_is_explained_marked_and_auditable():
    js = _js()
    assert "Inferir faltantes…" in js and "Inferir no es extraer." in js
    assert 'class="rs-inf"' in js and ">inferido</button>" in js
    assert 'data-view="inferidos"' in js and "Deshacer todos" in js
    for route in ("/inference/preview", "/inference/undo-all", "/inference`"):
        assert route in js


def test_open_thesis_keeps_its_references_while_others_refresh():
    js = _js()
    # Invalidation is per thesis, not a project-wide signature.
    assert "const docKey = d =>" in js and "state.rowsByDoc.clear();" in js.split("function resetIfNeeded")[1].split("const keys")[0]
    assert "state.docKeys.get(docId) !== key" in js


def test_summary_filters_by_reason_with_checkboxes_and_column_shortcut():
    js = _js()
    # B: «Filtrar ▾» panel with grouped checkboxes, active chips and any/all.
    for text in ("Faltan datos de la tesis", "Problemas en las referencias", "Estado", "Limpiar filtros", "data-filter-remove"):
        assert text in js
    assert "name=\"rsFilterMode\"" in js and "state.filterMode === 'all'" in js
    # C: «N faltan» under each column toggles that filter.
    assert "data-filter-quick=\"meta:${key}\"" in js
    # Both views respect the filters.
    assert js.count("passesFilters") >= 3
