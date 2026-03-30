# html2text_rs_py

`html2text_rs_py` is a Python package backed by Rust’s [`html2text`](https://docs.rs/html2text) with two extra affordances aimed at real corpora:

1. selector-aware filtering before conversion, so you can keep or drop things like navbars, sidebars, footers, and ads
2. selector frequency analysis across a directory of HTML files, so you can quickly spot the repeated selectors worth excluding

This package is still focused on plain text output. The main value over a thin wrapper is the selector-analysis and selector-filtering workflow.

It now also handles non-UTF-8 HTML inputs more directly:

1. file and CLI paths read raw bytes and sniff BOM or `<meta charset=...>` before decoding
2. Python callers can pass raw HTML bytes directly when the upstream fetcher has not decoded the response yet

## When to use this library

This is the right tool when you have a large corpus of HTML files with broadly similar structure and you want cleaned text fast.

Typical fit:

1. the site repeats the same navigation, footer, sidebar, promo blocks, or archive chrome on every page
2. the useful content usually sits inside one or two stable selectors such as `main`, `article`, or `#content`
3. you want a simple text-cleaning pipeline, not custom DOM extraction code for every page

If you need arbitrary DOM traversal, per-site extraction logic, or lots of one-off parsing rules, stay with `bs4`/`lxml`. If you need “bulk HTML in, clean text out, with selector-based keep/drop rules,” this is the case it is built for.

## Typical corpus workflow

The fastest workflow is:

1. run selector analysis on a representative sample directory
2. inspect the repeated selectors and decide what to keep or drop
3. run extraction or directory conversion with those selectors across the whole corpus

Example CLI workflow:

```bash
html2text-rs-py selectors ./sample-html --top-k 40 --min-docs 10

# decide from the output that the good content is in #content
# and the junk is in nav, .sidebar, .footer, and .breadcrumbs
html2text-rs-py convert-dir \
  ./sample-html \
  ./clean-txt \
  --include '#content' \
  --exclude nav \
  --exclude .sidebar \
  --exclude .footer \
  --exclude .breadcrumbs
```

Example Python workflow for a directory you already have on disk:

```python
from html2text_rs_py import (
    analyze_html_directory_selectors_py,
    convert_html_directory_to_text,
)

stats = analyze_html_directory_selectors_py("./sample-html", top_k=40, min_docs=10)

for selector, kind, documents, occurrences in stats[:15]:
    print(kind, selector, documents, occurrences)

convert_html_directory_to_text(
    "./sample-html",
    "./clean-txt",
    include_selectors=["#content"],
    exclude_selectors=["nav", ".sidebar", ".footer", ".breadcrumbs"],
)
```

If your crawler has raw response bytes rather than decoded strings, use the bytes API directly:

```python
from html2text_rs_py import text_plain_from_bytes

text = text_plain_from_bytes(
    raw_html_bytes,
    include_selectors=["#content"],
    exclude_selectors=["nav", ".sidebar", ".footer", ".breadcrumbs"],
    strip_table_borders=True,
)
```

## Installation

For development builds:

```bash
uv tool install maturin
uv tool run maturin develop --release
```

If you are working inside the repo and want an ephemeral environment:

```bash
uv run --with maturin maturin develop --release
```

## Python usage

String-first extraction:

```python
from html2text_rs_py import text_plain

html = """
<html>
  <body>
    <nav class="site-nav">Menu</nav>
    <main id="content">
      <h1>Title</h1>
      <p>Body text</p>
    </main>
    <footer>Footer</footer>
  </body>
</html>
"""

text = text_plain(
    html,
    exclude_selectors=["nav", "footer"],
)
```

Include first, then exclude inside the kept subtree:

```python
from html2text_rs_py import text_plain

text = text_plain(
    html,
    include_selectors=["#content", "article"],
    exclude_selectors=[".ad-slot", ".newsletter-signup"],
)
```

Bytes-first extraction for crawlers that still have raw response bytes:

```python
from html2text_rs_py import text_plain_from_bytes

text = text_plain_from_bytes(
    raw_html_bytes,
    include_selectors=["#content", "article"],
    exclude_selectors=["nav", ".sidebar", "footer"],
)
```

If older table-layout pages produce divider art in the output, you can strip those border-only lines after rendering:

```python
text = text_plain_from_bytes(
    raw_html_bytes,
    include_selectors=["#content"],
    strip_table_borders=True,
)
```

Selector analysis across a corpus:

```python
from html2text_rs_py import analyze_html_directory_selectors_py

stats = analyze_html_directory_selectors_py("./corpus", top_k=25, min_docs=5)

for selector, kind, documents, occurrences in stats:
    print(kind, selector, documents, occurrences)
```

That selector output is meant to feed directly back into your next extraction run.

File and directory conversion still work, now with optional selector filters:

```python
from html2text_rs_py import (
    convert_html_directory_to_text,
    convert_html_file_to_text_py,
    extract_text_from_html_file_py,
)

convert_html_directory_to_text(
    "./input_html",
    "./output_txt",
    exclude_selectors=["nav", ".sidebar", "footer"],
)

convert_html_file_to_text_py(
    "page.html",
    "page.txt",
    include_selectors=["main"],
    exclude_selectors=[".ad-slot"],
)

text = extract_text_from_html_file_py(
    "page.html",
    exclude_selectors=["nav", ".sidebar"],
)
```

## CLI usage

The package exposes a console script:

```bash
html2text-rs-py selectors ./corpus --top-k 50 --min-docs 5
html2text-rs-py extract page.html --exclude nav --exclude footer
html2text-rs-py extract page.html --include '#content' --strip-table-borders
html2text-rs-py convert-file page.html page.txt --include main --exclude .ad-slot
html2text-rs-py convert-dir ./html ./txt --exclude nav --exclude .sidebar --exclude footer
```

`selectors` prints tab-separated columns:

```text
kind    selector    documents    occurrences
```

The emitted selectors are intended to be pasted directly back into `--include`, `--exclude`, `include_selectors`, or `exclude_selectors`.

## selector semantics

If both `include_selectors` and `exclude_selectors` are provided, the pipeline is:

1. keep the union of the included selector matches
2. remove any nodes inside that retained content that match the exclude selectors
3. pass the filtered HTML into `html2text`

## Notes

1. `kuchiki` is used for selector matching, node removal, and re-serialization before the final `html2text` render.
2. HTML decoding now checks BOM first, then `<meta charset=...>`, then falls back to UTF-8 handling.
3. `strip_table_borders=True` removes lines that are only table-border glyphs from old table-layout pages.
4. The selector explorer is designed to surface repeated classes, ids, tags, tag-class combos, and tag-id combos across a corpus.
5. The package version is currently `0.2.1`.
