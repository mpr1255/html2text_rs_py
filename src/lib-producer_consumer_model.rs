use pyo3::prelude::*;
use std::fs;
use std::path::Path;
use walkdir::WalkDir;
use std::thread;
use std::sync::mpsc;
use rayon::prelude::*;

const MAX_FILES_IN_FLIGHT: usize = 1000; // adjust as needed

#[pyfunction]
fn convert_html_directory_to_text(input_dir: &str, output_dir: &str) -> PyResult<()> {
    // Convert the borrowed &str to owned String
    let input_dir = input_dir.to_string();
    let output_dir = output_dir.to_string();

    let (tx, rx) = mpsc::sync_channel(MAX_FILES_IN_FLIGHT);

    // Producer thread: Walks the directory and sends file paths to the consumer.
    let input_dir_clone = input_dir.clone();
    let producer = thread::spawn(move || {
        for entry in WalkDir::new(&input_dir_clone) {
            if let Ok(entry) = entry {
                println!("Processing directory: {:?}", entry.path()); 
                println!();
                if let Some(ext) = entry.path().extension() {
                    if ext == "htm" && !entry.path().file_name().unwrap().to_str().unwrap().ends_with(".htm.txt") {
                        println!("Processing file: {:?}", entry.path());
                        println!();
                        if let Err(e) = tx.send(entry.path().to_path_buf()) {
                            eprintln!("Error sending file path: {:?}", e);
                        }
                    }
                }
            } else if let Err(e) = entry {
                eprintln!("Error iterating directory: {:?}", e);
            }
        }
    });

    // Wait for the producer to finish and close the channel.
    producer.join().unwrap();

    // Collect all paths from the channel into a Vec.
    let paths: Vec<_> = rx.iter().collect();

    // Process the files in parallel using rayon.
    let input_dir_clone2 = input_dir.clone();
    paths.par_iter().for_each(|file_path| {
        let relative_path = file_path.strip_prefix(&input_dir_clone2).unwrap_or(&file_path);
        if let Ok(html_content) = fs::read_to_string(&file_path) {
            let text_content = html2text::from_read(html_content.as_bytes(), 80);
            let output_path = Path::new(&output_dir).join(relative_path).with_extension("txt");
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

    Ok(())
}

#[pymodule]
fn html2text_rs_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(convert_html_directory_to_text, m)?)?;
    Ok(())
}
