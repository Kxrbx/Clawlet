use pyo3::prelude::*;
use sha2::{Digest, Sha256};

#[pyfunction]
fn fast_hash(payload: &str) -> PyResult<String> {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    let digest = hasher.finalize();
    Ok(format!("{:x}", digest))
}

#[pyfunction]
fn validate_patch(patch: &str) -> PyResult<(bool, String)> {
    if !patch.contains("@@") {
        return Ok((false, "Patch must contain unified diff hunk markers (@@).".to_string()));
    }
    Ok((true, "ok".to_string()))
}

#[pymodule]
fn clawlet_rust_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fast_hash, m)?)?;
    m.add_function(wrap_pyfunction!(validate_patch, m)?)?;
    Ok(())
}
