#%%
import os
import random
import string
from pyprojroot import here
PROJECT_ROOT = here()
INPUT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'test_data', 'input_html')

def generate_random_text(length):
    return ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=length))

def generate_random_html_content():
    num_tags = random.randint(1, 3)
    tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'strong', 'em', 'i', 'b', 'u', 'blockquote']
    content = ''
    
    for _ in range(num_tags):
        tag = random.choice(tags)
        length = random.randint(20, 30)
        text = generate_random_text(length)
        content += f'<{tag}>{text}</{tag}>\n'
    
    return content

def generate_html_file(file_path):
    html_content = generate_random_html_content()
    with open(file_path, 'w') as f:
        f.write(html_content)

def main():
    output_dir = INPUT_DIR
    num_files = 10
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(num_files):
        file_path = os.path.join(output_dir, f'file_{i}.html')
        generate_html_file(file_path)

if __name__ == '__main__':
    main()
