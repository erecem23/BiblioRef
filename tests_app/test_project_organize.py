from contextlib import contextmanager

from biblioref.project_organize import OrganizeError, create_folder, delete_folder, move_documents, rename_folder
from biblioref.projects import project_tree


@contextmanager
def _refused():
    try:
        yield
    except OrganizeError:
        return
    raise AssertionError("expected OrganizeError")


def _corpus():
    project = {"id": "p"}
    docs = [
        {"id": f"d{i}", "project_id": "p", "filename": f"t{i}.pdf",
         "ingestion": {"relative_path": f"master_tesis/{uni}/t{i}.pdf"}}
        for i, uni in enumerate(["UNC", "UNC", "UNLP"])
    ]
    return project, docs


def _folders(nodes, prefix=()):
    out = {}
    for n in nodes:
        if n["kind"] == "folder":
            out["/".join(prefix + (n["name"],))] = n["count"]
            out.update(_folders(n["children"], prefix + (n["name"],)))
    return out


def test_import_folders_are_shown_until_something_is_organized():
    project, docs = _corpus()
    assert _folders(project_tree(project, docs)) == {"master_tesis": 3, "master_tesis/UNC": 2, "master_tesis/UNLP": 1}
    assert "folder" not in docs[0]


def test_create_empty_folder_and_move_with_undo_information():
    project, docs = _corpus()
    create_folder(project, docs, ["Duplicadas para revisar"])
    assert _folders(project_tree(project, docs))["Duplicadas para revisar"] == 0
    previous = move_documents(project, docs, [{"document_id": "d1", "path": ["Duplicadas para revisar"]}])
    assert previous == [{"document_id": "d1", "path": ["master_tesis", "UNC"]}]
    tree = _folders(project_tree(project, docs))
    assert tree["Duplicadas para revisar"] == 1 and tree["master_tesis/UNC"] == 1
    # Import provenance is kept.
    assert docs[1]["ingestion"]["relative_path"] == "master_tesis/UNC/t1.pdf"
    move_documents(project, docs, previous)
    assert _folders(project_tree(project, docs))["master_tesis/UNC"] == 2
    with _refused():
        create_folder(project, docs, ["Duplicadas para revisar"])


def test_rename_carries_theses_and_subfolders_and_refuses_collisions():
    project, docs = _corpus()
    create_folder(project, docs, ["master_tesis", "UNC", "Doctorado"])
    move_documents(project, docs, [{"document_id": "d0", "path": ["master_tesis", "UNC", "Doctorado"]}])
    rename_folder(project, docs, ["master_tesis", "UNC"], "Córdoba")
    tree = _folders(project_tree(project, docs))
    assert "master_tesis/UNC" not in tree
    assert tree["master_tesis/Córdoba"] == 2 and tree["master_tesis/Córdoba/Doctorado"] == 1
    with _refused():
        rename_folder(project, docs, ["master_tesis", "Córdoba"], "UNLP")


def test_delete_folder_moves_content_up_and_never_removes_theses():
    project, docs = _corpus()
    result = delete_folder(project, docs, ["master_tesis"])
    assert result["moved_documents"] == 3
    assert _folders(project_tree(project, docs)) == {"UNC": 2, "UNLP": 1}
    assert len(docs) == 3
    with _refused():
        delete_folder(project, docs, [])
    with _refused():
        move_documents(project, docs, [{"document_id": "zzz", "path": []}])


def test_explorer_ui_offers_folders_checkboxes_and_selections():
    from pathlib import Path
    js = Path("static/project-organize.js").read_text(encoding="utf-8")
    loader = Path("static/projects.js").read_text(encoding="utf-8")
    assert "project-organize.js?v=11" in loader
    for text in ("＋ Nueva carpeta", "Eliminar carpeta…", "Seleccionar su contenido", "Mover a…",
                 "Seleccionar por…", "Repetidas (mismo archivo)", "＋ Guardar búsqueda actual", "Deshacer",
                 "Mostrar las selecciones en el explorador", "Seleccionar todas las tesis visibles", "data-org-pick"):
        assert text in js
    for route in ("/folders`", "/folders/delete`", "/move`", "/documents/remove`", "/selections`"):
        assert route in js


def test_review_navigation_offers_both_layouts_and_a_page_rail():
    from pathlib import Path
    js = Path("static/review-navigation.js").read_text(encoding="utf-8")
    loader = Path("static/projects.js").read_text(encoding="utf-8")
    assert "review-navigation.js?v=" in loader
    assert loader.index("viewer-navigation.js") < loader.index("review-navigation.js")
    for text in ("biblioref.review-nav", 'data-rn-mode="list"', 'data-rn-mode="header"', "rn-strip",
                 "Volver a la bibliografía", "Límites de la sección ▾", "Alt+↑ / Alt+↓"):
        assert text in js
    # The horizontal page strip above the PDF is gone.
    assert "pagescrub" not in Path("static/viewer-navigation.js").read_text(encoding="utf-8")
