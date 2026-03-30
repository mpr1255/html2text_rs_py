# html2text_rs_py

`html2text_rs_py` is a Python package backed by Rust’s [`html2text`](https://docs.rs/html2text) with two extra affordances aimed at real corpora:

1. selector-aware filtering before conversion, so you can keep or drop things like navbars, sidebars, footers, and ads
2. selector frequency analysis across a directory of HTML files, so you can quickly spot the repeated selectors worth excluding

This package is still focused on plain text output. The main value over a thin wrapper is the selector-analysis and selector-filtering workflow.

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

Selector analysis across a corpus:

```python
from html2text_rs_py import analyze_html_directory_selectors_py

stats = analyze_html_directory_selectors_py("./corpus", top_k=25, min_docs=5)

for selector, kind, documents, occurrences in stats:
    print(kind, selector, documents, occurrences)
```

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
2. The selector explorer is designed to surface repeated classes, ids, tags, tag-class combos, and tag-id combos across a corpus.
3. The package version is currently `0.2.0`.
