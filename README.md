# html2text_rs_py
A Python library backed by Rust's [html2text](https://docs.rs/html2text) to convert HTML to plain text. The project leverages the power of Rust to ensure fast and efficient operations, while providing an easy-to-use Python interface.

Note this entire thing was done with GPT-4 and it's my first time touching Rust -- just a bit of a weekend sidequest/learning experience. As a wise man once said: *"I'm in the arena trying stuff. Some will work, some won't. But always learning."*

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Note on benchmarks](#Note-on-benchmarks)
- [Benchmarks](#Benchmarks)

## Installation

### Prerequisites:
1. Ensure you have both [Rust](https://www.rust-lang.org/tools/install) and Python installed on your machine.
2. Install `maturin`:

```bash
pip install maturin
```

### Building and Installing:

#### Option 1: Use precompiled binaries from PyPI
You can use the precompiled binaries available on PyPI. This means you don't need to compile anything yourself, and the Rust toolchain is not required.

```bash
pip install html2text_rs_py
```

#### Option 2: Building from source:
If you prefer to compile the Rust code yourself, or if you're interested in developing, you can build directly from the source code:

1. First, ensure you have the Rust toolchain installed. If you don't have it, get it from rustup.rs.

2. Clone this repo:

```bash
git clone https://github.com/mpr1255/html2text_rs_py.git
cd html2text_rs_py
```

3. Build and install the Python package:

```bash
maturin develop --release
```

This will compile the Rust code and link it with the Python wrapper, making the module available for Python.

## Usage

After installing, you can use the Rust functions directly in Python:

```python
from html2text_rs_py import convert_html_directory_to_text, convert_html_file_to_text_py, convert_html_files_to_text_batch_py

convert_html_directory_to_text("./input_directory", "./output_directory")

# Convert a single HTML file to text
convert_html_file_to_text_py("input_file.html", "output_file.txt")

# Convert multiple HTML files to text in a batch
input_files = ["input1.html", "input2.html"]
output_files = ["output1.txt", "output2.txt"]
convert_html_files_to_text_batch_py(input_files, output_files)
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change. Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit)

## Note on benchmarks

Speed was the motivation for this little project. To make sure the comparison was 1:1, I generated a ~1gb dataset of html files that do NOT contain links  (because the Rust html2text library does not expose a flag to stop generating the hyperlinked URLs, and I don't know enough Rust to figure it out). This shows that it's only ~6x faster than the normal python implementation and only ~3x faster than the Tika... Not that great... However, I will say there is a lot of boilerplate overhead with those (multithreading) whereas this wrapper has three very simple functions you can call, and the multithreading happens for free under the hood with Rust's rayon.

## Benchmarks

| Method | Threading | Documents Processed | Total Output Size (bytes) | Errors | Time (seconds) |
| --- | --- | --- | --- | --- | --- |
| tika | single-threaded | 3007 | 1500926103 | 0 | 94.76 |
| html2text | single-threaded | 3007 | 1500340646 | 0 | 184.90 |
| tika | multi-threaded | 3007 | 1500926103 | 0 | 14.29 |
| html2text | multi-threaded | 3007 | 1500340646 | 0 | 25.65 |
| rust | multi-threaded | 3007 | 1531829273 | 0 | 3.92 |