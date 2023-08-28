import os
import unittest
from html2text_rs_py import (
    convert_html_file_to_text_py,
    convert_html_files_to_text_batch_py,
    convert_html_directory_to_text,
)

class TestHtml2TextRust(unittest.TestCase):
    
    def setUp(self):
        self.input_folder = "tests/test_data/input_html"
        self.output_folder = "tests/test_data/output_txt"
        
        self.input_files = [os.path.join(self.input_folder, file) for file in os.listdir(self.input_folder) if file.endswith((".html", ".htm"))]

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    # def tearDown(self):
    #     # Cleanup after each test by removing output files
    #     for file in os.listdir(self.output_folder):
    #         os.remove(os.path.join(self.output_folder, file))

    def compute_total_output_size(self):
        return sum(os.path.getsize(os.path.join(self.output_folder, file)) for file in os.listdir(self.output_folder) if file.endswith(".txt"))

    def test_single_file_conversion(self):
        for input_file in self.input_files:
            output_file = os.path.join(self.output_folder, os.path.basename(input_file).replace('.html', '.txt'))
            convert_html_file_to_text_py(input_file, output_file)
        
        total_size = self.compute_total_output_size()
        print(f"Single File Conversion Test: Converted {len(self.input_files)} files with a total size of {total_size} bytes.")
        
        self.assertEqual(len(os.listdir(self.output_folder)), len(self.input_files))

    def test_batch_conversion(self):
        output_files = [os.path.join(self.output_folder, os.path.basename(input_file).replace('.html', '.txt')) for input_file in self.input_files]
        
        convert_html_files_to_text_batch_py(self.input_files, output_files)
        
        total_size = self.compute_total_output_size()
        print(f"Batch Conversion Test: Converted {len(self.input_files)} files with a total size of {total_size} bytes.")
        
        self.assertEqual(len(os.listdir(self.output_folder)), len(self.input_files))

    def test_directory_conversion(self):
        convert_html_directory_to_text(self.input_folder, self.output_folder)
        
        total_size = self.compute_total_output_size()
        print(f"Directory Conversion Test: Converted {len(self.input_files)} files with a total size of {total_size} bytes.")
        
        self.assertEqual(len(os.listdir(self.output_folder)), len(self.input_files))

if __name__ == '__main__':
    unittest.main()
