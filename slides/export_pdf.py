"""Export the four reviewed slide PNGs as a PDF handout.

Usage: python slides/export_pdf.py /path/to/rendered/slides
The editable original remains bailar.pptx.
"""

from pathlib import Path
import sys

from reportlab.pdfgen import canvas


def export(rendered: Path) -> None:
    target = Path(__file__).with_name("bailar.pdf")
    document = canvas.Canvas(str(target), pagesize=(960, 540))
    document.setTitle("Async Research Assistant - Bailar slides")
    for number in range(1, 5):
        document.drawImage(str(rendered / f"slide-{number}.png"), 0, 0, 960, 540)
        document.showPage()
    document.save()


if __name__ == "__main__":
    export(Path(sys.argv[1]))
