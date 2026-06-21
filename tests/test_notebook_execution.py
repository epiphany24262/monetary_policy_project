import os
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import nbformat


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_notebook_has_no_error_outputs(path: Path) -> None:
    nb = nbformat.read(str(path), as_version=4)
    for cell_idx, cell in enumerate(nb.cells):
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error", f"error output in cell {cell_idx}"
            payload = ""
            text = output.get("text", "")
            if isinstance(text, list):
                payload += "".join(text)
            else:
                payload += str(text)
            traceback = output.get("traceback", [])
            if isinstance(traceback, list):
                payload += "".join(traceback)
            else:
                payload += str(traceback)
            assert "A module that was compiled using NumPy 1.x" not in payload
            assert "ImportError" not in payload


def _install_current_python_kernel(tmp: Path) -> str:
    kernel_name = "monetary_policy_pytest_current_python"
    kernel_dir = tmp / "kernels" / kernel_name
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                "display_name": "Monetary Policy Pytest Python",
                "language": "python",
                "env": {"PYTHONNOUSERSITE": "1"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return kernel_name


def test_final_submission_notebook_matches_root_and_is_executed():
    root = Path(__file__).resolve().parents[1]
    root_nb = root / "notebooks" / "货币政策沟通与金融市场反应.ipynb"
    nested_submission_nb = root / "final_submission" / "notebooks" / "货币政策沟通与金融市场反应.ipynb"
    submission_nb = nested_submission_nb if nested_submission_nb.exists() else root_nb
    assert submission_nb.exists()
    assert _sha256(root_nb) == _sha256(submission_nb)
    nb = nbformat.read(str(submission_nb), as_version=4)
    assert sum(1 for c in nb.cells if c.cell_type == "code" and c.get("execution_count")) >= 10
    _assert_notebook_has_no_error_outputs(root_nb)
    _assert_notebook_has_no_error_outputs(submission_nb)


def test_notebook_executes_from_start():
    root = Path(__file__).resolve().parents[1]
    source_notebook = root / "notebooks" / "货币政策沟通与金融市场反应.ipynb"
    tmp = root / ".ipython_nbconvert_tmp_test"
    notebook_copy = tmp / "货币政策沟通与金融市场反应_test.ipynb"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_notebook, notebook_copy)
    notebook = str(notebook_copy)
    kernel_name = _install_current_python_kernel(tmp)
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--execute",
        "--to",
        "notebook",
        "--inplace",
        notebook,
        "--ExecutePreprocessor.timeout=420",
        f"--ExecutePreprocessor.kernel_name={kernel_name}",
    ]
    (tmp / "profile_default").mkdir(parents=True, exist_ok=True)
    (tmp / "profile_default" / "ipython_config.py").write_text(
        "c = get_config()\nc.HistoryManager.enabled = False\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["JUPYTER_ALLOW_INSECURE_WRITES"] = "true"
    env["IPYTHONDIR"] = str(tmp)
    env["JUPYTER_PATH"] = str(tmp) + (os.pathsep + env["JUPYTER_PATH"] if env.get("JUPYTER_PATH") else "")
    env["JUPYTER_RUNTIME_DIR"] = str(tmp / "runtime")
    (tmp / "runtime").mkdir(exist_ok=True)
    proc = subprocess.run(cmd, cwd=root, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-1000:]
    nb = nbformat.read(str(notebook_copy), as_version=4)
    assert sum(1 for c in nb.cells if c.cell_type == "code" and c.get("execution_count")) >= 10
    _assert_notebook_has_no_error_outputs(notebook_copy)
    text = "\n".join(c.source for c in nb.cells)
    for required in ["Student-t EGARCH-X", "市场功效分析", "跨拟合政策语调", "股票事件级核心模型"]:
        assert required in text
