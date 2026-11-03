# Extraction core non-regression manifests

This directory preserves the versioned SHA-256 manifests recording deliberate
changes and byte-for-byte invariants in BiblioRef's extraction engine.

- Each `EXTRACTION_CORE_NONREGRESSION*.json` file is historical evidence.
- File paths **inside each manifest** are relative to the **repository root**,
  not this directory. Their contents were not altered by this reorganization.
- Tests in `tests_core/` resolve manifests from this directory and validate
  source-file hashes against repository-root paths.
- When declaring a new extraction algorithm version, place its non-regression
  manifest here and update or add the corresponding tests.
- Git retains the original file history; the move is content-preserving.

Do not regenerate or delete historical manifests solely to tidy up the tree.
