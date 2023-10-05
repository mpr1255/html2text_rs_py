use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::fs;
use std::path::Path;
use walkdir::WalkDir;
use rayon::prelude::*;
use std::path::PathBuf;

fn collect_html_files(input_dir: &str) -> Vec<PathBuf> {
    WalkDir::new(input_dir)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .par_bridge() // Convert the sequential iterator to a parallel one
        .filter(|entry| {
            if let Some(ext) = entry.path().extension() {
                let ext_str = ext.to_str().unwrap_or("");
                ext_str == "htm" || ext_str == "html" || ext_str == "shtml"
            } else {
                false
            }
        })
        .map(|entry| entry.path().to_path_buf())
        .collect()
}


fn convert_files_to_text(files: &[PathBuf], input_dir: &str, output_dir: &str) {
    files.par_iter().for_each(|file_path| {
        if let Ok(html_content) = fs::read_to_string(&file_path) {
            let text_content = html2text::from_read(html_content.as_bytes(), 80);
            let relative_path = file_path.strip_prefix(input_dir).unwrap_or(&file_path);
            let output_path = Path::new(output_dir).join(relative_path).with_extension("txt");
            if let Some(parent) = output_path.parent() {
                fs::create_dir_all(parent).unwrap();
            }
            if let Err(_) = fs::write(&output_path, &text_content) {
                eprintln!("Error writing to file: {:?}", &output_path);
            }
        } else {
            eprintln!("Error reading file: {:?}", file_path);
        }
    });
}

fn convert_html_files_to_text_batch(input_files: &[String], output_files: &[String]) {
    input_files.par_iter().zip(output_files.par_iter()).for_each(|(input_file, output_file)| {
        if let Ok(html_content) = fs::read_to_string(input_file) {
            let text_content = html2text::from_read(html_content.as_bytes(), 80);
            if let Err(_) = fs::write(output_file, &text_content) {
                eprintln!("Error writing to file: {:?}", output_file);
            }
        } else {
            eprintln!("Error reading file: {:?}", input_file);
        }
    });
}

fn convert_html_file_to_text(input_file: &str, output_file: &str) {
    if let Ok(html_content) = fs::read_to_string(input_file) {
        let text_content = html2text::from_read(html_content.as_bytes(), 80);
        if let Err(_) = fs::write(output_file, &text_content) {
            eprintln!("Error writing to file: {:?}", output_file);
        }
    } else {
        eprintln!("Error reading file: {:?}", input_file);
    }
}

fn extract_text_from_html_file(input_file: &str) -> Result<String, std::io::Error> {
    if let Ok(html_content) = fs::read_to_string(input_file) {
        let text_content = html2text::from_read(html_content.as_bytes(), 80);
        Ok(text_content)
    } else {
        Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("Error reading file: {:?}", input_file),
        ))
    }
}

#[pyfunction]
fn extract_text_from_html_file_py(input_file: &str) -> PyResult<String> {
    match extract_text_from_html_file(input_file) {
        Ok(text_content) => Ok(text_content),
        Err(err) => Err(PyValueError::new_err(format!("Failed to extract text: {}", err))),
    }
}


#[pyfunction]
fn convert_html_directory_to_text(input_dir: &str, output_dir: &str) -> PyResult<()> {
    let paths = collect_html_files(input_dir);

    if paths.is_empty() {
        return Err(PyValueError::new_err("No HTML files found in the provided directory."));
    }

    convert_files_to_text(&paths, input_dir, output_dir);
    Ok(())
}

#[pyfunction]
fn convert_html_files_to_text_batch_py(input_files: Vec<String>, output_files: Vec<String>) -> PyResult<()> {
    if input_files.len() != output_files.len() {
        return Err(PyValueError::new_err(
            "Number of input files does not match the number of output files."
        ));
    }
    
    convert_html_files_to_text_batch(&input_files, &output_files);
    Ok(())
}

#[pyfunction]
fn convert_html_file_to_text_py(input_file: &str, output_file: &str) -> PyResult<()> {
    convert_html_file_to_text(input_file, output_file);
    Ok(())
}

#[pymodule]
fn html2text_rs_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(convert_html_directory_to_text, m)?)?;
    m.add_function(wrap_pyfunction!(convert_html_file_to_text_py, m)?)?;
    m.add_function(wrap_pyfunction!(convert_html_files_to_text_batch_py, m)?)?;
    m.add_function(wrap_pyfunction!(extract_text_from_html_file_py, m)?)?;
    Ok(())
}

