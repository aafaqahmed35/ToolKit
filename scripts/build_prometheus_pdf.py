#!/usr/bin/env python3
"""
ToolKit Handbook PDF Compiler - Prometheus Complete Handbook
Compiles both authoritative Prometheus markdown source chunks into a single,
professional, publication-quality PDF deliverable: docs/prometheus/BEH_PROMETHEUS_COMPLETE_HANDBOOK.pdf.
Uses ReportLab Platypus and custom canvas layout.
"""

import os
import re
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Preformatted
)
from reportlab.pdfgen import canvas
import pymupdf


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # Suppress header and footer on cover page
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header
        header_text = "ToolKit — Backend Engineering Tools & Infrastructure Handbook | Prometheus Complete Handbook"
        self.drawString(54, letter[1] - 36, header_text)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer
        footer_left = "Phase III — Production Observability | Production Engineering Series"
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(54, 34, footer_left)
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.line(54, 46, letter[0] - 54, 46)

        self.restoreState()


def clean_inline_markdown(text):
    """Converts inline markdown like `code`, **bold**, *italic* into reportlab XML tags."""
    # Escape HTML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 1. Extract inline code
    code_tokens = []
    def repl_code(match):
        idx = len(code_tokens)
        code_tokens.append(match.group(1))
        return f"__CODE_TOKEN_{idx}__"

    text = re.sub(r'`(.*?)`', repl_code, text)

    # 2. Process Bold + Italic: ***text***
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold: **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* (word boundary or space aware)
    text = re.sub(r'(?<!\*)\*(?!\*)([^\*]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)

    # 3. Restore inline code with Prometheus Orange accent
    for idx, code_content in enumerate(code_tokens):
        formatted_code = f'<font name="Courier" color="#c2410c" size="8.5"><b>{code_content}</b></font>'
        text = text.replace(f"__CODE_TOKEN_{idx}__", formatted_code)

    return text


def format_math_expression(expr):
    """Converts LaTeX math expressions like $$\\text{SLI} = ...$$ into clean readable text."""
    t = expr.strip()
    if t.startswith("$$") and t.endswith("$$"):
        t = t[2:-2].strip()
    elif t.startswith("\\[") and t.endswith("\\]"):
        t = t[2:-2].strip()
    t = re.sub(r'\\text\{([^}]+)\}', r'\1', t)
    t = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', t)
    t = t.replace('{,}', ',')
    t = t.replace('\\times', '×')
    t = t.replace('\\%', '%')
    return t


def parse_markdown_to_flowables(md_content, styles):
    flowables = []
    lines = md_content.split("\n")
    i = 0
    n = len(lines)

    in_code_block = False
    code_block_lines = []
    code_lang = ""

    in_table = False
    table_rows = []

    while i < n:
        line = lines[i]

        # Handle Code Blocks
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip()
                code_block_lines = []
                i += 1
                continue
            else:
                in_code_block = False
                code_text = "\n".join(code_block_lines)
                clean_code = code_text.replace("\t", "    ")
                wrapped_lines = []
                for cl in clean_code.split("\n"):
                    if len(cl) > 88:
                        chunks = [cl[k:k+88] for k in range(0, len(cl), 88)]
                        wrapped_lines.extend(chunks)
                    else:
                        wrapped_lines.append(cl)
                clean_code = "\n".join(wrapped_lines)

                code_p = Preformatted(
                    clean_code,
                    styles["CodeBlock"]
                )
                code_table = Table([[code_p]], colWidths=[letter[0] - 108])
                code_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(code_table)
                flowables.append(Spacer(1, 6))
                i += 1
                continue

        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # Handle Markdown Tables
        if "|" in line and (line.strip().startswith("|") or line.strip().endswith("|")):
            if not in_table:
                in_table = True
                table_rows = []
            
            raw_cells = [c.strip() for c in line.strip().split("|")]
            if len(raw_cells) > 0 and raw_cells[0] == "":
                raw_cells = raw_cells[1:]
            if len(raw_cells) > 0 and raw_cells[-1] == "":
                raw_cells = raw_cells[:-1]

            if all(re.match(r'^:?-+:?$', c) for c in raw_cells if c):
                i += 1
                continue
            
            table_rows.append(raw_cells)
            i += 1
            continue
        elif in_table:
            # End of table
            in_table = False
            if table_rows:
                num_cols = max(len(r) for r in table_rows)
                norm_rows = []
                for idx, r in enumerate(table_rows):
                    norm_row = []
                    is_header = (idx == 0)
                    for c_idx in range(num_cols):
                        c_val = r[c_idx] if c_idx < len(r) else ""
                        c_fmt = clean_inline_markdown(c_val)
                        style_to_use = styles["TableHeader"] if is_header else styles["TableCell"]
                        norm_row.append(Paragraph(c_fmt, style_to_use))
                    norm_rows.append(norm_row)
                
                avail_width = letter[0] - 108
                col_w = avail_width / num_cols
                col_widths = [col_w] * num_cols
                if num_cols == 2:
                    col_widths = [0.30 * avail_width, 0.70 * avail_width]
                elif num_cols == 3:
                    col_widths = [0.25 * avail_width, 0.35 * avail_width, 0.40 * avail_width]
                elif num_cols == 4:
                    col_widths = [0.20 * avail_width, 0.25 * avail_width, 0.25 * avail_width, 0.30 * avail_width]

                t = Table(norm_rows, colWidths=col_widths, repeatRows=1)
                t_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ]
                for row_i in range(1, len(norm_rows)):
                    if row_i % 2 == 1:
                        t_style.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor("#fff7ed")))
                    else:
                        t_style.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.white))
                t.setStyle(TableStyle(t_style))
                flowables.append(Spacer(1, 5))
                flowables.append(t)
                flowables.append(Spacer(1, 7))

        stripped = line.strip()

        # Empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped in ["---", "***", "___", "⸻"]:
            flowables.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#cbd5e1"), spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        # Mathematical Formula Block ($$...$$ or \[...\])
        if (stripped.startswith("$$") and stripped.endswith("$$")) or (stripped.startswith("\\[") and stripped.endswith("\\]")):
            raw_math = format_math_expression(stripped)
            clean_math = clean_inline_markdown(raw_math)
            math_p = Paragraph(f"<b>Formula:</b> &nbsp; {clean_math}", styles["MathText"])
            m_table = Table([[math_p]], colWidths=[letter[0] - 108])
            m_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
                ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#fdba74")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(m_table)
            flowables.append(Spacer(1, 5))
            i += 1
            continue

        # Headings
        if stripped.startswith("# "):
            title_text = clean_inline_markdown(stripped[2:].strip())
            flowables.append(Spacer(1, 12))
            flowables.append(Paragraph(title_text, styles["DocH1"]))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        if stripped.startswith("## "):
            title_text = clean_inline_markdown(stripped[3:].strip())
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(title_text, styles["DocH2"]))
            flowables.append(Spacer(1, 3))
            i += 1
            continue

        if stripped.startswith("### "):
            title_text = clean_inline_markdown(stripped[4:].strip())
            flowables.append(Spacer(1, 7))
            flowables.append(Paragraph(title_text, styles["DocH3"]))
            flowables.append(Spacer(1, 2))
            i += 1
            continue

        if stripped.startswith("#### "):
            title_text = clean_inline_markdown(stripped[5:].strip())
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(title_text, styles["DocH4"]))
            flowables.append(Spacer(1, 2))
            i += 1
            continue

        # Checklists or Unordered list items
        if stripped.startswith("* [ ] ") or stripped.startswith("- [ ] "):
            item_text = clean_inline_markdown(stripped[6:].strip())
            box_text = f"<font name='Helvetica' color='#ea580c'><b>[  ]</b></font>  {item_text}"
            flowables.append(Paragraph(box_text, styles["ChecklistItem"]))
            i += 1
            continue

        if stripped.startswith("* [x] ") or stripped.startswith("- [x] "):
            item_text = clean_inline_markdown(stripped[6:].strip())
            box_text = f"<font name='Helvetica' color='#16a34a'><b>[&#10003;]</b></font>  {item_text}"
            flowables.append(Paragraph(box_text, styles["ChecklistItem"]))
            i += 1
            continue

        if stripped.startswith("* ") or stripped.startswith("- "):
            item_text = clean_inline_markdown(stripped[2:].strip())
            bullet_text = f"<font color='#ea580c'>&#8226;</font>  {item_text}"
            flowables.append(Paragraph(bullet_text, styles["BulletItem"]))
            i += 1
            continue

        # Numbered list items
        num_match = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if num_match:
            num = num_match.group(1)
            item_text = clean_inline_markdown(num_match.group(2).strip())
            num_fmt = f"<font name='Helvetica-Bold' color='#0f172a'>{num}.</font>  {item_text}"
            flowables.append(Paragraph(num_fmt, styles["NumberedItem"]))
            i += 1
            continue

        # Blockquote / Callout
        if stripped.startswith("> "):
            callout_text = clean_inline_markdown(stripped[2:].strip())
            p = Paragraph(callout_text, styles["CalloutText"])
            c_table = Table([[p]], colWidths=[letter[0] - 108])
            c_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
                ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#ea580c")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(c_table)
            flowables.append(Spacer(1, 5))
            i += 1
            continue

        # Standard Paragraph
        para_text = clean_inline_markdown(stripped)
        flowables.append(Paragraph(para_text, styles["Body"]))
        flowables.append(Spacer(1, 3))
        i += 1

    return flowables


def build_prometheus_pdf():
    workspace = "/Users/mohammedaafaqahmed/Desktop/ToolKit"
    chunks = [
        ("PART I: METRICS, TIME SERIES & MONITORING FUNDAMENTALS", "content/prometheus/01-prometheus-metrics-scraping-promql-fundamentals.md", "Chunk 1 of 2"),
        ("PART II: ALERTING, SLOS, RECORDING RULES, RELIABILITY & INCIDENT MASTERY", "content/prometheus/02-prometheus-alerting-slos-recording-rules-production-reliability.md", "Chunk 2 of 2"),
    ]

    out_dir = os.path.join(workspace, "docs/prometheus")
    out_pdf = os.path.join(out_dir, "BEH_PROMETHEUS_COMPLETE_HANDBOOK.pdf")

    for title, rel_path, c_label in chunks:
        full_path = os.path.join(workspace, rel_path)
        if not os.path.exists(full_path):
            print(f"Error: Required source file missing: {full_path}")
            sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    # Document Styles
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'CoverSuper',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#ea580c"),
        alignment=0,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=30,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        'CoverSubTitle',
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#334155"),
        alignment=0,
        spaceAfter=14
    ))

    styles.add(ParagraphStyle(
        'CoverMetaHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    ))

    styles.add(ParagraphStyle(
        'CoverMetaVal',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a")
    ))

    styles.add(ParagraphStyle(
        'CoverDesc',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'DocH2',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'DocH3',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#ea580c"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'DocH4',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'Body',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        'BulletItem',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'ChecklistItem',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=18,
        firstLineIndent=-12,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'NumberedItem',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#0f172a"),
        leftIndent=18,
        firstLineIndent=-12,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'CalloutText',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b")
    ))

    styles.add(ParagraphStyle(
        'MathText',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#9a3412")
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#f8fafc")
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    ))

    styles.add(ParagraphStyle(
        'PartBanner',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#ffffff"),
        alignment=1
    ))

    styles.add(ParagraphStyle(
        'PartSubtitle',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#fed7aa"),
        alignment=1
    ))

    story = []

    # ================= COVER PAGE =================
    story.append(Spacer(1, 10))
    story.append(Paragraph("TOOLKIT · BACKEND ENGINEERING HANDBOOK", styles["CoverSuper"]))
    story.append(Paragraph("PROMETHEUS COMPLETE HANDBOOK", styles["CoverTitle"]))
    story.append(Paragraph("Time-Series Metrics, PromQL, Alerting Rules, Alertmanager, SLIs/SLOs & Production Reliability", styles["CoverSubTitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#ea580c"), spaceBefore=0, spaceAfter=12))

    meta_data = [
        [Paragraph("Phase", styles["CoverMetaHeader"]), Paragraph("III — Production Observability", styles["CoverMetaVal"])],
        [Paragraph("Tool ID", styles["CoverMetaHeader"]), Paragraph("10 of 13", styles["CoverMetaVal"])],
        [Paragraph("Curriculum Scope", styles["CoverMetaHeader"]), Paragraph("Complete 2-Chunk Comprehensive Curriculum", styles["CoverMetaVal"])],
        [Paragraph("Deliverable Type", styles["CoverMetaHeader"]), Paragraph("Consolidated Tool Engineering Handbook (Release Build)", styles["CoverMetaVal"])],
        [Paragraph("Source Authority", styles["CoverMetaHeader"]), Paragraph("content/prometheus/ (01 and 02 markdown sources)", styles["CoverMetaVal"])],
        [Paragraph("Target Audience", styles["CoverMetaHeader"]), Paragraph("Backend Software Engineers, SDE-1 / SDE-2, SREs, Systems Engineers", styles["CoverMetaVal"])],
        [Paragraph("Engineering Focus", styles["CoverMetaHeader"]), Paragraph("Metrics Scrapes, Core Metric Types, PromQL Math, Alert Rules, Alertmanager Routing, Recording Rules & SLO Incident Triage", styles["CoverMetaVal"])],
    ]
    meta_table = Table(meta_data, colWidths=[130, letter[0] - 108 - 130])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    desc_text = (
        "This comprehensive handbook provides an authoritative, production-grade guide to <b>Prometheus</b> for backend and site reliability engineering. "
        "Covering three rigorous pedagogical layers—Mental Models, Practical Engineering, and Production Incident Mastery—it equips engineers "
        "to design resilient metrics collection pipelines, understand time-series data structures and scrape intervals, leverage the four core metric types "
        "(Counters, Gauges, Histograms, Summaries), master PromQL expressions (rate, increase, sum by, histogram_quantile), implement Spring Boot Actuator and "
        "Micrometer instrumentation, write actionable alerting rules, configure Alertmanager deduplication and routing, precompute expensive aggregations with "
        "recording rules, define quantitative SLIs and SLOs with burn rates, prevent high-cardinality label explosion, and systematically triage real-world production incidents."
    )
    story.append(Paragraph(desc_text, styles["CoverDesc"]))
    story.append(Spacer(1, 8))

    overview_box = [
        [Paragraph("<b>Curriculum Structure & Core Topics</b>", styles["TableHeader"])],
        [Paragraph("<b>Part I — Metrics, Time Series & Monitoring Fundamentals:</b> Time-series data architecture, metric names and label dimensions, the four core metric types (Counter, Gauge, Histogram, Summary), pull-based scraping mechanics, scrape targets, jobs, instances, exporters vs native instrumentation, Metrics vs Logs vs Traces, Spring Boot Actuator setup, PromQL basics (up, rate, increase, error ratios, histogram quantiles), and cardinality management.", styles["TableCell"])],
        [Paragraph("<b>Part II — Alerting, SLOs, Recording Rules, Production Reliability & Incident Mastery:</b> Complete alerting pipeline, anatomy of alerting rules (expr, for, labels, annotations), Alertmanager architecture (grouping, deduplication, routing, inhibition, silencing), SLIs vs SLOs vs SLAs, error budgets and burn rates, symptom vs cause alerting, recording rules, cardinality explosion prevention, security, and production incident runbooks.", styles["TableCell"])]
    ]
    ot = Table(overview_box, colWidths=[letter[0] - 108])
    ot.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ea580c")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#fff7ed")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#fdba74")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fed7aa")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ot)

    # ================= BODY CHUNKS =================
    for part_title, rel_path, c_label in chunks:
        story.append(PageBreak())

        # Chapter Banner
        banner_data = [
            [Paragraph(f"<b>{part_title}</b>", styles["PartBanner"])],
            [Paragraph(f"{c_label} · Backend Engineering Handbook", styles["PartSubtitle"])]
        ]
        bt = Table(banner_data, colWidths=[letter[0] - 108])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#334155")),
        ]))
        story.append(bt)
        story.append(Spacer(1, 14))

        # Read and parse chunk markdown
        full_path = os.path.join(workspace, rel_path)
        with open(full_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        flowables = parse_markdown_to_flowables(md_content, styles)
        story.extend(flowables)

    # Build Document
    doc = SimpleDocTemplate(
        out_pdf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Prometheus Complete Handbook successfully compiled: {out_pdf}")


if __name__ == "__main__":
    build_prometheus_pdf()
