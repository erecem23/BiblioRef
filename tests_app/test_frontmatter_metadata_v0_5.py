from pathlib import Path

import fitz

from biblioref.document_title_v24 import TITLE_READING_REVISION, detect_thesis_title
from biblioref.metadata.cover_v05 import COVER_METADATA_VERSION, clean_person, detect_cover_metadata
from biblioref.metadata.integration import _apply_cover_metadata


def _pdf(path: Path, pages) -> None:
    doc = fitz.open()
    for rows in pages:
        page = doc.new_page(width=595, height=842)
        for row in rows:
            x, y, size, text = row if len(row) == 4 else (70, *row)
            page.insert_text((x, y), text, fontsize=size)
    doc.save(path)
    doc.close()


def _body(first_line: str, start: float = 90, lines: int = 22):
    rows = [(start, 12, first_line)]
    for i in range(1, lines):
        rows.append((start + i * 26, 12, "texto de cuerpo con varias palabras seguidas para llenar la página número"))
    return rows


def test_clean_person_strips_labels_honorifics_and_affiliations():
    assert COVER_METADATA_VERSION == "cover-metadata-v0.5.2"
    assert clean_person("ESTUDIANTE: Martina Cisneros") == "Martina Cisneros"
    assert clean_person("Doctor. Especialista, Jonathan Aguirre") == "Jonathan Aguirre"
    assert clean_person("Prof. Ab., Mónica Silvina Presser") == "Mónica Silvina Presser"
    assert clean_person("Esp. Lic. Pablo David Barrenengoa") == "Pablo David Barrenengoa"
    assert clean_person("Lorena Canet Juric (UNMDP, CONICET, IPSIBAT)") == "Lorena Canet Juric"
    assert clean_person("Carlos M. Díaz-Lázaro Ph. D") == "Carlos M. Díaz-Lázaro"
    assert clean_person("DR. JUAN MÁXIMO TRENCH") == "Juan Máximo Trench"
    assert clean_person("Doctoranda: Lic. María A. Benítez") == "María A. Benítez"
    assert clean_person("Doctoranda: Lic. Ana Soledad Briolotti") == "Ana Soledad Briolotti"
    assert clean_person("Dra. Florencia Macchioli") == "Florencia Macchioli"
    assert clean_person("EXPLICACIONES PSICOPATOLÓGICAS Y CATEGORÍAS") is None
    assert clean_person("MARÍA M. RICHARD’S") == "María M. Richard’s"
    assert clean_person("Cecilia Inés Calero · Mariano Sigman") == "Cecilia Inés Calero"
    assert clean_person("Leonardo Adrián Medrano & Fátima González Palau") == "Leonardo Adrián Medrano"
    assert clean_person("Dra. Graziela Napolitano y Dr. François Sauvagnat") == "Graziela Napolitano"
    assert clean_person("Imagen: Carolina Monterrubio") is None
    assert clean_person("Doctor en Psicología") is None
    assert clean_person("Y Directora de Beca del Conicet") is None
    assert clean_person("Cuenta Microsoft") is None


def test_v05_specialization_cover_with_labels_and_abstract_page(tmp_path):
    path = tmp_path / "tif.pdf"
    _pdf(path, [
        [
            (92, 12, "Carrera de Especialización en Docencia Universitaria –"),
            (112, 12, "Cohorte 2020"),
            (133, 12, "UNIVERSIDAD NACIONAL DE MAR DEL PLATA"),
            (195, 12, "TRABAJO INTEGRADOR FINAL"),
            (237, 12, "REPENSANDO LA ENSEÑANZA DE LAS CIENCIAS SOCIALES EN LA"),
            (258, 12, "UNIVERSIDAD: NUEVOS RECURSOS DIDÁCTICOS PARA SOCIOLOGÍA"),
            (278, 12, "DE LA CULTURA"),
            (673, 12, "Imagen: Carolina Monterrubio"),
            (715, 12, "Estudiante: Dra. Estefanía Martynowskyj"),
            (735, 12, "Tutora: Dra. María Florentina Lapadula"),
            (756, 12, "Fecha: 25 de marzo de 2026"),
        ],
        [
            (92, 12, "TÍTULO: Repensando la enseñanza de las Ciencias Sociales en la"),
            (112, 12, "Universidad: nuevos recursos didácticos para Sociología de la Cultura"),
            *_body("RESUMEN: Este trabajo describe una innovación pedagógica en la cátedra", start=175),
            (760, 12, "Cultura, del departamento de Sociología de la Facultad de Humanidades de la"),
        ],
    ])
    detected = detect_cover_metadata(path, path.name)
    meta = detected["metadata"]
    assert meta["author"] == "Estefanía Martynowskyj"
    assert meta["director"] == "María Florentina Lapadula"
    assert meta["degree_level"] == "especializacion"
    assert meta["program"] == "Especialización en Docencia Universitaria"
    assert meta["university"] == "Universidad Nacional de Mar del Plata"
    assert meta["year"] == "2026"
    # The abstract fragment "Facultad de Humanidades de la" is never kept as is.
    assert meta.get("faculty") in (None, "Facultad de Humanidades")

    title, source = detect_thesis_title(path, path.name, excluded_people=[meta["author"]])
    assert title.casefold() == (
        "Repensando la enseñanza de las Ciencias Sociales en la Universidad: "
        "nuevos recursos didácticos para Sociología de la Cultura"
    ).casefold()
    assert source == "cover_layout"
    assert TITLE_READING_REVISION == "document-title-v2.4"


def test_v05_plural_guide_label_and_acknowledgements_do_not_leak(tmp_path):
    path = tmp_path / "guia.pdf"
    _pdf(path, [
        [
            (292, 12, "Aportes desde la psicología crítica al campo de la salud mental: narrativas de"),
            (320, 12, "malestares adolescentes sobre el periodo pandémico."),
            (430, 12, "Maximiliano Andrés Apolonio Lorenzo"),
            (540, 12, "Profesoras guía Dra. María Sol Anigstein"),
            (568, 12, "Profesora Co-guía Dra. Paulina Chávez"),
            (678, 12, "Santiago, octubre de 2024"),
        ],
        [
            (72, 12, "Agradecimientos"),
            (127, 12, "A la Universidad Pública, por recibirme entre sus muros y a quienes"),
            (154, 12, "centro de la intervención y del trabajo cotidiano de estos años."),
        ],
    ])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["author"] == "Maximiliano Andrés Apolonio Lorenzo"
    assert meta["director"] == "María Sol Anigstein"
    assert meta["codirector"] == "Paulina Chávez"
    assert meta["year"] == "2024"
    assert "institution" not in meta
    assert "university" not in meta


def test_v05_jury_names_and_repository_notice_stay_out(tmp_path):
    path = tmp_path / "jurado.pdf"
    _pdf(path, [
        [
            (188, 172, 18, "DOCTORADO EN PSICOLOGÍA"),
            (280, 233, 16, "TESIS"),
            (115, 261, 14, "Contacto intergrupal entre personas con distinto estatus social"),
            (240, 314, 14, "Autor: Pablo Correa"),
            (229, 341, 14, "Directora: Cecilia Reyna"),
            (213, 367, 14, "Co-Directora: Silvina Brussino"),
            (240, 420, 14, "Tribunal evaluador:"),
            (259, 447, 14, "Elena Zubieta"),
            (257, 473, 14, "Alicia Barreiro"),
            (241, 499, 14, "Edgardo Etchezahar"),
            (238, 603, 10, "BY-NC) 4.0 Internacional. Y puede ser consultada en el Repositorio Institucional"),
            (238, 616, 10, "de la Universidad Nacional de Córdoba (RDU): https://rdu.unc.edu.ar"),
            (281, 718, 12, "-2023-"),
        ],
        [
            (355, 75, 22, "Agradecimientos"),
            (85, 135, 12, "Universidad Nacional de Córdoba, por todas las enseñanzas. Sin universidad pública"),
        ],
    ])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["author"] == "Pablo Correa"
    assert meta["director"] == "Cecilia Reyna"
    assert meta["codirector"] == "Silvina Brussino"
    assert meta["program"] == "Doctorado en Psicología"
    assert meta["year"] == "2023"
    assert meta.get("university") in (None, "Universidad Nacional de Córdoba")

    title, _ = detect_thesis_title(path, path.name, excluded_people=[meta["author"]])
    assert title == "Contacto intergrupal entre personas con distinto estatus social"


def test_v24_name_line_and_degree_statement_are_not_part_of_title(tmp_path):
    caps = tmp_path / "caps-name.pdf"
    _pdf(caps, [[
        (216, 162, 18, "VERÓNICA D'ANGELO"),
        (159, 194, 18, "El uso de ejemplos ilustrativos durante"),
        (151, 227, 18, "el aprendizaje de conceptos declarativos"),
        (247, 325, 14, "TESIS DOCTORAL"),
        (209, 353, 14, "DOCTORADO EN PSICOLOGIA"),
        (179, 381, 14, "UNIVERSIDAD NACIONAL DE CORDOBA"),
        (279, 437, 14, "Director:"),
        (217, 465, 14, "DR. JUAN MÁXIMO TRENCH"),
    ]])
    title, _ = detect_thesis_title(caps, caps.name)
    assert title == "El uso de ejemplos ilustrativos durante el aprendizaje de conceptos declarativos"
    assert detect_cover_metadata(caps, caps.name)["metadata"]["director"] == "Juan Máximo Trench"

    sized = tmp_path / "sized-name.pdf"
    _pdf(sized, [[
        (224, 182, 16, "Mario Alberto Trógolo"),
        (107, 226, 18, "Propuesta y evaluación de un modelo explicativo de"),
        (152, 267, 18, "conducción riesgosa en hombres jóvenes"),
        (122, 327, 17, "Tesis para acceder al grado de Doctor en Psicología"),
        (72, 414, 16, "Director: Dr. Rubén Daniel Ledesma"),
        (281, 670, 16, "2025"),
    ]])
    title, _ = detect_thesis_title(sized, sized.name)
    assert title == "Propuesta y evaluación de un modelo explicativo de conducción riesgosa en hombres jóvenes"
    meta = detect_cover_metadata(sized, sized.name)["metadata"]
    assert meta["program"] == "Doctorado en Psicología"
    assert meta["degree_level"] == "doctorado"


def test_v05_reads_captions_placed_under_the_name(tmp_path):
    path = tmp_path / "captions.pdf"
    _pdf(path, [
        [
            (278, 12, "Propuesta de una estrategia psicoeducativa de afrontamiento basada en la terapia"),
            (305, 12, "narrativa para niños y niñas ante el divorcio de sus padres. Cuenca – Ecuador 2021-2022"),
            (471, 12, "Mgt. Miriam Alexandra Lucio Bravo"),
            (498, 12, "Facultad de Psicología, Universidad de La Plata"),
            (526, 12, "Tesis para obtener el grado de doctora en Psicología"),
            (581, 12, "Cuenca, 2022"),
        ],
        [
            (71, 12, "Tesis para alcanzar el grado de doctora en Psicología"),
            (209, 12, "Mgt. Miriam Alexandra Lucio Bravo"),
            (236, 12, "Doctoranda"),
            (264, 12, "Dra. Isis Angélica Pernas Álvarez"),
            (292, 12, "Directora"),
            (319, 12, "Dra. Irma Colanzi"),
            (347, 12, "Codirectora"),
        ],
    ])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["author"] == "Miriam Alexandra Lucio Bravo"
    assert meta["director"] == "Isis Angélica Pernas Álvarez"
    assert meta["codirector"] == "Irma Colanzi"
    assert meta["faculty"] == "Facultad de Psicología"
    assert meta["university"] == "Universidad de La Plata"
    assert meta["program"] == "Doctorado en Psicología"
    assert meta["year"] == "2022"


def test_v05_year_ranges_and_wrapped_university_names(tmp_path):
    path = tmp_path / "range.pdf"
    _pdf(path, [[
        (90, 13, "UNIVERSIDAD NACIONAL DE"),
        (108, 13, "LA PLATA"),
        (130, 13, "FACULTAD DE PSICOLOGÍA"),
        (260, 16, "Arte abstracto y psicología de la Gestalt en la Argentina."),
        (285, 16, "Una historia de la psicologización de la forma (1944-1953)"),
        (400, 12, "Tesis de Doctorado en Psicología"),
        (700, 12, "La Plata, 2018"),
    ]])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["year"] == "2018"
    assert meta["university"] == "Universidad Nacional de La Plata"
    assert meta["faculty"] == "Facultad de Psicología"
    assert meta["institution"] == "Universidad Nacional de La Plata"


def test_v24_series_heading_is_not_a_title(tmp_path):
    path = tmp_path / "serie.pdf"
    _pdf(path, [[
        (210, 80, 19.6, "Universidad de Belgrano"),
        (112, 191, 64, "Las tesis"),
        (166, 226, 72, "de Belgrano"),
        (234, 508, 10, "Facultad de Estudios para Graduados"),
        (234, 520, 10, "Doctorado en Sociología"),
        (234, 568, 10, "Justicia y reforma en la Argentina democrática"),
        (234, 616, 10, "N° 65 Luis María Palma"),
        (234, 652, 10, "Tutor: Prof. Mag. José Gustavo Roger"),
        (234, 694, 10, "Julio 2013"),
    ]])
    title, _ = detect_thesis_title(path, path.name)
    assert title == "Justicia y reforma en la Argentina democrática"
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["director"] == "José Gustavo Roger"
    assert meta["university"] == "Universidad de Belgrano"


def test_v05_unlabelled_cover_name_and_roles_in_parentheses(tmp_path):
    path = tmp_path / "suelto.pdf"
    _pdf(path, [[
        (70, 12, "Jorge Ángel Bruera"),
        (110, 16, "Aportes a la explicación de la violencia sexual:"),
        (132, 16, "un contraste empírico del Modelo de Confluencia"),
        (200, 12, "Tesis doctoral"),
        (220, 12, "Doctorado en Psicología"),
        (300, 12, "Dra. Karin Arbach (directora)"),
        (320, 12, "Dra. Antonella Bobbio (codirectora)"),
        (700, 12, "2025"),
    ]])
    meta = detect_cover_metadata(path, path.name)["metadata"]
    assert meta["author"] == "Jorge Ángel Bruera"
    assert meta["director"] == "Karin Arbach"
    assert meta["codirector"] == "Antonella Bobbio"

    inline = tmp_path / "doctoranda.pdf"
    _pdf(inline, [[
        (200, 16, "Imaginario social y discurso institucional acerca de los niños"),
        (400, 12, "Doctoranda en Psicología Claudia Orleans"),
        (420, 12, "Director Dr. Carlos Ciappina"),
    ]])
    meta = detect_cover_metadata(inline, inline.name)["metadata"]
    assert meta["author"] == "Claudia Orleans"
    assert meta["director"] == "Carlos Ciappina"
    assert clean_person("Doctoranda: Mg. María Romé. mrome@psico.unlp.edu.ar") == "María Romé"


def test_background_refresh_rereads_stale_theses_and_keeps_human_edits(tmp_path):
    import threading
    import time
    from types import SimpleNamespace

    from biblioref.metadata import integration

    paths = {}
    for key, author in (("a", "Pablo Correa"), ("b", "Silvina Brussino")):
        paths[key] = tmp_path / f"{key}.pdf"
        _pdf(paths[key], [[
            (261, 14, "Contacto intergrupal entre personas con distinto estatus social"),
            (314, 14, f"Autor: {author}"),
            (700, 12, "2023"),
        ]])

    def stale(path, metadata, suggestions, project="p"):
        return {
            "project_id": project, "path": str(path), "filename": path.name,
            "title": "título viejo", "title_source": "cover_layout", "metadata": metadata,
            "metadata_detection": {"suggestions": suggestions},
            "cover_metadata_revision": "cover-metadata-v0.2", "title_reading_revision": "gap-spans-1",
        }

    docs = {
        "d1": stale(paths["a"], {"author": "Imagen: Carolina Monterrubio"}, {"author": "Imagen: Carolina Monterrubio"}),
        "d2": stale(paths["b"], {"author": "Autora editada a mano"}, {"author": "Otra sugerencia"}),
        "d3": stale(paths["a"], {}, {}, project="otro"),
    }
    saves = []
    store = SimpleNamespace(lock=threading.RLock(), docs=lambda: docs, save=lambda: saves.append(1))
    app_module = SimpleNamespace(STORE=store)

    assert integration._start_refresh(app_module, "p")["total"] == 2
    deadline = time.monotonic() + 120
    while integration._refresh_status("p")["running"] and time.monotonic() < deadline:
        time.sleep(0.2)
    status = integration._refresh_status("p")
    assert status["running"] is False and status["done"] == 2 and status["failed"] == 0
    assert docs["d1"]["metadata"]["author"] == "Pablo Correa"
    assert docs["d1"]["title"] == "Contacto intergrupal entre personas con distinto estatus social"
    assert docs["d2"]["metadata"]["author"] == "Autora editada a mano"
    assert not integration._is_stale(docs["d1"]) and not integration._is_stale(docs["d2"])
    assert integration._is_stale(docs["d3"])
    assert saves


def test_refresh_drops_stale_automatic_values_but_keeps_human_edits(tmp_path):
    path = tmp_path / "stale.pdf"
    _pdf(path, [[
        (250, 14, "Procesos de aprendizaje y memoria en adultos mayores"),
        (400, 14, "Carlos Méndez"),
        (680, 12, "Santiago, octubre de 2022"),
    ]])
    doc = {
        "path": str(path),
        "filename": path.name,
        "title": "centro de la intervención",
        "title_source": "cover_layout",
        "metadata": {
            "institution": "centro de la intervención",
            "faculty": "Facultad de Humanidades de la",
            "university": "Universidad corregida a mano",
        },
        "metadata_detection": {
            "version": "cover-metadata-v0.4",
            "suggestions": {
                "institution": "centro de la intervención",
                "faculty": "Facultad de Humanidades de la",
                "university": "Universidad Nacional de Córdoba, por todas las enseñanzas",
            },
        },
    }
    assert _apply_cover_metadata(None, doc) is True
    assert doc["title"] == "Procesos de aprendizaje y memoria en adultos mayores"
    assert "institution" not in doc["metadata"]
    assert "faculty" not in doc["metadata"]
    assert doc["metadata"]["university"] == "Universidad corregida a mano"
    assert doc["metadata"]["author"] == "Carlos Méndez"
    assert doc["cover_metadata_revision"] == COVER_METADATA_VERSION


def test_v051_degree_title_split_across_lines(tmp_path):
    split_head = tmp_path / "split_head.pdf"
    _pdf(split_head, [[
        (90, 16, "EVALUACIÓN DE TRATAMIENTOS PARA REVERTIR EFECTOS"),
        (200, 12, "Tesis doctoral para optar por el grado de Doctor"),
        (215, 12, "en Psicología de la Universidad Nacional de"),
        (230, 12, "Córdoba"),
        (300, 12, "Director: Dr. Ricardo Marcos Pautassi"),
        (400, 12, "AÑO 2024"),
    ]])
    assert detect_cover_metadata(split_head)["metadata"]["program"] == "Doctorado en Psicología"

    own_line = tmp_path / "own_line.pdf"
    _pdf(own_line, [[
        (90, 16, "Funciones ejecutivas y rendimiento académico"),
        (140, 12, "Macarena Verónica del Valle"),
        (170, 12, "Este trabajo de Tesis fue presentado en la Facultad de Psicología de la Universidad"),
        (185, 12, "Nacional de Mar del Plata como requisito parcial para la obtención del título de"),
        (200, 12, "DOCTORA EN PSICOLOGÍA"),
        (260, 12, "Director: Dr. Sebastián Urquijo"),
        (400, 12, "Mar del Plata, 2021"),
    ]])
    meta = detect_cover_metadata(own_line)["metadata"]
    assert meta["program"] == "Doctorado en Psicología"
    assert meta["degree_level"] == "doctorado"


def test_v051_program_from_abstract_when_cover_has_no_text(tmp_path):
    path = tmp_path / "scanned.pdf"
    _pdf(path, [
        [],
        [
            (90, 14, "Resumen:"),
            (120, 12, "La presente tesis, producto de la carrera de doctorado en Psicología de la"),
            (135, 12, "Universidad Nacional de Córdoba, se propone analizar la última producción."),
        ],
        [
            (90, 14, "Agradecimientos"),
            (120, 12, "A mis compañeros de la carrera de Especialización en Neuropsicología."),
        ],
    ])
    meta = detect_cover_metadata(path)["metadata"]
    assert meta["program"] == "Doctorado en Psicología"
    assert meta["degree_level"] == "doctorado"


def test_v051_career_without_en_and_conflicting_career_elsewhere(tmp_path):
    path = tmp_path / "career.pdf"
    _pdf(path, [
        [
            (90, 12, "Universidad Nacional de La Plata"),
            (105, 12, "Facultad de Psicología"),
            (120, 12, "Carrera de Doctorado Psicología"),
            (135, 12, "Tesis"),
            (160, 14, "Sobrecarga de familiares cuidadores de personas mayores"),
            (220, 12, "Director: Psic. Telma Piacente"),
            (240, 12, "Año 2023"),
        ],
        _body("Curriculum: egresada de la carrera de Especialización en Neuropsicología"),
    ])
    assert detect_cover_metadata(path)["metadata"]["program"] == "Doctorado en Psicología"
