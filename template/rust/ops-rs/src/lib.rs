//! Python bindings for `turbojet/engine/ops/`: generated from the signatures in `port.rs` by rust-anything.
//! Regenerate with `rust-anything refresh` after changing them.

#![allow(clippy::too_many_arguments)]

use pyo3::prelude::*;

pub mod port;

fn error(message: String) -> PyErr {
    use pyo3::exceptions as e;
    let (kind, text) = message.split_once(": ").unwrap_or(("", message.as_str()));
    let text = text.to_string();
    match kind {
        "TypeError" => e::PyTypeError::new_err(text),
        "KeyError" => e::PyKeyError::new_err(text),
        "IndexError" => e::PyIndexError::new_err(text),
        "OverflowError" => e::PyOverflowError::new_err(text),
        "ZeroDivisionError" => e::PyZeroDivisionError::new_err(text),
        "AttributeError" => e::PyAttributeError::new_err(text),
        "RuntimeError" => e::PyRuntimeError::new_err(text),
        "NotImplementedError" => e::PyNotImplementedError::new_err(text),
        "LookupError" => e::PyLookupError::new_err(text),
        "ArithmeticError" => e::PyArithmeticError::new_err(text),
        "UnicodeError" => e::PyUnicodeError::new_err(text),
        "ValueError" => e::PyValueError::new_err(text),
        _ => e::PyValueError::new_err(message),
    }
}

fn aggregate_chunk_inner(
    chunk_text: String,
    options_json: String,
    first_row: i64,
) -> Result<String, String> {
    let out = port::aggregate_chunk(chunk_text, options_json, first_row)?;
    Ok(out)
}

/// `aggregate_chunk`.
#[pyfunction]
#[pyo3(name = "aggregate_chunk", signature = (chunk_text, options_json, first_row))]
fn aggregate_chunk(chunk_text: String, options_json: String, first_row: i64) -> PyResult<String> {
    aggregate_chunk_inner(chunk_text, options_json, first_row).map_err(error)
}

fn detect_delimiter_inner(header_line: String) -> Result<String, String> {
    let out = port::detect_delimiter(header_line)?;
    Ok(out)
}

/// `detect_delimiter`.
#[pyfunction]
#[pyo3(name = "detect_delimiter", signature = (header_line))]
fn detect_delimiter(header_line: String) -> PyResult<String> {
    detect_delimiter_inner(header_line).map_err(error)
}

fn preview_inner(head_text: String, max_rows: i64) -> Result<String, String> {
    let out = port::preview(head_text, max_rows)?;
    Ok(out)
}

/// `preview`.
#[pyfunction]
#[pyo3(name = "preview", signature = (head_text, max_rows))]
fn preview(head_text: String, max_rows: i64) -> PyResult<String> {
    preview_inner(head_text, max_rows).map_err(error)
}

#[pymodule]
#[pyo3(name = "_native")]
fn native_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(aggregate_chunk, m)?)?;
    m.add_function(wrap_pyfunction!(detect_delimiter, m)?)?;
    m.add_function(wrap_pyfunction!(preview, m)?)?;
    Ok(())
}
