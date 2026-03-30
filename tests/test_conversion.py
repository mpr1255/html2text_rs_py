import os
import subprocess
import tempfile
import unittest

from html2text_rs_py import (
    analyze_html_directory_selectors_py,
    convert_html_file_to_text_py,
    convert_html_files_to_text_batch_py,
    extract_text_from_html_file_py,
    extract_text_from_html_py,
    text_plain,
    text_plain_from_bytes,
)


class TestHtml2TextRust(unittest.TestCase):
    def setUp(self):
        self.input_folder = "tests/test_data/input_html"
        self.input_files = [
            os.path.join(self.input_folder, file)
            for file in os.listdir(self.input_folder)
            if file.endswith((".html", ".htm"))
        ]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_folder = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def assert_directory_file_count(self):
        output_files = [file for file in os.listdir(self.output_folder) if file.endswith(".txt")]
        self.assertEqual(len(output_files), len(self.input_files))

    def compute_total_output_size(self):
        return sum(
            os.path.getsize(os.path.join(self.output_folder, file))
            for file in os.listdir(self.output_folder)
            if file.endswith(".txt")
        )

    def test_single_file_conversion(self):
        for input_file in self.input_files:
            output_file = os.path.join(
                self.output_folder, os.path.basename(input_file).replace(".html", ".txt")
            )
            convert_html_file_to_text_py(input_file, output_file)

        total_size = self.compute_total_output_size()
        print(
            f"Single file conversion test: converted {len(self.input_files)} files "
            f"with a total size of {total_size} bytes."
        )

        self.assert_directory_file_count()

    def test_batch_conversion(self):
        output_files = [
            os.path.join(self.output_folder, os.path.basename(input_file).replace(".html", ".txt"))
            for input_file in self.input_files
        ]

        convert_html_files_to_text_batch_py(self.input_files, output_files)

        total_size = self.compute_total_output_size()
        print(
            f"Batch conversion test: converted {len(self.input_files)} files "
            f"with a total size of {total_size} bytes."
        )

        self.assert_directory_file_count()

    def test_extract_text(self):
        for input_file in self.input_files:
            extracted_text = extract_text_from_html_file_py(input_file)
            self.assertIsInstance(extracted_text, str)
            self.assertGreater(len(extracted_text), 0)
        print(f"Text extraction test: successfully extracted text from {len(self.input_files)} files.")

    def test_selector_filters_for_string_input(self):
        html = """
        <html>
            <body>
                <nav class="site-nav">Menu</nav>
                <main id="content">
                    <h1>Title</h1>
                    <p>Body text</p>
                    <aside class="ad-slot">Ad copy</aside>
                </main>
                <footer>Footer text</footer>
            </body>
        </html>
        """

        unfiltered_text = text_plain(html)
        filtered_text = extract_text_from_html_py(
            html,
            exclude_selectors=["nav", ".ad-slot", "footer"],
        )
        included_text = extract_text_from_html_py(
            html,
            include_selectors=["#content"],
            exclude_selectors=[".ad-slot"],
        )

        self.assertIn("Menu", unfiltered_text)
        self.assertNotIn("Menu", filtered_text)
        self.assertNotIn("Ad copy", filtered_text)
        self.assertNotIn("Footer text", filtered_text)
        self.assertIn("Title", filtered_text)
        self.assertIn("Body text", included_text)
        self.assertNotIn("Menu", included_text)
        self.assertNotIn("Footer text", included_text)
        self.assertNotIn("Ad copy", included_text)

    def test_selector_analysis_for_directory(self):
        corpus_dir = tempfile.TemporaryDirectory()
        self.addCleanup(corpus_dir.cleanup)

        html_documents = [
            """
            <html><body>
                <nav class="site-nav">Menu</nav>
                <main id="article"><p>One</p></main>
                <footer class="site-footer">Footer</footer>
            </body></html>
            """,
            """
            <html><body>
                <nav class="site-nav">Menu 2</nav>
                <main id="article"><p>Two</p></main>
                <footer class="site-footer">Footer 2</footer>
            </body></html>
            """,
        ]

        for index, html in enumerate(html_documents):
            file_path = os.path.join(corpus_dir.name, f"doc_{index}.html")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(html)

        stats = analyze_html_directory_selectors_py(corpus_dir.name, top_k=20, min_docs=2)
        by_selector = {selector: (kind, documents, occurrences) for selector, kind, documents, occurrences in stats}

        self.assertIn(".site-nav", by_selector)
        self.assertIn("#article", by_selector)
        self.assertEqual(by_selector[".site-nav"][1], 2)
        self.assertEqual(by_selector["#article"][1], 2)

    def test_cli_selector_and_extract_smoke(self):
        corpus_dir = tempfile.TemporaryDirectory()
        self.addCleanup(corpus_dir.cleanup)

        html_file = os.path.join(corpus_dir.name, "sample.html")
        with open(html_file, "w", encoding="utf-8") as handle:
            handle.write(
                """
                <html><body>
                    <nav class="site-nav">Menu</nav>
                    <main id="content"><p>Useful text</p></main>
                </body></html>
                """
            )

        selector_run = subprocess.run(
            ["html2text-rs-py", "selectors", corpus_dir.name, "--top-k", "10", "--min-docs", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn(".site-nav", selector_run.stdout)

        extract_run = subprocess.run(
            [
                "html2text-rs-py",
                "extract",
                html_file,
                "--exclude",
                "nav",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Useful text", extract_run.stdout)
        self.assertNotIn("Menu", extract_run.stdout)

    def test_non_utf8_html_does_not_abort_analysis_or_extraction(self):
        corpus_dir = tempfile.TemporaryDirectory()
        self.addCleanup(corpus_dir.cleanup)

        html_file = os.path.join(corpus_dir.name, "latinish.html")
        html_bytes = (
            b"<html><body>"
            b"<nav class='site-nav'>Menu\x92Bar</nav>"
            b"<main id='content'><p>Useful\x96text</p></main>"
            b"</body></html>"
        )

        with open(html_file, "wb") as handle:
            handle.write(html_bytes)

        stats = analyze_html_directory_selectors_py(corpus_dir.name, top_k=20, min_docs=1)
        by_selector = {selector: (kind, documents, occurrences) for selector, kind, documents, occurrences in stats}

        self.assertIn(".site-nav", by_selector)

        extracted_text = extract_text_from_html_file_py(
            html_file,
            exclude_selectors=["nav"],
        )
        self.assertIn("Useful", extracted_text)
        self.assertNotIn("Menu", extracted_text)

    def test_shift_jis_bytes_api_uses_meta_charset(self):
        html = """
        <html>
            <head><meta charset="Shift_JIS"></head>
            <body>
                <nav>Menu</nav>
                <main id="content">
                    <h1>外務省</h1>
                    <p>国際協力の本文です。</p>
                </main>
            </body>
        </html>
        """
        html_bytes = html.encode("shift_jis")

        extracted_text = text_plain_from_bytes(
            html_bytes,
            include_selectors=["#content"],
        )

        self.assertIn("外務省", extracted_text)
        self.assertIn("国際協力", extracted_text)
        self.assertNotIn("Menu", extracted_text)

    def test_text_plain_accepts_bytes_input_directly(self):
        html = """
        <html>
            <head><meta charset="Shift_JIS"></head>
            <body>
                <main id="content">
                    <h1>外務省</h1>
                    <p>本文です。</p>
                </main>
            </body>
        </html>
        """
        html_bytes = html.encode("shift_jis")

        extracted_text = text_plain(
            html_bytes,
            include_selectors=["#content"],
        )

        alias_text = extract_text_from_html_py(
            html_bytes,
            include_selectors=["#content"],
        )

        self.assertIn("外務省", extracted_text)
        self.assertIn("本文です", extracted_text)
        self.assertEqual(extracted_text, alias_text)

    def test_shift_jis_file_api_uses_meta_charset(self):
        html_file = os.path.join(self.output_folder, "shift_jis_page.html")
        html = """
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=Shift_JIS">
            </head>
            <body>
                <nav>Menu</nav>
                <main id="content">
                    <h1>報道発表</h1>
                    <p>本文を抽出します。</p>
                </main>
            </body>
        </html>
        """

        with open(html_file, "wb") as handle:
            handle.write(html.encode("shift_jis"))

        extracted_text = extract_text_from_html_file_py(
            html_file,
            include_selectors=["#content"],
        )

        self.assertIn("報道発表", extracted_text)
        self.assertIn("本文を抽出します", extracted_text)
        self.assertNotIn("Menu", extracted_text)

    def test_strip_table_borders_flag_removes_border_only_lines(self):
        html = """
        <html>
            <body>
                <pre>
────────────────────────
本文
────────────────────────
                </pre>
            </body>
        </html>
        """

        unfiltered_text = text_plain(html)
        filtered_text = text_plain(html, strip_table_borders=True)

        self.assertIn("────────────────────────", unfiltered_text)
        self.assertIn("本文", filtered_text)
        self.assertNotIn("────────────────────────", filtered_text)

    def test_strip_table_borders_flattens_simple_archive_table(self):
        html = """
        <html>
            <body>
                <center>
                    <b>過去の記録</b><br>
                    <table border="0" cellspacing="0" cellpadding="2" width="550">
                        <tr align="left" valign="top">
                            <td nowrap><img src="image/button_y.gif" alt="・"></td>
                            <td><a href="16/rls_0531b.html">日・オランダ租税条約改正に向けた第1回正式交渉の開催について</a></td>
                            <td nowrap>（平成16年5月31日）</td>
                        </tr>
                        <tr align="left" valign="top">
                            <td nowrap><img src="image/button_y.gif" alt="・"></td>
                            <td><a href="16/rls_0531a.html">インドの「ポリオ撲滅計画」のためのユニセフに対する無償資金協力について</a></td>
                            <td nowrap>（平成16年5月31日）</td>
                        </tr>
                    </table>
                </center>
            </body>
        </html>
        """

        flattened_text = text_plain(
            html,
            include_selectors=["body center"],
            strip_table_borders=True,
            width=10000,
        )

        self.assertIn("過去の記録", flattened_text)
        self.assertIn("・ [日・オランダ租税条約改正に向けた第1回正式交渉の開催について][1] （平成16年5月31日）", flattened_text)
        self.assertIn("・ [インドの「ポリオ撲滅計画」のためのユニセフに対する無償資金協力について][2] （平成16年5月31日）", flattened_text)
        self.assertNotIn("│", flattened_text)


if __name__ == "__main__":
    unittest.main()
