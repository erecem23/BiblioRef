from tools.human_gold.visual_stress import difficulty_score, rank_stress_profiles, visual_labels


def profile(**overrides):
    row = {
        "page_count": 120,
        "sample_count": 5,
        "landscape_share": 0.0,
        "aspect_ratio_span": 0.0,
        "median_ink_fraction": 0.10,
        "ink_fraction_span": 0.03,
        "two_column_like_share": 0.0,
    }
    row.update(overrides)
    return row


def test_visual_labels_use_only_render_geometry_and_density_features():
    labels = visual_labels(profile(
        page_count=520,
        landscape_share=0.4,
        aspect_ratio_span=0.25,
        median_ink_fraction=0.24,
        two_column_like_share=0.6,
    ))
    assert set(labels) >= {
        "very_long_document",
        "landscape_pages",
        "mixed_page_geometry",
        "dense_render",
        "two_column_like",
    }


def test_difficulty_score_increases_with_visual_complexity():
    simple = difficulty_score(profile())
    complex_ = difficulty_score(profile(
        page_count=500,
        landscape_share=0.2,
        aspect_ratio_span=0.2,
        median_ink_fraction=0.25,
        ink_fraction_span=0.15,
        two_column_like_share=0.6,
    ))
    assert complex_ > simple


def test_rank_stress_profiles_is_deterministic_and_marks_pre_biblioref_selection():
    rows = [{"document_id": f"d{i:02d}"} for i in range(10)]
    profiles = {row["document_id"]: profile(page_count=100 + i * 50) for i, row in enumerate(rows)}
    first = rank_stress_profiles(rows, profiles, n=8, selection_seed=20260913)
    second = rank_stress_profiles(list(reversed(rows)), profiles, n=8, selection_seed=20260913)
    assert [row["document_id"] for row in first] == [row["document_id"] for row in second]
    assert all(row["selected_before_biblioref_run"] is True for row in first)
    assert all(row["visual_difficulty_labels"] for row in first)
    assert all(row["visual_profile_method"] == "pdfium_raster_geometry_v1" for row in first)
