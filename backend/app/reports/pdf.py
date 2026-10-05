from typing import Any

from fpdf import FPDF

REPLACEMENTS = {
    "≥": ">=",
    "≤": "<=",
    "–": "-",
    "—": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "…": "...",
    "⁄": "/",
    "•": "-",
}
LEVEL_COLORS = {
    "CRITICO": (180, 30, 30),
    "ALTO": (214, 98, 0),
    "MODERADO": (176, 140, 0),
    "BAJO": (40, 120, 60),
    "INFORMATIVO": (40, 90, 160),
    "SIN_DATOS": (110, 110, 110),
}


def latin1(text: Any) -> str:
    value = str(text if text is not None else "")
    for src, dst in REPLACEMENTS.items():
        value = value.replace(src, dst)
    return value.encode("latin-1", "replace").decode("latin-1")


class ReportPdf(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4")
        self.footer_text = footer_text
        self.set_auto_page_break(True, margin=20)
        self.set_margins(18, 18, 18)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=7)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 3.5, latin1(f"{self.footer_text}  Página {self.page_no()}"), align="C", new_x="LMARGIN", new_y="NEXT")


def render_pdf(report: dict[str, Any]) -> bytes:
    pdf = ReportPdf("Plataforma municipal de información de riesgo. No es SENAPRED ni un sistema oficial de alertas.")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, latin1(report["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(0, 5, latin1(f"Comuna de {report['municipality']}. Generado {report['generated_at_local']}."), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    color = LEVEL_COLORS.get(report["overall_level"], (0, 0, 0))
    pdf.set_text_color(*color)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 6, latin1(f"Nivel general calculado: {report['overall_level_label']} (cálculo de la plataforma)"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    for section in report["sections"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(235, 239, 244)
        pdf.multi_cell(0, 7, latin1(section["title"]), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        for item in section["items"]:
            pdf.set_font("Helvetica", size=9.5)
            pdf.multi_cell(0, 5, latin1(item["text"]), new_x="LMARGIN", new_y="NEXT")
            meta = []
            if item.get("data_class_label"):
                meta.append(item["data_class_label"])
            if item.get("source") and item["source"] not in meta:
                meta.append(item["source"])
            if meta:
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 4, latin1("   [" + " | ".join(meta) + "]"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
        pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, "Fuentes", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8.5)
    for source in report["sources"]:
        when = f" (actualizado {source['updated_at_local']})" if source.get("updated_at_local") else ""
        pdf.multi_cell(0, 4.5, latin1(f"- {source['source']}{when}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, latin1(report["disclaimer"]), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
