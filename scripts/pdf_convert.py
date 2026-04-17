#!/usr/bin/env python3
"""PDF conversion backend: cross-platform dispatcher.

macOS -> docx2pdf (drives Microsoft Word via AppleScript).
Linux -> libreoffice --headless --convert-to pdf.

Both backends produce a PDF next to the .docx with the same base name.
Output size is verified (>= 1 KB) to catch silent conversion failures.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


MIN_PDF_BYTES = 1024


def convert_to_pdf(docx_path) -> Path:
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"Source .docx not found: {docx_path}")
    pdf_path = docx_path.with_suffix('.pdf')

    if sys.platform == 'darwin':
        _convert_macos(docx_path, pdf_path)
    elif sys.platform.startswith('linux'):
        _convert_linux(docx_path, pdf_path)
    else:
        raise RuntimeError(f"Unsupported platform for PDF conversion: {sys.platform}")

    if not pdf_path.exists() or pdf_path.stat().st_size < MIN_PDF_BYTES:
        size = pdf_path.stat().st_size if pdf_path.exists() else 0
        raise RuntimeError(
            f"PDF conversion produced invalid output: {pdf_path} ({size} bytes)"
        )
    return pdf_path


def _convert_macos(docx_path: Path, pdf_path: Path) -> None:
    from docx2pdf import convert
    convert(str(docx_path), str(pdf_path))


def _convert_linux(docx_path: Path, pdf_path: Path) -> None:
    soffice = shutil.which('libreoffice') or shutil.which('soffice')
    if not soffice:
        raise RuntimeError(
            "libreoffice (or soffice) not installed. "
            "Install with: sudo apt-get install -y libreoffice --no-install-recommends"
        )
    outdir = pdf_path.parent
    outdir.mkdir(parents=True, exist_ok=True)
    # LibreOffice writes to <outdir>/<docx-stem>.pdf which matches pdf_path.
    proc = subprocess.run(
        [soffice, '--headless', '--convert-to', 'pdf', '--outdir',
         str(outdir), str(docx_path)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"libreoffice conversion failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Convert .docx to .pdf (cross-platform)")
    ap.add_argument('docx', type=Path)
    args = ap.parse_args()
    out = convert_to_pdf(args.docx)
    print(f"PDF_OUTPUT: {out}")
