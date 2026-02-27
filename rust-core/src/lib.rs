use pyo3::prelude::*;
use regex::Regex;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::fs;
use std::process::{Command, Stdio};
use std::time::Duration;
use wait_timeout::ChildExt;

#[pyfunction]
fn fast_hash(payload: &str) -> PyResult<String> {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    let digest = hasher.finalize();
    Ok(format!("{:x}", digest))
}

#[pyfunction]
fn validate_patch(patch: &str) -> PyResult<(bool, String)> {
    if patch.trim().is_empty() {
        return Ok((false, "Patch is empty".to_string()));
    }

    let hunk_re = Regex::new(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Regex error: {e}")))?;

    let mut saw_hunk = false;
    let mut in_hunk = false;
    let mut expected_old = 0usize;
    let mut expected_new = 0usize;
    let mut seen_old = 0usize;
    let mut seen_new = 0usize;

    for line in patch.lines() {
        if let Some(caps) = hunk_re.captures(line) {
            if in_hunk {
                if expected_old > 0 && seen_old != expected_old {
                    return Ok((
                        false,
                        format!("Old-side hunk line count mismatch: expected {expected_old}, got {seen_old}"),
                    ));
                }
                if expected_new > 0 && seen_new != expected_new {
                    return Ok((
                        false,
                        format!("New-side hunk line count mismatch: expected {expected_new}, got {seen_new}"),
                    ));
                }
            }

            saw_hunk = true;
            in_hunk = true;
            expected_old = caps
                .get(2)
                .map(|m| m.as_str().parse::<usize>().unwrap_or(1))
                .unwrap_or(1);
            expected_new = caps
                .get(4)
                .map(|m| m.as_str().parse::<usize>().unwrap_or(1))
                .unwrap_or(1);
            seen_old = 0;
            seen_new = 0;
            continue;
        }

        if !in_hunk {
            if line.starts_with("--- ") || line.starts_with("+++ ") || line.starts_with("diff ") || line.starts_with("index ") {
                continue;
            }
            continue;
        }

        if line.starts_with(' ') {
            seen_old += 1;
            seen_new += 1;
            continue;
        }
        if line.starts_with('-') {
            seen_old += 1;
            continue;
        }
        if line.starts_with('+') {
            seen_new += 1;
            continue;
        }
        if line.starts_with("\\ No newline") {
            continue;
        }
        if line.starts_with("--- ") || line.starts_with("+++ ") {
            continue;
        }

        return Ok((false, format!("Unsupported patch line in hunk: {line}")));
    }

    if !saw_hunk {
        return Ok((false, "Patch must contain at least one unified diff hunk (@@ ...).".to_string()));
    }

    if in_hunk {
        if expected_old > 0 && seen_old != expected_old {
            return Ok((
                false,
                format!("Old-side hunk line count mismatch: expected {expected_old}, got {seen_old}"),
            ));
        }
        if expected_new > 0 && seen_new != expected_new {
            return Ok((
                false,
                format!("New-side hunk line count mismatch: expected {expected_new}, got {seen_new}"),
            ));
        }
    }

    Ok((true, "ok".to_string()))
}

#[pyfunction]
fn execute_command_argv(
    argv: Vec<String>,
    cwd: String,
    timeout_seconds: f64,
) -> PyResult<(bool, i32, String, String, String)> {
    if argv.is_empty() {
        return Ok((false, -1, "".to_string(), "".to_string(), "Empty argv".to_string()));
    }

    let mut command = Command::new(&argv[0]);
    if argv.len() > 1 {
        command.args(&argv[1..]);
    }
    if !cwd.is_empty() {
        command.current_dir(cwd);
    }
    command.stdout(Stdio::piped()).stderr(Stdio::piped());

    let mut child = match command.spawn() {
        Ok(c) => c,
        Err(e) => {
            return Ok((
                false,
                -1,
                "".to_string(),
                "".to_string(),
                format!("Spawn error: {e}"),
            ))
        }
    };

    let duration = Duration::from_millis((timeout_seconds.max(0.001) * 1000.0) as u64);
    let status_opt = match child.wait_timeout(duration) {
        Ok(v) => v,
        Err(e) => {
            return Ok((
                false,
                -1,
                "".to_string(),
                "".to_string(),
                format!("Wait error: {e}"),
            ))
        }
    };

    let timed_out = status_opt.is_none();
    if timed_out {
        let _ = child.kill();
        let _ = child.wait();
    }

    let mut stdout_text = String::new();
    let mut stderr_text = String::new();

    if let Some(mut out) = child.stdout.take() {
        let mut bytes = Vec::new();
        if out.read_to_end(&mut bytes).is_ok() {
            stdout_text = String::from_utf8_lossy(&bytes).to_string();
        }
    }
    if let Some(mut err) = child.stderr.take() {
        let mut bytes = Vec::new();
        if err.read_to_end(&mut bytes).is_ok() {
            stderr_text = String::from_utf8_lossy(&bytes).to_string();
        }
    }

    if timed_out {
        return Ok((
            false,
            -1,
            stdout_text,
            stderr_text,
            format!("Command timed out after {:.1}s", timeout_seconds),
        ));
    }

    let status = status_opt.unwrap();
    let code = status.code().unwrap_or(-1);
    let success = status.success();
    let error = if success {
        "".to_string()
    } else {
        format!("Exit code: {code}")
    };

    Ok((success, code, stdout_text, stderr_text, error))
}

#[pyfunction]
fn read_text_file(path: String) -> PyResult<(bool, String, String)> {
    match fs::read_to_string(&path) {
        Ok(content) => Ok((true, content, "".to_string())),
        Err(e) => Ok((false, "".to_string(), format!("Read error: {e}"))),
    }
}

#[pyfunction]
fn write_text_file(path: String, content: String) -> PyResult<(bool, usize, String)> {
    match fs::write(&path, content.as_bytes()) {
        Ok(_) => Ok((true, content.len(), "".to_string())),
        Err(e) => Ok((false, 0usize, format!("Write error: {e}"))),
    }
}

#[pyfunction]
fn list_dir_entries(path: String) -> PyResult<(bool, Vec<(String, bool)>, String)> {
    let mut out: Vec<(String, bool)> = Vec::new();
    let entries = match fs::read_dir(&path) {
        Ok(v) => v,
        Err(e) => return Ok((false, out, format!("List error: {e}"))),
    };

    for entry in entries {
        match entry {
            Ok(item) => {
                let name = item.file_name().to_string_lossy().to_string();
                let is_dir = item.file_type().map(|ft| ft.is_dir()).unwrap_or(false);
                out.push((name, is_dir));
            }
            Err(e) => return Ok((false, out, format!("List entry error: {e}"))),
        }
    }
    out.sort_by(|a, b| a.0.cmp(&b.0));
    Ok((true, out, "".to_string()))
}

#[pymodule]
fn clawlet_rust_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fast_hash, m)?)?;
    m.add_function(wrap_pyfunction!(validate_patch, m)?)?;
    m.add_function(wrap_pyfunction!(execute_command_argv, m)?)?;
    m.add_function(wrap_pyfunction!(read_text_file, m)?)?;
    m.add_function(wrap_pyfunction!(write_text_file, m)?)?;
    m.add_function(wrap_pyfunction!(list_dir_entries, m)?)?;
    Ok(())
}
