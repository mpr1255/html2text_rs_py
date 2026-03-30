use anyhow::{anyhow, Context, Result};
use clap::{Args, Parser, Subcommand};
use kuchiki::traits::*;
use kuchiki::NodeRef;
use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use walkdir::WalkDir;

const DEFAULT_WIDTH: usize = 80;

#[derive(Clone, Debug, Eq, PartialEq)]
struct SelectorStat {
    selector: String,
    kind: String,
    documents: usize,
    occurrences: usize,
}

#[derive(Parser, Debug)]
#[command(
    name = "html2text-rs-py",
    about = "Selector-aware HTML to text conversion and selector discovery."
)]
struct Cli {
    #[command(subcommand)]
    command: CliCommand,
}

#[derive(Subcommand, Debug)]
enum CliCommand {
    Selectors(SelectorArgs),
    Extract(ExtractArgs),
    ConvertFile(ConvertFileArgs),
    ConvertDir(ConvertDirArgs),
}

#[derive(Args, Debug)]
struct SelectorArgs {
    input_dir: String,
    #[arg(long, default_value_t = 50)]
    top_k: usize,
    #[arg(long, default_value_t = 1)]
    min_docs: usize,
}

#[derive(Args, Debug, Clone)]
struct FilterArgs {
    #[arg(long = "include")]
    include_selectors: Vec<String>,
    #[arg(long = "exclude")]
    exclude_selectors: Vec<String>,
    #[arg(long, default_value_t = DEFAULT_WIDTH)]
    width: usize,
}

#[derive(Args, Debug)]
struct ExtractArgs {
    input: String,
    #[arg(long)]
    output: Option<String>,
    #[command(flatten)]
    filter: FilterArgs,
}

#[derive(Args, Debug)]
struct ConvertFileArgs {
    input_file: String,
    output_file: String,
    #[command(flatten)]
    filter: FilterArgs,
}

#[derive(Args, Debug)]
struct ConvertDirArgs {
    input_dir: String,
    output_dir: String,
    #[command(flatten)]
    filter: FilterArgs,
}

fn collect_html_files(input_dir: &str) -> Vec<PathBuf> {
    WalkDir::new(input_dir)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .par_bridge()
        .filter(|entry| {
            entry
                .path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| matches!(ext, "htm" | "html" | "shtml"))
                .unwrap_or(false)
        })
        .map(|entry| entry.path().to_path_buf())
        .collect()
}

fn normalize_width(width: usize) -> usize {
    width.max(3)
}

fn normalize_selector_list(selectors: Option<Vec<String>>) -> Option<String> {
    let selectors = selectors
        .unwrap_or_default()
        .into_iter()
        .map(|selector| selector.trim().to_string())
        .filter(|selector| !selector.is_empty())
        .collect::<Vec<_>>();

    if selectors.is_empty() {
        None
    } else {
        Some(selectors.join(", "))
    }
}

fn node_id(node: &NodeRef) -> usize {
    Rc::as_ptr(&node.0) as usize
}

fn matching_nodes(document: &NodeRef, selectors: &str, label: &str) -> Result<Vec<NodeRef>> {
    document
        .select(selectors)
        .map_err(|_| anyhow!("Invalid {label} CSS selector list: {selectors}"))
        .map(|matches| matches.map(|matched| matched.as_node().clone()).collect())
}

fn detach_matching_nodes(document: &NodeRef, selectors: &str, label: &str) -> Result<()> {
    let nodes = matching_nodes(document, selectors, label)?;
    for node in nodes {
        node.detach();
    }
    Ok(())
}

fn has_selected_ancestor(node: &NodeRef, selected_ids: &HashSet<usize>) -> bool {
    node.ancestors()
        .skip(1)
        .any(|ancestor| selected_ids.contains(&node_id(&ancestor)))
}

fn build_included_html(document: &NodeRef, selectors: &str) -> Result<String> {
    let nodes = matching_nodes(document, selectors, "include")?;
    let mut selected_ids = HashSet::new();
    let mut html = String::new();

    for node in nodes {
        if has_selected_ancestor(&node, &selected_ids) {
            continue;
        }
        selected_ids.insert(node_id(&node));
        html.push_str(&node.to_string());
    }

    Ok(html)
}

fn filter_html(
    html_content: &str,
    include_selectors: Option<&str>,
    exclude_selectors: Option<&str>,
) -> Result<String> {
    if include_selectors.is_none() && exclude_selectors.is_none() {
        return Ok(html_content.to_string());
    }

    let mut filtered_html = if let Some(include_selectors) = include_selectors {
        let document = kuchiki::parse_html().one(html_content);
        build_included_html(&document, include_selectors)?
    } else {
        html_content.to_string()
    };

    if filtered_html.is_empty() {
        return Ok(filtered_html);
    }

    if let Some(exclude_selectors) = exclude_selectors {
        let document = kuchiki::parse_html().one(filtered_html);
        detach_matching_nodes(&document, exclude_selectors, "exclude")?;
        filtered_html = document.to_string();
    }

    Ok(filtered_html)
}

fn text_plain_from_html(
    html_content: &str,
    width: usize,
    include_selectors: Option<&str>,
    exclude_selectors: Option<&str>,
) -> Result<String> {
    let filtered_html = filter_html(html_content, include_selectors, exclude_selectors)?;
    if filtered_html.is_empty() {
        return Ok(String::new());
    }

    Ok(html2text::from_read(
        filtered_html.as_bytes(),
        normalize_width(width),
    ))
}

fn read_html_file(input_file: &str) -> Result<String> {
    fs::read_to_string(input_file)
        .with_context(|| format!("Failed to read HTML file: {input_file}"))
}

fn write_text_file(output_file: &str, text_content: &str) -> Result<()> {
    let output_path = Path::new(output_file);
    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create output directory: {}", parent.display()))?;
    }
    fs::write(output_path, text_content)
        .with_context(|| format!("Failed to write output file: {output_file}"))?;
    Ok(())
}

fn convert_html_file_to_text_impl(
    input_file: &str,
    output_file: &str,
    width: usize,
    include_selectors: Option<&str>,
    exclude_selectors: Option<&str>,
) -> Result<()> {
    let html_content = read_html_file(input_file)?;
    let text_content =
        text_plain_from_html(&html_content, width, include_selectors, exclude_selectors)?;
    write_text_file(output_file, &text_content)
}

fn convert_html_files_to_text_batch_impl(
    input_files: &[String],
    output_files: &[String],
    width: usize,
    include_selectors: Option<&str>,
    exclude_selectors: Option<&str>,
) -> Result<()> {
    input_files
        .par_iter()
        .zip(output_files.par_iter())
        .try_for_each(|(input_file, output_file)| {
            convert_html_file_to_text_impl(
                input_file,
                output_file,
                width,
                include_selectors,
                exclude_selectors,
            )
        })
}

fn convert_html_directory_to_text_impl(
    input_dir: &str,
    output_dir: &str,
    width: usize,
    include_selectors: Option<&str>,
    exclude_selectors: Option<&str>,
) -> Result<()> {
    let paths = collect_html_files(input_dir);
    if paths.is_empty() {
        return Err(anyhow!("No HTML files found in the provided directory."));
    }

    paths.par_iter().try_for_each(|file_path| {
        let relative_path = file_path.strip_prefix(input_dir).unwrap_or(file_path);
        let output_path = Path::new(output_dir)
            .join(relative_path)
            .with_extension("txt");
        convert_html_file_to_text_impl(
            &file_path.to_string_lossy(),
            &output_path.to_string_lossy(),
            width,
            include_selectors,
            exclude_selectors,
        )
    })
}

fn is_simple_css_identifier(value: &str) -> bool {
    let mut chars = value.chars();
    let Some(first) = chars.next() else {
        return false;
    };

    if !(first.is_ascii_alphabetic() || first == '_' || first == '-') {
        return false;
    }

    chars.all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
}

fn escape_attr_value(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn class_selector(value: &str) -> String {
    if is_simple_css_identifier(value) {
        format!(".{value}")
    } else {
        format!("[class~=\"{}\"]", escape_attr_value(value))
    }
}

fn id_selector(value: &str) -> String {
    if is_simple_css_identifier(value) {
        format!("#{value}")
    } else {
        format!("[id=\"{}\"]", escape_attr_value(value))
    }
}

fn selector_occurrences_in_html(html_content: &str) -> HashMap<(String, String), usize> {
    let document = kuchiki::parse_html().one(html_content);
    let mut counts = HashMap::new();

    for element in document.descendants().elements() {
        let tag = element.name.local.to_string();
        *counts
            .entry((tag.clone(), String::from("tag")))
            .or_insert(0) += 1;

        let attributes = element.attributes.borrow();

        if let Some(id) = attributes.get("id") {
            let id = id.trim();
            if !id.is_empty() {
                let id_sel = id_selector(id);
                *counts
                    .entry((id_sel.clone(), String::from("id")))
                    .or_insert(0) += 1;
                *counts
                    .entry((format!("{tag}{id_sel}"), String::from("tag_id")))
                    .or_insert(0) += 1;
            }
        }

        if let Some(class_attr) = attributes.get("class") {
            let mut seen_classes = HashSet::new();
            for class_name in class_attr.split_whitespace() {
                if !seen_classes.insert(class_name) {
                    continue;
                }
                let class_sel = class_selector(class_name);
                *counts
                    .entry((class_sel.clone(), String::from("class")))
                    .or_insert(0) += 1;
                *counts
                    .entry((format!("{tag}{class_sel}"), String::from("tag_class")))
                    .or_insert(0) += 1;
            }
        }
    }

    counts
}

fn analyze_html_directory_selectors_impl(
    input_dir: &str,
    top_k: usize,
    min_docs: usize,
) -> Result<Vec<SelectorStat>> {
    let files = collect_html_files(input_dir);
    if files.is_empty() {
        return Err(anyhow!("No HTML files found in the provided directory."));
    }

    let per_document = files
        .par_iter()
        .map(|file_path| -> Result<HashMap<(String, String), usize>> {
            let html_content = fs::read_to_string(file_path).with_context(|| {
                format!("Failed to read HTML file: {}", file_path.to_string_lossy())
            })?;
            Ok(selector_occurrences_in_html(&html_content))
        })
        .collect::<Vec<_>>();

    let mut aggregate: HashMap<(String, String), (usize, usize)> = HashMap::new();
    for document_counts in per_document {
        let document_counts = document_counts?;
        for ((selector, kind), occurrences) in document_counts {
            let entry = aggregate.entry((selector, kind)).or_insert((0, 0));
            entry.0 += 1;
            entry.1 += occurrences;
        }
    }

    let mut stats = aggregate
        .into_iter()
        .filter_map(|((selector, kind), (documents, occurrences))| {
            if documents < min_docs {
                None
            } else {
                Some(SelectorStat {
                    selector,
                    kind,
                    documents,
                    occurrences,
                })
            }
        })
        .collect::<Vec<_>>();

    stats.sort_by(|left, right| {
        right
            .documents
            .cmp(&left.documents)
            .then_with(|| right.occurrences.cmp(&left.occurrences))
            .then_with(|| left.kind.cmp(&right.kind))
            .then_with(|| left.selector.cmp(&right.selector))
    });

    if top_k > 0 && stats.len() > top_k {
        stats.truncate(top_k);
    }

    Ok(stats)
}

fn selector_stats_to_python_rows(stats: Vec<SelectorStat>) -> Vec<(String, String, usize, usize)> {
    stats
        .into_iter()
        .map(|stat| (stat.selector, stat.kind, stat.documents, stat.occurrences))
        .collect()
}

fn read_cli_input(input: &str) -> Result<String> {
    if input == "-" {
        let mut html = String::new();
        std::io::stdin()
            .read_to_string(&mut html)
            .context("Failed to read HTML from stdin")?;
        Ok(html)
    } else {
        read_html_file(input)
    }
}

fn print_selector_stats(stats: &[SelectorStat]) {
    println!("kind\tselector\tdocuments\toccurrences");
    for stat in stats {
        println!(
            "{}\t{}\t{}\t{}",
            stat.kind, stat.selector, stat.documents, stat.occurrences
        );
    }
}

fn run_cli(args: Vec<String>) -> Result<()> {
    let cli = Cli::try_parse_from(args).map_err(|err| anyhow!(err.to_string()))?;

    match cli.command {
        CliCommand::Selectors(args) => {
            let stats =
                analyze_html_directory_selectors_impl(&args.input_dir, args.top_k, args.min_docs)?;
            print_selector_stats(&stats);
        }
        CliCommand::Extract(args) => {
            let include_selectors = normalize_selector_list(Some(args.filter.include_selectors));
            let exclude_selectors = normalize_selector_list(Some(args.filter.exclude_selectors));
            let html_content = read_cli_input(&args.input)?;
            let text = text_plain_from_html(
                &html_content,
                args.filter.width,
                include_selectors.as_deref(),
                exclude_selectors.as_deref(),
            )?;
            if let Some(output_file) = args.output {
                write_text_file(&output_file, &text)?;
            } else {
                print!("{text}");
            }
        }
        CliCommand::ConvertFile(args) => {
            let include_selectors = normalize_selector_list(Some(args.filter.include_selectors));
            let exclude_selectors = normalize_selector_list(Some(args.filter.exclude_selectors));
            convert_html_file_to_text_impl(
                &args.input_file,
                &args.output_file,
                args.filter.width,
                include_selectors.as_deref(),
                exclude_selectors.as_deref(),
            )?;
        }
        CliCommand::ConvertDir(args) => {
            let include_selectors = normalize_selector_list(Some(args.filter.include_selectors));
            let exclude_selectors = normalize_selector_list(Some(args.filter.exclude_selectors));
            convert_html_directory_to_text_impl(
                &args.input_dir,
                &args.output_dir,
                args.filter.width,
                include_selectors.as_deref(),
                exclude_selectors.as_deref(),
            )?;
        }
    }

    Ok(())
}

fn to_py_result<T>(result: Result<T>) -> PyResult<T> {
    result.map_err(|err| {
        let message = err.to_string();
        if err
            .chain()
            .any(|cause| cause.downcast_ref::<std::io::Error>().is_some())
        {
            PyIOError::new_err(message)
        } else {
            PyValueError::new_err(message)
        }
    })
}

#[pyfunction(signature = (html_content, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn text_plain(
    py: Python<'_>,
    html_content: &str,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<String> {
    let include_selectors = normalize_selector_list(include_selectors);
    let exclude_selectors = normalize_selector_list(exclude_selectors);
    to_py_result(py.allow_threads(|| {
        text_plain_from_html(
            html_content,
            width,
            include_selectors.as_deref(),
            exclude_selectors.as_deref(),
        )
    }))
}

#[pyfunction(signature = (input_file, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn extract_text_from_html_file_py(
    py: Python<'_>,
    input_file: &str,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<String> {
    let include_selectors = normalize_selector_list(include_selectors);
    let exclude_selectors = normalize_selector_list(exclude_selectors);
    to_py_result(py.allow_threads(|| {
        let html_content = read_html_file(input_file)?;
        text_plain_from_html(
            &html_content,
            width,
            include_selectors.as_deref(),
            exclude_selectors.as_deref(),
        )
    }))
}

#[pyfunction(signature = (html_content, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn extract_text_from_html_py(
    py: Python<'_>,
    html_content: &str,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<String> {
    text_plain(
        py,
        html_content,
        width,
        include_selectors,
        exclude_selectors,
    )
}

#[pyfunction(signature = (input_dir, output_dir, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn convert_html_directory_to_text(
    py: Python<'_>,
    input_dir: &str,
    output_dir: &str,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<()> {
    let include_selectors = normalize_selector_list(include_selectors);
    let exclude_selectors = normalize_selector_list(exclude_selectors);
    to_py_result(py.allow_threads(|| {
        convert_html_directory_to_text_impl(
            input_dir,
            output_dir,
            width,
            include_selectors.as_deref(),
            exclude_selectors.as_deref(),
        )
    }))
}

#[pyfunction(signature = (input_files, output_files, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn convert_html_files_to_text_batch_py(
    py: Python<'_>,
    input_files: Vec<String>,
    output_files: Vec<String>,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<()> {
    if input_files.len() != output_files.len() {
        return Err(PyValueError::new_err(
            "Number of input files does not match the number of output files.",
        ));
    }

    let include_selectors = normalize_selector_list(include_selectors);
    let exclude_selectors = normalize_selector_list(exclude_selectors);
    to_py_result(py.allow_threads(|| {
        convert_html_files_to_text_batch_impl(
            &input_files,
            &output_files,
            width,
            include_selectors.as_deref(),
            exclude_selectors.as_deref(),
        )
    }))
}

#[pyfunction(signature = (input_file, output_file, width = DEFAULT_WIDTH, include_selectors = None, exclude_selectors = None))]
fn convert_html_file_to_text_py(
    py: Python<'_>,
    input_file: &str,
    output_file: &str,
    width: usize,
    include_selectors: Option<Vec<String>>,
    exclude_selectors: Option<Vec<String>>,
) -> PyResult<()> {
    let include_selectors = normalize_selector_list(include_selectors);
    let exclude_selectors = normalize_selector_list(exclude_selectors);
    to_py_result(py.allow_threads(|| {
        convert_html_file_to_text_impl(
            input_file,
            output_file,
            width,
            include_selectors.as_deref(),
            exclude_selectors.as_deref(),
        )
    }))
}

#[pyfunction(signature = (input_dir, top_k = 50, min_docs = 1))]
fn analyze_html_directory_selectors_py(
    py: Python<'_>,
    input_dir: &str,
    top_k: usize,
    min_docs: usize,
) -> PyResult<Vec<(String, String, usize, usize)>> {
    to_py_result(py.allow_threads(|| {
        analyze_html_directory_selectors_impl(input_dir, top_k, min_docs)
            .map(selector_stats_to_python_rows)
    }))
}

#[pyfunction]
fn cli_main(py: Python<'_>) -> PyResult<i32> {
    let argv = py
        .import("sys")?
        .getattr("argv")?
        .extract::<Vec<String>>()?;
    match run_cli(argv) {
        Ok(()) => Ok(0),
        Err(err) => {
            eprintln!("{err}");
            Ok(1)
        }
    }
}

#[pymodule]
fn html2text_rs_py(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(text_plain, m)?)?;
    m.add_function(wrap_pyfunction!(extract_text_from_html_file_py, m)?)?;
    m.add_function(wrap_pyfunction!(extract_text_from_html_py, m)?)?;
    m.add_function(wrap_pyfunction!(convert_html_directory_to_text, m)?)?;
    m.add_function(wrap_pyfunction!(convert_html_file_to_text_py, m)?)?;
    m.add_function(wrap_pyfunction!(convert_html_files_to_text_batch_py, m)?)?;
    m.add_function(wrap_pyfunction!(analyze_html_directory_selectors_py, m)?)?;
    m.add_function(wrap_pyfunction!(cli_main, m)?)?;
    Ok(())
}
