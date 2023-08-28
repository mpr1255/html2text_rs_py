#%%
import os
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from queue import Queue
import shutil

import html2text
from pyprojroot import here
from tika import parser

from html2text_rs_py import convert_html_files_to_text_batch_py

# This will give you the project root directory, if recognizable markers (e.g., .git, .here, pyproject.toml, etc.) are present in the project.
PROJECT_ROOT = here()

# Now, define your paths relative to this `PROJECT_ROOT`:
INPUT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'test_data', 'input_html')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'test_data', 'output_txt')

lock = threading.Lock()

# Stats variables
stats = {
    'single-threaded': {
        'tika': {'count': 0, 'size': 0, 'errors': 0, 'time': 0},
        'html2text': {'count': 0, 'size': 0, 'errors': 0, 'time': 0},
        'rust': {'count': 0, 'size': 0, 'errors': 0, 'time': 0},
        'html2text_links': {'count': 0, 'size': 0, 'errors': 0, 'time': 0}
    },
    'multi-threaded': {
        'tika': {'count': 0, 'size': 0, 'errors': 0, 'time': 0},
        'html2text': {'count': 0, 'size': 0, 'errors': 0, 'time': 0},
        'html2text_links': {'count': 0, 'size': 0, 'errors': 0, 'time': 0}
    }
}



def purge_directory(directory):
    shutil.rmtree(directory)
    os.makedirs(directory)



def convert_with_rust(files, output_folder, threading_mode):
    try:
        output_files = [os.path.join(output_folder, os.path.relpath(input_file, INPUT_DIR).replace('.html', '.txt').replace('.htm', '.txt').replace(".shtml", ".txt")) for input_file in files]
        for output_file in output_files:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        convert_html_files_to_text_batch_py(files, output_files)
        
        total_size = sum([os.path.getsize(output_file) for output_file in output_files])
        return total_size, 0
    except Exception as e:
        print(f"Error with Rust batch conversion: {e}")
        return 0, len(files)


def convert_with_tika(file_path, output_folder, threading_mode):
    try:
        parsed = parser.from_file(file_path)
        content = parsed['content']
        save_to_txt(file_path, content, output_folder, 'tika')
        return len(content), 0
    except Exception as e:
        print(f"Error with Tika on file {file_path}: {e}")
        return 0, 1

def convert_with_html2text(file_path, output_folder, threading_mode):
    try:
        with open(file_path, 'r') as f:
            html_content = f.read()
        text_maker = html2text.HTML2Text()
        text_maker.ignore_links = True
        text_content = text_maker.handle(html_content)
        save_to_txt(file_path, text_content, output_folder, 'html2text')
        return len(text_content), 0
    except Exception as e:
        print(f"Error with html2text on file {file_path}: {e}")
        return 0, 1

def convert_with_html2text_links(file_path, output_folder, threading_mode):
    try:
        with open(file_path, 'r') as f:
            html_content = f.read()
        text_maker = html2text.HTML2Text()
        text_maker.ignore_links = False
        text_content = text_maker.handle(html_content)
        save_to_txt(file_path, text_content, output_folder, 'html2text_links')
        return len(text_content), 0
    except Exception as e:
        print(f"Error with html2text_links on file {file_path}: {e}")
        return 0, 1


def save_to_txt(original_path, content, base_output_folder, method):
    # relative_path = os.path.relpath(original_path, './html')
    relative_path = os.path.relpath(original_path, INPUT_DIR)
    output_path = os.path.join(base_output_folder, method, os.path.splitext(relative_path)[0] + '.txt')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(content)

def threaded_process(conversion_function, file_queue, output_folder, method, threading_mode):
    local_count = 0
    local_size = 0
    local_errors = 0
    
    while not file_queue.empty():
        file_path = file_queue.get()
        size, errors = conversion_function(file_path, output_folder, threading_mode)
        local_count += 1
        local_size += size
        local_errors += errors
    
    with lock:
        stats[threading_mode][method]['count'] += local_count
        stats[threading_mode][method]['size'] += local_size
        stats[threading_mode][method]['errors'] += local_errors

def worker_function(conversion_function, files, output_folder, method, threading_mode):
    local_count = 0
    local_size = 0
    local_errors = 0
    
    for file_path in files:
        size, errors = conversion_function(file_path, output_folder, threading_mode)
        local_count += 1
        local_size += size
        local_errors += errors
        
    return local_count, local_size, local_errors

def convert(files, output_folder, method, num_threads=8):
    if num_threads == 1:
        threading_mode = 'single-threaded'
    else:
        threading_mode = 'multi-threaded'
        
    start_time = time.time()

    if method == 'tika':
        conversion_function = convert_with_tika
    elif method == 'html2text':
        conversion_function = convert_with_html2text
    elif method == 'html2text_links':
        conversion_function = convert_with_html2text_links
    elif method == 'rust':
        conversion_function = convert_with_rust
    else:
        raise ValueError("Invalid method")

    if num_threads == 1:
        for file_path in files:
            size, errors = conversion_function(file_path, output_folder, threading_mode)
            stats[threading_mode][method]['count'] += 1
            stats[threading_mode][method]['size'] += size
            stats[threading_mode][method]['errors'] += errors
    else:
        chunks = [files[i::num_threads] for i in range(num_threads)]
        if method == 'html2text':  # Use ProcessPool for html2text
            with ProcessPoolExecutor(max_workers=num_threads) as executor:
                results = list(executor.map(worker_function, [conversion_function]*num_threads, chunks, [output_folder]*num_threads, [method]*num_threads, [threading_mode]*num_threads))
        else:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                results = list(executor.map(worker_function, [conversion_function]*num_threads, chunks, [output_folder]*num_threads, [method]*num_threads, [threading_mode]*num_threads))

        for count, size, errors in results:
            stats[threading_mode][method]['count'] += count
            stats[threading_mode][method]['size'] += size
            stats[threading_mode][method]['errors'] += errors
    
    stats[threading_mode][method]['time'] = time.time() - start_time

def get_all_html_files(folder_path):
    return [os.path.join(root, f) for root, dirs, files in os.walk(folder_path) for f in files if f.endswith(('.html', '.htm', '.shtml'))]

# def save_results_to_file(filename="./results.txt"):
#     with open(filename, "w") as f:
#         for threading_mode, methods in stats.items():
#             f.write(f"\n{threading_mode.capitalize()} Statistics:\n")
#             print(f"\n{threading_mode.capitalize()} Statistics:")
#             for method, data in methods.items():
#                 result_string = (
#                     f"\nMethod: {method}\n"
#                     f"Documents Processed: {data['count']}\n"
#                     f"Total Output Size: {data['size']} bytes\n"
#                     f"Errors Encountered: {data['errors']}\n"
#                     f"Time Taken: {data['time']} seconds\n"
#                 )
#                 print(result_string)
#                 f.write(result_string)


def compare_conversion_speed(input_folder=INPUT_DIR, output_folder=OUTPUT_DIR):
    files = get_all_html_files(input_folder)
    
    print("\nStarting benchmarks...\n")
    
    # Handle multi-threaded conversion for 'tika' and 'html2text'
    for method in ['tika', 'html2text']:
        for num_threads in [1, 8]:
            print(f"\nConverting with {method} using {num_threads} thread(s)...\n")
            
            # Purge the output directory before each run
            purge_directory(output_folder)
            
            convert(files, output_folder, method, num_threads)
    
    purge_directory(output_folder)

    print(f"\nConverting with html2text with links using 8 threads...\n")
    convert(files, output_folder, 'html2text_links', num_threads=8)
    # Separately handle multi-threaded conversion for 'html2text_links'

    # Handle single-threaded conversion for 'rust'
    print(f"\nConverting with rust using 1 thread...\n")
    
    # Purge the output directory before Rust conversion
    purge_directory(output_folder)
    
    # Since Rust is using batch processing, we don't use the threaded_process function, and directly call the conversion function
    start_time = time.time()  # Set the start time before Rust conversion
    size, errors = convert_with_rust(files, output_folder, 'single-threaded')
    stats['single-threaded']['rust']['count'] += len(files)
    stats['single-threaded']['rust']['size'] += size
    stats['single-threaded']['rust']['errors'] += errors
    stats['single-threaded']['rust']['time'] = time.time() - start_time

    # Move rust stats to multi-threaded
    stats['multi-threaded']['rust'] = stats['single-threaded']['rust']
    del stats['single-threaded']['rust']

    # save_results_to_file()


def generate_markdown_table():
    headers = ["Method", "Threading", "Documents Processed", "Total Output Size (bytes)", "Errors", "Time (seconds)"]
    table = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]

    methods_order = ['tika', 'html2text', 'html2text_links', 'rust']  # Define a specific order to ensure Rust comes last

    for threading_mode in stats.keys():
        for method in methods_order: 
            # If the method is 'html2text_links' and the threading mode is 'single-threaded', continue
            if method == 'html2text_links' and threading_mode == 'single-threaded':
                continue
                
            if method in stats[threading_mode]:  # Check to ensure the method exists for that threading mode
                data = stats[threading_mode][method]
                row = [
                    method,
                    threading_mode,
                    str(data['count']),
                    str(data['size']),
                    str(data['errors']),
                    "{:.2f}".format(data['time'])
                ]
                table.append("| " + " | ".join(row) + " |")
    
    return "\n".join(table)



def update_readme_with_results():
    markdown_table = generate_markdown_table()
    
    # Read current README contents
    with open("README.md", "r") as f:
        content = f.read()

    # Split at Benchmark Results, if present
    if "## Benchmarks" in content:
        content = content.split("## Benchmarks")[0]

    content = content.rstrip()  # Remove any trailing newlines or spaces
    
    # Write back to README with updated results
    with open("README.md", "w") as f:
        f.write(content)
        f.write("\n\n## Benchmarks\n\n")
        f.write(markdown_table)

if __name__ == "__main__":
    compare_conversion_speed()
    update_readme_with_results()
