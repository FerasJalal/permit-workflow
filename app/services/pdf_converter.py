import asyncio
from pathlib import Path

from app.config import settings


async def convert_excel_to_pdf(excel_path: Path) -> Path:
    output_dir = settings.generated_path
    output_dir.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        settings.libreoffice_path,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(excel_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit {proc.returncode}): {stderr.decode()}"
        )

    pdf_path = output_dir / f"{excel_path.stem}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not generated at expected path: {pdf_path}")

    return pdf_path
