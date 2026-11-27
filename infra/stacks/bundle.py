"""Builds the Lambda package without Docker. Plain Python (no CDK imports), so it can be
run and checked on its own:

    python infra/stacks/bundle.py /tmp/bundle
"""

import compileall
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
PYTHON_VERSION = "3.13"

# Parts of LiteLLM's proxy server, which the app never runs (it uses LiteLLM as a
# library). Removing them keeps the package well under Lambda's 250 MB limit.
UNUSED_PATHS = ["litellm/proxy/_experimental", "litellm/proxy/swagger"]

# Lambda refuses packages over 250 MB unzipped. Stop the build with a clear message
# before that, rather than failing the deploy.
MAX_BUNDLE_MB = 235


def folder_size_mb(folder: Path) -> float:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1_000_000


def precompile(folder: Path) -> None:
    """Precompile every .py file so Lambda can use the bytecode as shipped.

    Lambda can't write to its code folder, and the CDK gives every file in the
    package the same fixed timestamp. Ordinary .pyc files are checked against
    the source's timestamp, so Python would reject them all and recompile on every
    cold start. Unchecked-hash .pyc files skip that check, which is safe because
    the package never changes after it's built. Measured: about half the import time.
    """
    if sys.version_info[:2] != tuple(int(p) for p in PYTHON_VERSION.split(".")):
        raise RuntimeError(f"Build with Python {PYTHON_VERSION} so the bytecode matches Lambda's runtime.")
    ok = compileall.compile_dir(
        str(folder),
        quiet=1,
        force=True,  # replace pip's timestamp-checked .pyc files too
        workers=0,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    if not ok:
        raise RuntimeError("Precompiling the Lambda package failed.")


def bundle_backend(output_dir: str) -> float:
    """Install Linux arm64 wheels, copy the app and start script, trim, check the size."""
    out = Path(output_dir)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", str(BACKEND_DIR / "requirements.txt"),
            "--target", str(out),
            "--platform", "manylinux2014_aarch64",
            "--implementation", "cp",
            "--python-version", PYTHON_VERSION,
            "--only-binary=:all:",
            "--upgrade",
            "--quiet",
        ],
        check=True,
    )
    for unused in UNUSED_PATHS:
        shutil.rmtree(out / unused, ignore_errors=True)
    shutil.copytree(
        BACKEND_DIR / "app", out / "app", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy2(BACKEND_DIR / "run.sh", out / "run.sh")
    os.chmod(out / "run.sh", 0o755)
    precompile(out)

    size = folder_size_mb(out)
    if size > MAX_BUNDLE_MB:
        raise RuntimeError(
            f"The Lambda package is {size:.0f} MB, over the {MAX_BUNDLE_MB} MB safety limit "
            "(Lambda's hard limit is 250 MB). Trim dependencies or switch to a container image."
        )
    return size


if __name__ == "__main__":
    print(f"Bundle is {bundle_backend(sys.argv[1]):.0f} MB")
