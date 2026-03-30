import os
import subprocess
import tempfile
import unittest

from html2text_rs_py import (
    analyze_html_directory_selectors_py,
    convert_html_directory_to_text,
    convert_html_file_to_text_py,
    convert_html_files_to_text_batch_py,
    extract_text_from_html_file_py,
    extract_text_from_html_py,
    text_plain,
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

    def test_directory_conversion(self):
        convert_html_directory_to_text(self.input_folder, self.output_folder)

        total_size = self.compute_total_output_size()
        print(
            f"Directory conversion test: converted {len(self.input_files)} files "
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


if __name__ == "__main__":
    unittest.main()
