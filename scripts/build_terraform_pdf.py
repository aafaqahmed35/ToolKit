#!/usr/bin/env python3
"""
ToolKit Handbook PDF Compiler - Terraform Complete Handbook
Compiles all three authoritative Terraform markdown source chunks into a single,
professional, publication-quality PDF deliverable: docs/terraform/BEH_TERRAFORM_COMPLETE_HANDBOOK.pdf.
Uses ReportLab Platypus and custom canvas layout with Terraform Purple (#7b42bc) styling.
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
        header_text = "ToolKit — Backend Engineering Tools & Infrastructure Handbook | Terraform Complete Handbook"
        self.drawString(54, letter[1] - 36, header_text)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer
        footer_left = "Phase IV — Container Orchestration & Cloud Infrastructure | Production Engineering Series"
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

    # 3. Restore inline code with Terraform Purple accent
    for idx, code_content in enumerate(code_tokens):
        formatted_code = f'<font name="Courier" color="#6b21a8" size="8.5"><b>{code_content}</b></font>'
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

                CHUNK_SIZE = 35
                if len(wrapped_lines) <= CHUNK_SIZE:
                    clean_code = "\n".join(wrapped_lines)
                    code_p = Preformatted(clean_code, styles["CodeBlock"])
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
                else:
                    flowables.append(Spacer(1, 4))
                    for chunk_idx in range(0, len(wrapped_lines), CHUNK_SIZE):
                        sub_chunk = wrapped_lines[chunk_idx:chunk_idx + CHUNK_SIZE]
                        code_p = Preformatted("\n".join(sub_chunk), styles["CodeBlock"])
                        code_table = Table([[code_p]], colWidths=[letter[0] - 108])
                        code_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
                            ('LEFTPADDING', (0, 0), (-1, -1), 10),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        flowables.append(code_table)
                        if chunk_idx + CHUNK_SIZE < len(wrapped_lines):
                            flowables.append(Spacer(1, 3))
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
                    col_widths = [0.28 * avail_width, 0.72 * avail_width]
                elif num_cols == 3:
                    col_widths = [0.24 * avail_width, 0.38 * avail_width, 0.38 * avail_width]
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
                        t_style.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor("#faf5ff")))
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
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#faf5ff")),
                ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#d8b4fe")),
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
            box_text = f"<font name='Helvetica' color='#7b42bc'><b>[  ]</b></font>  {item_text}"
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
            bullet_text = f"<font color='#7b42bc'>&#8226;</font>  {item_text}"
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
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#faf5ff")),
                ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#7b42bc")),
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

        # Regular Body Paragraph
        p_text = clean_inline_markdown(stripped)
        flowables.append(Paragraph(p_text, styles["Body"]))
        flowables.append(Spacer(1, 3))
        i += 1

    return flowables


def build_terraform_pdf():
    workspace = "/Users/mohammedaafaqahmed/Desktop/ToolKit"
    out_dir = os.path.join(workspace, "docs/terraform")
    os.makedirs(out_dir, exist_ok=True)
    out_pdf = os.path.join(out_dir, "BEH_TERRAFORM_COMPLETE_HANDBOOK.pdf")

    chunks = [
        (
            "Part I: Infrastructure as Code, Core Concepts & Mental Models",
            "content/terraform/01-terraform-infrastructure-as-code-core-mental-models.md",
            "Chunk 1 of 3"
        ),
        (
            "Part II: State Management, Modules, Environments & Safe Infrastructure Workflows",
            "content/terraform/02-terraform-state-modules-environments-safe-workflows.md",
            "Chunk 2 of 3"
        ),
        (
            "Part III: Production Infrastructure, Security, CI/CD, Reliability & Incident Mastery",
            "content/terraform/03-terraform-production-security-cicd-reliability-incident-mastery.md",
            "Chunk 3 of 3"
        )
    ]

    styles = getSampleStyleSheet()

    # Base typography styles with Terraform Purple palette
    styles.add(ParagraphStyle(
        'CoverSuper',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11.5,
        textColor=colors.HexColor("#7b42bc"),
        spaceAfter=5
    ))

    styles.add(ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        'CoverSubTitle',
        fontName='Helvetica',
        fontSize=10.5,
        leading=13.5,
        textColor=colors.HexColor("#475569"),
        spaceAfter=7
    ))

    styles.add(ParagraphStyle(
        'CoverMetaHeader',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a")
    ))

    styles.add(ParagraphStyle(
        'CoverMetaVal',
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155")
    ))

    styles.add(ParagraphStyle(
        'CoverDesc',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155")
    ))

    styles.add(ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
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
        textColor=colors.HexColor("#7b42bc"),
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
        textColor=colors.HexColor("#581c87")
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
        textColor=colors.HexColor("#d8b4fe"),
        alignment=1
    ))

    story = []

    # ================= COVER PAGE =================
    story.append(Spacer(1, 6))
    story.append(Paragraph("TOOLKIT · BACKEND ENGINEERING HANDBOOK", styles["CoverSuper"]))
    story.append(Paragraph("TERRAFORM COMPLETE HANDBOOK", styles["CoverTitle"]))
    story.append(Paragraph("Infrastructure as Code, HCL, State Management, Modules, Remote Backends, Security, CI/CD & Production Reliability", styles["CoverSubTitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#7b42bc"), spaceBefore=0, spaceAfter=8))

    meta_data = [
        [Paragraph("Phase", styles["CoverMetaHeader"]), Paragraph("IV — Container Orchestration & Cloud Infrastructure", styles["CoverMetaVal"])],
        [Paragraph("Tool ID", styles["CoverMetaHeader"]), Paragraph("13 of 13", styles["CoverMetaVal"])],
        [Paragraph("Curriculum Scope", styles["CoverMetaHeader"]), Paragraph("Complete 3-Chunk Comprehensive Curriculum", styles["CoverMetaVal"])],
        [Paragraph("Deliverable Type", styles["CoverMetaHeader"]), Paragraph("Consolidated Tool Engineering Handbook (Release Build)", styles["CoverMetaVal"])],
        [Paragraph("Source Authority", styles["CoverMetaHeader"]), Paragraph("content/terraform/ (01, 02, and 03 markdown sources)", styles["CoverMetaVal"])],
        [Paragraph("Target Audience", styles["CoverMetaHeader"]), Paragraph("Backend Software Engineers, SDE-1 / SDE-2, DevOps Engineers, Cloud Platform Teams", styles["CoverMetaVal"])],
        [Paragraph("Engineering Focus", styles["CoverMetaHeader"]), Paragraph("IaC Declarative Lifecycle, State Ledger & Locking, Module Reusability, Environment Boundaries, Blast Radius, CI/CD Gateways, Drift & Incident Runbooks", styles["CoverMetaVal"])],
    ]
    meta_table = Table(meta_data, colWidths=[120, letter[0] - 108 - 120])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    desc_text = (
        "This authoritative engineering handbook provides an exhaustive, production-grade guide to <b>Terraform</b> for backend developers and cloud infrastructure engineers. "
        "Spanning three comprehensive pedagogical layers—Mental Models, Practical Workflows, and Production Incident Mastery—it moves engineers from basic resource "
        "declarations to managing mission-critical cloud topologies safely. Readers master declarative HCL syntax, provider and resource graphs, state architecture "
        "and ledger mechanics, local versus remote backends with distributed state locking, modular infrastructure composition, environment partitioning strategies, "
        "workspaces vs. distinct configurations, resource address migrations with moved blocks, provider version pinning via .terraform.lock.hcl, blast radius minimization, "
        "Policy as Code guardrails, automated CI/CD validation and plan review pipelines, drift remediation, sensitive state governance, and real-world incident runbooks."
    )
    story.append(Paragraph(desc_text, styles["CoverDesc"]))
    story.append(Spacer(1, 6))

    overview_box = [
        [Paragraph("<b>Curriculum Structure & Core Topics</b>", styles["TableHeader"])],
        [Paragraph("<b>Part I — Infrastructure as Code, Core Concepts & Mental Models:</b> The IaC imperative, configuration-plan-apply-reconcile cycle, declarative vs imperative paradigms, providers and resource schemas, HCL fundamentals (blocks, arguments, expressions, variables, outputs, data sources), state ledger role, dependency graphs, drift detection, and local execution with terraform_data.", styles["TableCell"])],
        [Paragraph("<b>Part II — State Management, Modules, Environments & Safe Infrastructure Workflows:</b> State management internals, local vs remote backends, distributed state locking and concurrency, reusable child module architecture, input/output composition, environment separation (directories vs workspaces), state migrations, moved blocks for refactoring, provider lock files, and safe state recovery.", styles["TableCell"])],
        [Paragraph("<b>Part III — Production Infrastructure, Security, CI/CD, Reliability & Incident Mastery:</b> Production change control, blast radius containment, provider version pinning and upgrade paths, network isolation, short-lived workload identity, Policy as Code, cost optimization, multi-stage CI/CD pipelines, partial apply triage, prevent_destroy guardrails, drift investigation, and production incident runbooks.", styles["TableCell"])]
    ]
    ot = Table(overview_box, colWidths=[letter[0] - 108])
    ot.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#7b42bc")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#faf5ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#d8b4fe")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e9d5ff")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
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
    print(f"Terraform Complete Handbook successfully compiled: {out_pdf}")


if __name__ == "__main__":
    build_terraform_pdf()
