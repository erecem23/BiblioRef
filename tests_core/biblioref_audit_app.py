# -*- coding: utf-8 -*-
"""BiblioRef v0.9.3-audit: memory-safe visual adapter with selective rescue routing."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

from biblioref.audit import (
    AUDIT_APP_VERSION,
    ManualZoneSpec,
    add_audit_columns,
    build_audit_bundle,
    candidate_heading_lines,
    dataframe_csv_bytes,
    detect_reference_like_regions,
    nearest_line,
    page_dimensions,
    pdf_page_count,
    process_manual_zone,
    render_page_png,
    workbook_bytes,
)
from biblioref import process_pdf
from biblioref.rescue import PROFILE_LABELS, RESCUE_PROFILES
from biblioref.ingestion import (
    clear_layout_line_cache,
    extract_layout_lines,
    extract_layout_lines_range,
    pdf_preflight,
    stream_file_to_disk,
)


st.set_page_config(page_title="BiblioRef Audit", page_icon="📚", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 3rem;}
    [data-testid="stMetricValue"] {font-size: 1.55rem;}
    .small-note {color:#5b6472; font-size:0.92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _save_upload(uploaded) -> tuple[Path, str]:
    """Persist an upload by chunks and keep only its path/metadata in session."""
    signature = (
        Path(uploaded.name).name,
        int(getattr(uploaded, "size", 0) or 0),
        str(getattr(uploaded, "file_id", "") or ""),
    )
    existing = st.session_state.get("pdf_path")
    if st.session_state.get("upload_signature") == signature and existing and Path(existing).exists():
        return Path(existing), str(st.session_state["pdf_digest"])

    workdir = Path(tempfile.mkdtemp(prefix="biblioref_audit_"))
    safe_name = Path(uploaded.name).name
    pdf_path = workdir / safe_name
    streamed = stream_file_to_disk(uploaded, pdf_path)
    digest = str(streamed["sha256"])[:16]
    for key in (
        "references_df", "zones_df", "manual_clicks", "manual_specs",
        "pending_start", "pending_end", "pasted_references",
        "suggested_end_page", "page_to_mark", "manual_end_page_input",
        "zone_start_page_input", "zone_end_page_input",
        "last_extraction_message", "requested_zone_start_page", "requested_zone_end_page",
        "audit_view_page",
    ):
        st.session_state.pop(key, None)
    st.session_state.update({
        "upload_signature": signature,
        "pdf_digest": digest,
        "pdf_path": str(pdf_path),
        "pdf_size_bytes": int(streamed["size_bytes"]),
        "manual_clicks": [],
        "manual_specs": [],
        "pending_start": None,
        "pending_end": None,
    })
    return pdf_path, digest


@st.cache_data(show_spinner=False)
def _extract_lines_cached(pdf_path: str, digest: str):
    del digest
    return extract_layout_lines(pdf_path)


@st.cache_data(show_spinner=False)
def _process_cached(pdf_path: str, digest: str, scope: str, adaptive_mode: str, rescue_profile: str, rescue_chain: tuple[str, ...]):
    del digest
    return process_pdf(pdf_path, scope=scope, adaptive_mode=adaptive_mode, rescue_profile=rescue_profile, rescue_audit=True, rescue_chain=rescue_chain)


@st.cache_data(show_spinner=False)
def _preflight_cached(pdf_path: str, digest: str):
    del digest
    return pdf_preflight(pdf_path)


@st.cache_data(show_spinner=False, max_entries=8)
def _render_cached(pdf_path: str, digest: str, page: int, zoom: float):
    del digest
    return render_page_png(pdf_path, page, zoom)


def _native_pdf_viewer(pdf_path: Path, heavy_mode: bool, page_count: int, digest: str) -> None:
    """Use the full browser viewer only for ordinary PDFs; heavy PDFs render one page."""
    if not heavy_mode and hasattr(st, "pdf"):
        try:
            st.pdf(str(pdf_path), height=760)
            return
        except Exception:
            pass
    st.session_state.setdefault("audit_view_page", max(1, min(page_count, int(page_count * 0.85) or 1)))
    page = int(st.number_input(
        "Página visible", min_value=1, max_value=max(page_count, 1), step=1, key="audit_view_page"
    ))
    png = _render_cached(str(pdf_path), digest, page, 1.35)
    st.image(png, caption=f"Página {page} de {page_count}", width="stretch")
    if heavy_mode:
        st.caption("Modo PDF pesado: el visor renderiza únicamente la página visible.")


def _ensure_frames(report: dict, result_key: str) -> None:
    if st.session_state.get("frames_result_key") != result_key:
        st.session_state.references_df = pd.DataFrame(add_audit_columns(report.get("records", [])))
        st.session_state.zones_df = pd.DataFrame(report.get("zones", []))
        st.session_state.frames_result_key = result_key


def _overlaps(row: pd.Series, start: int, end: int) -> bool:
    row_start = int(row.get("zone_start_page", row.get("start_page", -1)))
    row_end = int(row.get("zone_end_page", row.get("end_page", -1)))
    return row_start <= end and row_end >= start


def _safe_page(value, fallback: int, page_count: int) -> int:
    """Convert optional widget/session values into a valid PDF page."""
    try:
        if value is None or pd.isna(value):
            raise ValueError
        page = int(value)
    except (TypeError, ValueError, OverflowError):
        page = int(fallback)
    return max(1, min(int(page_count), page))


def _suggest_end_page(
    start_page: int,
    page_count: int,
    regions: pd.DataFrame,
    automatic_zones=None,
) -> int:
    """Prefer an automatic closure, then structural regions, then a generous end."""
    start_page = _safe_page(start_page, 1, page_count)
    for zone in automatic_zones or []:
        zone_start = _safe_page(zone.get("start_page"), start_page, page_count)
        zone_end = _safe_page(zone.get("end_page"), zone_start, page_count)
        if abs(zone_start - start_page) <= 1 and zone_end >= start_page:
            return zone_end
    if not regions.empty:
        matching = regions.loc[
            (regions["start_page"] <= start_page + 2)
            & (regions["end_page"] >= start_page)
        ]
        if not matching.empty:
            return _safe_page(matching["end_page"].max(), start_page, page_count)
    if start_page >= max(1, int(page_count * 0.70)):
        return page_count
    return min(page_count, start_page + max(5, int(page_count * 0.08)))


def _next_zone_id(zones: pd.DataFrame) -> int:
    if zones.empty or "zone_id" not in zones:
        return 1
    values = pd.to_numeric(zones["zone_id"], errors="coerce").dropna()
    return int(values.max()) + 1 if not values.empty else 1


st.title("BiblioRef · auditoría visual")
st.caption(
    f"Interfaz {AUDIT_APP_VERSION}. El PDF permanece en tu computadora; la aplicación corre localmente."
)

uploaded = st.file_uploader("Subí una tesis en PDF", type=["pdf"])
if uploaded is None:
    st.info("Subí un PDF para ejecutar la detección automática y abrir el modo de auditoría.")
    st.stop()

pdf_path, pdf_digest = _save_upload(uploaded)
preflight = _preflight_cached(str(pdf_path), pdf_digest)
page_count = int(preflight["page_count"])
heavy_mode = bool(preflight["heavy_mode"])
if heavy_mode:
    reasons = ", ".join(preflight.get("heavy_mode_reasons", []))
    st.info(
        f"PDF pesado detectado: {preflight['size_mb']} MB · {page_count} páginas. "
        f"Se activó procesamiento de memoria reducida ({reasons}). "
        "La extracción bibliográfica no cambia; el visor carga páginas bajo demanda."
    )

scope = st.sidebar.selectbox(
    "Alcance",
    ["all_reference_sections", "final_reference_section", "unique_references"],
    format_func=lambda value: {
        "all_reference_sections": "Todas las zonas",
        "final_reference_section": "Última zona",
        "unique_references": "Referencias únicas",
    }[value],
)
adaptive_enabled = st.sidebar.checkbox("Diagnóstico adaptativo (shadow)", value=True)
adaptive_mode = "shadow" if adaptive_enabled else "off"
rescue_profile = st.sidebar.selectbox(
    "Método / rescate selectivo",
    list(RESCUE_PROFILES),
    index=0,
    format_func=lambda value: PROFILE_LABELS[value],
    help="La ruta efectiva v0.9.0 siempre se calcula primero. Los rescates sólo se aplican si los elegís explícitamente.",
)
rescue_chain_text = st.sidebar.text_input(
    "Cadena avanzada de rescates (opcional)",
    value="",
    help=(
        "Separá perfiles con comas, por ejemplo: numeric_filter,multi_column_reflow_v2. "
        "La cadena es explícita y nunca se autoaplica; los rescates que cambian zonas deben ir al final."
    ),
)
rescue_chain = tuple(x.strip() for x in rescue_chain_text.split(",") if x.strip())
if rescue_chain:
    rescue_profile = "stable"

with st.spinner("Analizando estructura, zonas y referencias…"):
    report = _process_cached(str(pdf_path), pdf_digest, scope, adaptive_mode, rescue_profile, rescue_chain)
    if heavy_mode:
        clear_layout_line_cache()
        layout_lines = None
        probable_regions = list(report.get("candidate_reference_regions", []) or [])
    else:
        layout_lines = _extract_lines_cached(str(pdf_path), pdf_digest)
        probable_regions = detect_reference_like_regions(layout_lines, page_count)
_ensure_frames(report, f"{pdf_digest}|{scope}|{adaptive_mode}|{rescue_profile}|{','.join(rescue_chain)}")

tabs = st.tabs(["Resultado", "Auditoría PDF", "Exportar"])

with tabs[0]:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Páginas", page_count)
    m2.metric("Zonas", len(st.session_state.zones_df))
    m3.metric("Referencias", len(st.session_state.references_df))
    flagged = 0
    if not st.session_state.references_df.empty and "audit_flags" in st.session_state.references_df:
        flagged = int(st.session_state.references_df["audit_flags"].fillna("").ne("").sum())
    m4.metric("Con alertas", flagged)

    router_audit = report.get("post_extraction_audit", {})
    recommendations = router_audit.get("recommendations", []) or []
    if rescue_profile == "stable" and recommendations:
        st.warning(
            "La extracción efectiva se mantuvo intacta, pero el auditor detectó síntomas de posible problema. "
            "Podés probar uno de los métodos selectivos sugeridos desde la barra lateral y comparar antes de aceptar."
        )
        for item in recommendations[:4]:
            st.write(f"• **{item.get('label', item.get('profile'))}** · {item.get('severity', 'review')} · `{item.get('reason', '')}`")
    elif rescue_profile != "stable" or rescue_chain:
        comparison = report.get("rescue_candidate_comparison", {})
        if comparison:
            label = "Cadena explícita" if rescue_chain else "Candidato de rescate explícito"
            st.info(
                f"{label}: {comparison.get('stable_n_records')} → "
                f"{comparison.get('candidate_n_records')} referencias; "
                f"{comparison.get('stable_n_zones')} → {comparison.get('candidate_n_zones')} zonas. "
                "No se considera automáticamente mejor: requiere revisión visual."
            )
        next_audit = report.get("post_rescue_audit", {})
        next_recommendations = next_audit.get("recommendations", []) or []
        if next_recommendations:
            st.warning("Después de este candidato todavía quedan síntomas distintos. Próximos rescates sugeridos:")
            for item in next_recommendations[:4]:
                st.write(f"• **{item.get('label', item.get('profile'))}** · {item.get('severity', 'review')} · `{item.get('reason', '')}`")

    decision = report.get("detection_decision", {})
    detection_method = decision.get("method", "stable_v0_5_3_route")
    if detection_method == "inferred_unknown_style":
        st.warning(
            "No funcionó la ruta estable. BiblioRef encontró una zona por regularidad "
            "bibliográfica y la extrajo como hipótesis. Revisala antes de aceptarla."
        )
    elif detection_method == "stable_zone_resegmentation_v0_6_1":
        repairs = report.get("segmentation_repairs", [])
        repaired = ", ".join(str(item.get("zone_id")) for item in repairs)
        st.warning(
            "La zona fue localizada por la ruta estable, pero la primera segmentación "
            f"fusionaba referencias. Se aplicó la reparación v0.6.1 en la(s) zona(s) {repaired}. "
            "Revisá visualmente algunas filas antes de exportar."
        )
    elif detection_method == "audit_required":
        shadow = report.get("adaptive_shadow", {})
        shadow_status = shadow.get("overall_status", "not_run")
        if shadow_status in {"candidate_worth_reviewing", "ambiguous", "manual_review_required"}:
            st.warning(
                "La ruta estable se abstuvo. El análisis adaptativo en modo shadow encontró "
                "una hipótesis que merece revisión, pero no modificó ni creó referencias "
                "automáticamente. Revisala en el diagnóstico adaptativo y en «Auditoría PDF»."
            )
        elif shadow_status == "bibliographic_region_unverified":
            st.warning(
                "La ruta estable se abstuvo y se encontró una región repetitiva, pero la nueva "
                "verificación bibliográfica no reunió evidencia suficiente para segmentarla. "
                "No se generaron referencias shadow; revisá la región en «Auditoría PDF»."
            )
        else:
            st.warning(
                "La ruta estable no produjo un resultado confiable y el análisis adaptativo "
                "tampoco encontró una hipótesis suficientemente informativa. Revisá las "
                "regiones propuestas en «Auditoría PDF»."
            )
    elif report.get("n_zones", 0) == 0:
        if probable_regions:
            st.warning(
                f"No se detectó un encabezado estándar, pero aparecieron {len(probable_regions)} "
                "regiones con estructura de referencias. Confirmalas en «Auditoría PDF»."
            )
        else:
            st.warning(
                "No se detectaron zonas automáticamente. Abrí «Auditoría PDF», buscá el encabezado y marcá el inicio y el final."
            )
    else:
        st.success(
            "Se conservó la ruta estable: las reglas adaptativas no modificaron esta extracción."
        )

    adaptive_shadow = report.get("adaptive_shadow")
    if adaptive_shadow and adaptive_shadow.get("mode") == "shadow":
        overall = adaptive_shadow.get("overall_status", "not_run")
        review_ids = adaptive_shadow.get("review_zone_ids", [])
        if overall == "stable_preferred":
            st.caption(
                "Shadow adaptativo: no encontró una alternativa estructuralmente mejor. "
                "La salida visible sigue siendo la validada."
            )
        elif overall == "bibliographic_region_unverified":
            st.caption(
                "Shadow adaptativo: se descubrió una región repetitiva, pero no superó la "
                "verificación bibliográfica. El scoring de fronteras no se ejecutó."
            )
        elif overall != "not_run":
            st.info(
                "Shadow adaptativo: se detectó una alternativa para revisar. "
                "No se aplicó automáticamente."
            )

        verification_rows = adaptive_shadow.get("region_verifications", [])
        if verification_rows:
            with st.expander("Verificación de región bibliográfica", expanded=overall == "bibliographic_region_unverified"):
                st.caption(
                    "Descubrir una región por layout no alcanza para segmentarla. La verificación "
                    "exige convergencia de señales bibliográficas independientes y penaliza prosa temporal."
                )
                region_rows = []
                for item in verification_rows:
                    verification = item.get("region_verification", {})
                    heading = verification.get("heading", {})
                    context = verification.get("document_context", {})
                    region_rows.append({
                        "región": item.get("region_id"),
                        "veredicto": verification.get("verdict"),
                        "score": verification.get("score_0_12"),
                        "rol_documental": context.get("dominant_role", "—"),
                        "score_contexto": context.get("context_score"),
                        "familias": ", ".join(verification.get("signal_families", [])),
                        "encabezado": heading.get("text") if heading.get("found") else "—",
                        "segmentación_shadow": item.get("segmentation_attempted"),
                    })
                st.dataframe(pd.DataFrame(region_rows), hide_index=True, width="stretch")

        document_context = adaptive_shadow.get("document_context", {})
        repeated_decorations = adaptive_shadow.get("repeated_decorations", {})
        if document_context or repeated_decorations.get("items"):
            with st.expander("Contexto documental y geometría global", expanded=False):
                role_counts = document_context.get("role_counts", {})
                if role_counts:
                    st.caption("Roles documentales inferidos de forma heurística; funcionan como evidencia contextual, no como reglas rígidas.")
                    st.json(role_counts)
                decorations = repeated_decorations.get("items", [])
                if decorations:
                    st.caption("Encabezados/pies repetidos detectados por texto + banda geométrica + frecuencia.")
                    st.dataframe(pd.DataFrame(decorations), hide_index=True, width="stretch")

        if adaptive_shadow.get("zones"):
            with st.expander("Diagnóstico adaptativo (shadow)", expanded=overall != "stable_preferred"):
                st.caption(
                    "Los puntajes son sumas heurísticas explícitas, no probabilidades. "
                    "En regiones descubiertas, el scoring sólo corre después de superar la "
                    "verificación bibliográfica. Esta capa nunca reemplaza la extracción por sí sola."
                )
                rows = []
                for zone_shadow in adaptive_shadow.get("zones", []):
                    baseline = zone_shadow.get("baseline", {})
                    candidate = zone_shadow.get("shadow_candidate", {})
                    comparison = zone_shadow.get("comparison", {})
                    evidence = zone_shadow.get("candidate_evidence_summary", {})
                    geometry = zone_shadow.get("geometry_diagnostics", {})
                    x0_profile = geometry.get("x0_profile", {})
                    gap_profile = geometry.get("gap_profile", {})
                    rows.append({
                        "zona": zone_shadow.get("zone_id"),
                        "estado": comparison.get("status"),
                        "segmentos_base": baseline.get("n_segments"),
                        "segmentos_shadow": candidate.get("n_segments"),
                        "score_base": baseline.get("structural_score_0_10"),
                        "score_shadow": candidate.get("structural_score_0_10"),
                        "fronteras_activas": evidence.get("n_active_boundaries"),
                        "sangría_francesa": x0_profile.get("hanging_indent_detected"),
                        "gap_mediana": gap_profile.get("median_gap"),
                        "gap_MAD": gap_profile.get("mad_gap"),
                        "densidad_local_mediana": geometry.get("local_density_median"),
                        "revisar": comparison.get("requires_review"),
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

                for zone_shadow in adaptive_shadow.get("zones", []):
                    if not zone_shadow.get("comparison", {}).get("requires_review"):
                        continue
                    candidates = zone_shadow.get("noteworthy_boundaries", [])
                    if not candidates:
                        continue
                    st.markdown(f"**Fronteras destacadas — zona {zone_shadow.get('zone_id')}**")
                    preview_rows = []
                    for item in candidates[:40]:
                        preview_rows.append({
                            "página": item.get("page"),
                            "score": item.get("score"),
                            "etiqueta": item.get("label"),
                            "activa": item.get("active_shadow_boundary"),
                            "señales": ", ".join(
                                part.get("signal", "") for part in item.get("contributions", [])
                            ),
                            "texto": item.get("text_preview"),
                        })
                    st.dataframe(pd.DataFrame(preview_rows), hide_index=True, width="stretch")

    logical_groups = report.get("logical_zone_groups", [])
    if logical_groups:
        st.info(
            "Se detectaron encabezados corridos: varias zonas físicas pertenecen a una "
            "misma bibliografía lógica. Las referencias no fueron modificadas."
        )

    st.subheader("Zonas bibliográficas")
    if (
        not st.session_state.zones_df.empty
        and "numeric_sequence_warning" in st.session_state.zones_df
        and st.session_state.zones_df["numeric_sequence_warning"].fillna("").ne("").any()
    ):
        warnings = st.session_state.zones_df.loc[
            st.session_state.zones_df["numeric_sequence_warning"].fillna("").ne(""),
            [column for column in ("heading", "numeric_sequence_warning") if column in st.session_state.zones_df],
        ]
        st.warning("Se detectaron discontinuidades en la numeración. Revisá estas zonas antes de aceptar la salida.")
        st.dataframe(warnings, hide_index=True, width="stretch")
    st.session_state.zones_df = st.data_editor(
        st.session_state.zones_df,
        width="stretch",
        num_rows="dynamic",
        hide_index=True,
        key="zones_editor",
    )

    st.subheader("Referencias")
    st.caption("La tabla es editable. Podés corregir texto, aceptar/rechazar filas, agregar notas o crear filas nuevas.")
    column_config = {
        "accepted": st.column_config.CheckboxColumn("Aceptada", default=True),
        "audit_status": st.column_config.SelectboxColumn(
            "Estado",
            options=["pending_review", "accepted", "corrected", "rejected", "manual"],
        ),
        "reference_text": st.column_config.TextColumn("Referencia", width="large"),
        "audit_note": st.column_config.TextColumn("Nota de auditoría", width="medium"),
    }
    st.session_state.references_df = st.data_editor(
        st.session_state.references_df,
        width="stretch",
        height=520,
        num_rows="dynamic",
        hide_index=True,
        column_config=column_config,
        key="references_editor",
    )

    with st.expander("Agregar referencias copiadas manualmente"):
        pasted = st.text_area(
            "Pegá una o varias referencias. Separalas con una línea en blanco.",
            key="pasted_references",
            height=160,
        )
        if st.button("Agregar a la grilla", disabled=not pasted.strip()):
            chunks = [chunk.replace("\n", " ").strip() for chunk in pasted.split("\n\n") if chunk.strip()]
            rows = [{
                "reference_text": chunk,
                "annotation_text": "",
                "style": "manual_paste",
                "manual_zone": True,
                "accepted": True,
                "audit_status": "manual",
                "audit_note": "Pegada desde el visor PDF",
            } for chunk in chunks]
            st.session_state.references_df = pd.concat(
                [st.session_state.references_df, pd.DataFrame(rows)], ignore_index=True
            )
            st.rerun()

with tabs[1]:
    left, right = st.columns([1.05, 1], gap="large")
    if layout_lines is not None:
        candidates = pd.DataFrame(candidate_heading_lines(layout_lines))
    else:
        candidates = pd.DataFrame([
            {
                "page": int(zone.get("start_page", 1) or 1),
                "y": 0.0,
                "text": str(zone.get("heading", "Zona detectada")),
                "score": 1.0,
                "reason": "effective_zone_heading",
            }
            for zone in report.get("zones", [])
        ])
    regions_df = pd.DataFrame(probable_regions)

    with left:
        st.subheader("Visor del PDF")
        st.caption("En este visor podés buscar texto, seleccionar y copiar referencias.")
        _native_pdf_viewer(pdf_path, heavy_mode, page_count, pdf_digest)

    with right:
        st.subheader("Extraer una zona")
        st.caption(
            "Elegí la primera y la última página del bloque. Los clics sobre el PDF "
            "quedan disponibles sólo para casos que necesiten un corte dentro de una página."
        )
        if st.session_state.get("last_extraction_message"):
            st.success(st.session_state.last_extraction_message)

        if not candidates.empty:
            with st.expander(f"Encabezados candidatos ({len(candidates)})", expanded=report.get("n_zones", 0) == 0):
                st.dataframe(candidates, width="stretch", height=190, hide_index=True)
        else:
            st.caption("No aparecieron encabezados textuales confiables.")

        if not regions_df.empty:
            with st.expander(
                f"Zonas probables por estructura ({len(regions_df)})",
                expanded=report.get("n_zones", 0) == 0,
            ):
                st.dataframe(regions_df, width="stretch", height=190, hide_index=True)
                selected_region_id = st.selectbox(
                    "Región sugerida",
                    regions_df["region_id"].astype(int).tolist(),
                    format_func=lambda value: (
                        f"Región {value}: páginas "
                        f"{int(regions_df.loc[regions_df.region_id == value, 'start_page'].iloc[0])}-"
                        f"{int(regions_df.loc[regions_df.region_id == value, 'end_page'].iloc[0])}"
                    ),
                )
                if st.button("Usar esta región como rango inicial"):
                    region = regions_df.loc[regions_df.region_id == selected_region_id].iloc[0]
                    start_page_suggested = int(region["start_page"])
                    suggested_end = max(
                        int(region["end_page"]),
                        _suggest_end_page(
                            start_page_suggested,
                            page_count,
                            regions_df,
                            report.get("zones", []),
                        ),
                    )
                    st.session_state.zone_start_page_input = start_page_suggested
                    st.session_state.zone_end_page_input = suggested_end
                    st.session_state.page_to_mark = start_page_suggested
                    st.rerun()

        if not candidates.empty:
            late_candidates = candidates.loc[candidates["page"] >= max(1, int(page_count * 0.50))]
            default_candidate = late_candidates.iloc[0] if not late_candidates.empty else candidates.iloc[0]
            default_page = int(default_candidate["page"])
        elif not regions_df.empty:
            default_page = int(regions_df.iloc[-1]["start_page"])
        else:
            default_page = max(1, int(page_count * 0.85))

        default_page = _safe_page(default_page, page_count, page_count)
        default_end = _suggest_end_page(
            default_page, page_count, regions_df, report.get("zones", [])
        )
        st.session_state.setdefault("zone_start_page_input", default_page)
        st.session_state.setdefault("zone_end_page_input", default_end)
        requested_start = st.session_state.pop("requested_zone_start_page", None)
        requested_end = st.session_state.pop("requested_zone_end_page", None)
        if requested_start is not None:
            st.session_state.zone_start_page_input = requested_start
        if requested_end is not None:
            st.session_state.zone_end_page_input = requested_end
        st.session_state.zone_start_page_input = _safe_page(
            st.session_state.zone_start_page_input, default_page, page_count
        )
        st.session_state.zone_end_page_input = _safe_page(
            st.session_state.zone_end_page_input, default_end, page_count
        )

        if not candidates.empty:
            candidate_indices = list(candidates.index)
            selected_candidate_index = st.selectbox(
                "Encabezado que parece iniciar la sección",
                candidate_indices,
                format_func=lambda index: (
                    f"Página {int(candidates.loc[index, 'page'])}: "
                    f"{candidates.loc[index, 'text']}"
                ),
            )
            if st.button("Usar este encabezado como inicio"):
                selected_page = int(candidates.loc[selected_candidate_index, "page"])
                st.session_state.zone_start_page_input = selected_page
                st.session_state.zone_end_page_input = _suggest_end_page(
                    selected_page, page_count, regions_df, report.get("zones", [])
                )
                st.session_state.page_to_mark = selected_page
                st.rerun()

        st.markdown("#### 1. Confirmá las páginas")
        page_col1, page_col2 = st.columns(2)
        with page_col1:
            zone_start_page = st.number_input(
                "Primera página",
                min_value=1,
                max_value=page_count,
                step=1,
                key="zone_start_page_input",
            )
        with page_col2:
            zone_end_page = st.number_input(
                "Última página",
                min_value=1,
                max_value=page_count,
                step=1,
                key="zone_end_page_input",
            )
        valid_range = int(zone_end_page) >= int(zone_start_page)
        if valid_range:
            st.info(
                f"Se analizarán las páginas {int(zone_start_page)}–{int(zone_end_page)} "
                f"({int(zone_end_page) - int(zone_start_page) + 1} páginas)."
            )
        else:
            st.error("La última página no puede ser anterior a la primera.")

        note = st.text_input("Nota opcional para esta zona")
        replace_overlap = st.checkbox(
            "Reemplazar zonas automáticas superpuestas", value=True
        )

        st.markdown("#### 2. Ejecutá la extracción")
        if st.button(
            "Extraer referencias de estas páginas",
            type="primary",
            disabled=not valid_range,
            width="stretch",
        ):
            start_page_value = int(zone_start_page)
            end_page_value = int(zone_end_page)
            start_marker = st.session_state.get("pending_start")
            end_marker = st.session_state.get("pending_end")
            start_y = (
                float(start_marker["y_pdf"])
                if start_marker
                and start_marker.get("kind") == "start"
                and int(start_marker.get("page", -1)) == start_page_value
                else 0.0
            )
            end_y = (
                float(end_marker["y_pdf"])
                if end_marker
                and end_marker.get("kind") == "end"
                and int(end_marker.get("page", -1)) == end_page_value
                else None
            )
            same_page_candidates = candidates.loc[candidates["page"] == start_page_value]
            heading_text = (
                str(same_page_candidates.iloc[0]["text"])
                if not same_page_candidates.empty
                else "Zona bibliográfica seleccionada por páginas"
            )
            spec = ManualZoneSpec(
                start_page=start_page_value,
                start_y=start_y,
                end_page=end_page_value,
                end_y=end_y,
                heading_text=heading_text,
                note=note,
            )
            manual_lines = (
                layout_lines
                if layout_lines is not None
                else extract_layout_lines_range(pdf_path, start_page_value, end_page_value)
            )
            manual = process_manual_zone(
                pdf_path,
                spec,
                manual_lines,
                zone_id=_next_zone_id(st.session_state.zones_df),
            )
            refs = st.session_state.references_df.copy()
            zones = st.session_state.zones_df.copy()
            if replace_overlap:
                if not refs.empty and "zone_start_page" in refs:
                    refs = refs.loc[
                        ~refs.apply(
                            lambda row: _overlaps(row, spec.start_page, spec.end_page), axis=1
                        )
                    ]
                if not zones.empty and "start_page" in zones:
                    zones = zones.loc[
                        ~zones.apply(
                            lambda row: _overlaps(row, spec.start_page, spec.end_page), axis=1
                        )
                    ]
            st.session_state.references_df = pd.concat(
                [refs, pd.DataFrame(add_audit_columns(manual["records"]))],
                ignore_index=True,
            )
            st.session_state.zones_df = pd.concat(
                [zones, pd.DataFrame([manual["zone"]])], ignore_index=True
            )
            st.session_state.manual_specs.append(manual["spec"])
            st.session_state.pending_start = None
            st.session_state.pending_end = None
            st.session_state.suggested_end_page = None
            st.session_state.last_extraction_message = (
                f"Extracción terminada: {len(manual['records'])} segmentos en las páginas "
                f"{start_page_value}–{end_page_value}. Revisalos en «Resultado»."
            )
            st.rerun()

        with st.expander("Ajuste fino dentro de una página (opcional)"):
            st.caption(
                "Usalo sólo si la bibliografía empieza o termina a mitad de una página. "
                "Seleccioná la página, hacé clic sobre el punto exacto y guardalo."
            )
            st.session_state.setdefault("page_to_mark", int(zone_start_page))
            page_number = st.number_input(
                "Página para el ajuste fino",
                min_value=1,
                max_value=page_count,
                step=1,
                key="page_to_mark",
            )
            mode = st.radio(
                "Qué marca el clic",
                ["Inicio exacto", "Final exacto"],
                horizontal=True,
            )
            png = _render_cached(str(pdf_path), pdf_digest, int(page_number), 1.45)
            image = Image.open(__import__("io").BytesIO(png))
            click = streamlit_image_coordinates(
                image,
                width=min(760, image.width),
                key=f"page_click_{page_number}_{mode}",
            )
            if click:
                rendered_width = float(click.get("width") or min(760, image.width))
                rendered_height = float(
                    click.get("height") or image.height * rendered_width / image.width
                )
                pdf_width, pdf_height = page_dimensions(pdf_path, int(page_number))
                y_pdf = float(click["y"]) * pdf_height / rendered_height
                x_pdf = float(click["x"]) * pdf_width / rendered_width
                click_lines = (
                    layout_lines
                    if layout_lines is not None
                    else extract_layout_lines_range(pdf_path, int(page_number), int(page_number))
                )
                close_line = nearest_line(click_lines, int(page_number), y_pdf)
                st.caption(
                    f"Clic: página {page_number}, x={x_pdf:.1f}, y={y_pdf:.1f}. "
                    f"Línea cercana: {close_line.text if close_line else 'sin texto próximo'}"
                )
                if st.button("Guardar ajuste"):
                    marker = {
                        "kind": "start" if mode.startswith("Inicio") else "end",
                        "page": int(page_number),
                        "x_pdf": round(x_pdf, 2),
                        "y_pdf": round(close_line.y0 if close_line else y_pdf, 2),
                        "nearest_text": close_line.text if close_line else "",
                    }
                    key = "pending_start" if marker["kind"] == "start" else "pending_end"
                    st.session_state[key] = marker
                    st.session_state.manual_clicks.append(marker)
                    if marker["kind"] == "start":
                        st.session_state.requested_zone_start_page = int(page_number)
                    else:
                        st.session_state.requested_zone_end_page = int(page_number)
                    st.rerun()

            start = st.session_state.get("pending_start")
            end = st.session_state.get("pending_end")
            st.write("**Inicio exacto guardado:**", start or "—")
            st.write("**Final exacto guardado:**", end or "—")

with tabs[2]:
    st.subheader("Paquete de auditoría")
    st.write(
        "El ZIP incluye CSV, un Excel con tres hojas, el reporte JSON, los clics manuales y capturas de las páginas relevantes."
    )
    clicks_df = pd.DataFrame(st.session_state.manual_clicks)
    screenshot_pages = []
    if not st.session_state.zones_df.empty:
        for column in ("start_page", "end_page"):
            if column in st.session_state.zones_df:
                screenshot_pages.extend(
                    pd.to_numeric(st.session_state.zones_df[column], errors="coerce").dropna().astype(int).tolist()
                )
    screenshot_pages.extend([item.get("page") for item in st.session_state.manual_clicks])
    report_for_export = dict(report)
    report_for_export["probable_reference_regions"] = probable_regions
    bundle = build_audit_bundle(
        pdf_path,
        report_for_export,
        st.session_state.references_df,
        st.session_state.zones_df,
        clicks_df,
        screenshot_pages,
    )
    stem = pdf_path.stem
    st.download_button(
        "Descargar paquete completo de auditoría",
        data=bundle,
        file_name=f"biblioref_audit_{stem}.zip",
        mime="application/zip",
        type="primary",
    )
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "CSV de referencias",
        dataframe_csv_bytes(st.session_state.references_df),
        file_name=f"{stem}_references_audited.csv",
        mime="text/csv",
    )
    c2.download_button(
        "CSV de zonas",
        dataframe_csv_bytes(st.session_state.zones_df),
        file_name=f"{stem}_zones_audited.csv",
        mime="text/csv",
    )
    c3.download_button(
        "Excel de auditoría",
        workbook_bytes(st.session_state.references_df, st.session_state.zones_df, clicks_df),
        file_name=f"{stem}_biblioref_audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
