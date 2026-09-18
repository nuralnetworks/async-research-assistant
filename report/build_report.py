"""Build Bailar's contribution PDF with reportlab (document tool dependency)."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


def build() -> None:
    root = Path(__file__).resolve().parent
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Copy", fontName="Helvetica", fontSize=10.5, leading=15,
        textColor=colors.HexColor("#25364A"), spaceAfter=9, alignment=TA_LEFT,
    ))
    styles["Title"].textColor = colors.HexColor("#153B57")
    styles["Heading2"].textColor = colors.HexColor("#087E8B")
    styles["Heading2"].keepWithNext = True
    story = []
    for block in root.joinpath("report.md").read_text(encoding="utf-8").split("\n\n"):
        text = " ".join(block.splitlines()).strip()
        if not text:
            continue
        style = "Copy"
        if text.startswith("# "):
            text, style = text[2:], "Title"
        elif text.startswith("## "):
            text, style = text[3:], "Heading2"
            if text == "Measured verification":
                story.append(PageBreak())
        story.append(Paragraph(escape(text.replace("`", "")), styles[style]))
        if style == "Title":
            story.append(Spacer(1, 8))

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(48, 30, "Bailar / Contribution report / 18 September 2026")
        canvas.drawRightString(A4[0] - 48, 30, str(doc.page))

    SimpleDocTemplate(
        str(root / "report.pdf"), pagesize=A4, rightMargin=48, leftMargin=48,
        topMargin=42, bottomMargin=50, title="Async Research Assistant - Bailar",
        author="Bailar (AI-assisted draft)",
    ).build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    build()
