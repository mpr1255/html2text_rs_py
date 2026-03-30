# html2text_rs_py docs

## Main Python functions

`text_plain(html_content: str | bytes, width: int = 80, include_selectors: list[str] | None = None, exclude_selectors: list[str] | None = None, strip_table_borders: bool = False) -> str`

Converts HTML text or HTML bytes to plain text, optionally keeping only selected subtrees or removing unwanted selectors before rendering.

`text_plain_from_bytes(html_bytes: bytes, width: int = 80, include_selectors: list[str] | None = None, exclude_selectors: list[str] | None = None, strip_table_borders: bool = False) -> str`

Accepts raw HTML bytes, sniffs BOM or `<meta charset=...>`, decodes with `encoding_rs`, then applies the same selector-aware extraction pipeline.

This is the preferred entry point when your fetcher already has raw response bytes and you do not want caller-side charset handling.

`extract_text_from_html_py(...) -> str`

Alias-style string input helper with the same selector options as `text_plain`.

`extract_text_from_html_file_py(input_file: str, width: int = 80, include_selectors: list[str] | None = None, exclude_selectors: list[str] | None = None, strip_table_borders: bool = False) -> str`

Reads an HTML file, optionally filters by selectors, and returns plain text.

`convert_html_file_to_text_py(input_file: str, output_file: str, width: int = 80, include_selectors: list[str] | None = None, exclude_selectors: list[str] | None = None, strip_table_borders: bool = False) -> None`

Converts one HTML file to one text file.

`convert_html_files_to_text_batch_py(input_files: list[str], output_files: list[str], width: int = 80, include_selectors: list[str] | None = None, exclude_selectors: list[str] | None = None, strip_table_borders: bool = False) -> None`

Converts many HTML files in parallel.

`analyze_html_directory_selectors_py(input_dir: str, top_k: int = 50, min_docs: int = 1) -> list[tuple[str, str, int, int]]`

Analyzes a corpus of HTML files and returns tuples of:

`(selector, kind, documents, occurrences)`

Kinds include:

1. `tag`
2. `class`
3. `id`
4. `tag_class`
5. `tag_id`

## CLI

The installed console script is:

`html2text-rs-py`

Supported subcommands:

1. `selectors INPUT_DIR --top-k 50 --min-docs 5`
2. `extract INPUT_FILE --include main --exclude nav --strip-table-borders --source-url https://example.com/page.html`
3. `convert-file INPUT_FILE OUTPUT_FILE --exclude nav --exclude footer`

## selector pipeline

When both include and exclude selectors are present:

1. include selectors are applied first
2. exclude selectors are applied to the retained HTML
3. the filtered HTML is rendered to plain text with `html2text`

## Decoding behavior

1. BOM is honored when present.
2. Otherwise the library inspects early `<meta>` tags for `charset=...`.
3. If neither is available, it falls back to UTF-8 handling without aborting.
