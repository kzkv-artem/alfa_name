from __future__ import annotations

import sqlite3
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# reportlab не умеет кириллицу штатными шрифтами — берём готовый TTF из
# matplotlib (тот же пакет уже стоит для графиков в ноутбуках), не тащим
# отдельный файл шрифта в репозиторий.
_FONT_DIR = Path(matplotlib.__file__).resolve().parent / "mpl-data" / "fonts" / "ttf"
_fonts_registered = False


def _ensure_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
    _fonts_registered = True


def build_draft_pdf(
    client: sqlite3.Row,
    program: sqlite3.Row,
    missing: list[str],
    draft_text: str,
) -> bytes:
    """Черновик заявления в PDF — не копия официальной формы ведомства
    (у большинства из 20 программ отдельного скачиваемого бланка просто нет,
    подача идёт через личный кабинет на стороннем портале), а оформленный
    документ с данными клиента и программы на основе уже сгенерированного
    agent.draft_application()."""
    _ensure_fonts()

    title_style = ParagraphStyle(
        "title", fontName="DejaVuSans-Bold", fontSize=15, leading=19, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", fontName="DejaVuSans", fontSize=11, leading=15, textColor="#444444",
    )
    h2_style = ParagraphStyle(
        "h2", fontName="DejaVuSans-Bold", fontSize=11, leading=14, spaceBefore=14, spaceAfter=4,
    )
    body_style = ParagraphStyle("body", fontName="DejaVuSans", fontSize=10.5, leading=15)
    muted_style = ParagraphStyle(
        "muted", fontName="DejaVuSans", fontSize=8.5, leading=12, textColor="#777777",
    )

    story = [
        Paragraph("Черновик заявления на меру господдержки", title_style),
        Paragraph(escape(program["name"]), subtitle_style),
        Spacer(1, 12),
        Paragraph("Заявитель", h2_style),
        Paragraph(
            f"{escape(client['full_name'])} &mdash; {escape(client['entity_type'])}, "
            f"отрасль: {escape(client['industry_code'] or 'не указана')}",
            body_style,
        ),
        Paragraph(
            f"Регион: {escape(client['region_code'] or 'не указан')}. "
            f"Бизнес зарегистрирован: {escape(client['business_registered_at'] or 'не указано')}",
            body_style,
        ),
        Paragraph("Программа", h2_style),
        Paragraph(f"Организатор: {escape(program['organizer'] or 'не указан')}", body_style),
    ]

    if missing:
        story.append(Paragraph("Недостающие документы", h2_style))
        story.append(Paragraph(escape(", ".join(missing)), body_style))

    story.append(Paragraph("Текст заявления", h2_style))
    for para in draft_text.split("\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(escape(para), body_style))
            story.append(Spacer(1, 5))

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "Черновик сформирован автоматически на основе данных банка и не является "
        "официальной формой ведомства-организатора программы. Проверьте и дополните "
        "перед подачей — актуальную форму подачи уточните на сайте организатора.",
        muted_style,
    ))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
    )
    doc.build(story)
    return buffer.getvalue()
