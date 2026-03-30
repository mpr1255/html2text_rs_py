# Changelog

## 0.2.1 - 2026-03-30

1. Added bytes-first extraction with `text_plain_from_bytes(...)`, so Python callers can pass raw HTML bytes directly into the selector-aware pipeline.
2. Added BOM and `<meta charset=...>` detection through `encoding_rs`, which fixes meta-declared encodings such as Shift-JIS without requiring caller-side pre-decoding.
3. Added `strip_table_borders` across the Python APIs and CLI to remove border-only lines from old table-layout pages after rendering.
4. Added regression coverage for Shift-JIS bytes, Shift-JIS files, and border-line cleanup.
5. Expanded the README and docs with a clearer corpus workflow for “many similar HTML files with predictable selectors”.

## 0.2.0 - 2026-03-30

1. Added selector-aware filtering for HTML extraction with `include_selectors` and `exclude_selectors` across the string, file, batch, and directory Python APIs.
2. Added corpus-level selector discovery with `analyze_html_directory_selectors_py(...)` to surface repeated ids, classes, tags, tag-class, and tag-id selectors.
3. Added a CLI entry point, `html2text-rs-py`, with `selectors`, `extract`, `convert-file`, and `convert-dir` subcommands for rapid selector exploration and selector-aware conversion.
4. Switched the differentiating DOM preprocessing layer to `kuchiki`, which provides CSS selection, node detachment, and HTML serialization before handing content to `html2text`.
5. Reworked the test suite to use temporary output directories and added coverage for selector filtering, selector analysis, and CLI behavior.
6. Stopped selector analysis and extraction from aborting on non-UTF-8 HTML files by switching the wrapper’s file-loading path to raw-byte reads with loss-tolerant decoding.
7. Updated package metadata and documentation for the `0.2.0` release.
