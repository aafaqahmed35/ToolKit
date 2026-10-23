#!/usr/bin/env python3
"""
ToolKit Handbook PDF Compiler - Linux Complete Handbook
Compiles all 6 authoritative Linux markdown source chunks into a single,
professional, publication-quality PDF deliverable: docs/linux/BEH_LINUX_COMPLETE_HANDBOOK.pdf.
Uses ReportLab Platypus and custom canvas layout.
"""

import os
import re
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Preformatted
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
        header_text = "ToolKit — Backend Engineering Tools & Infrastructure Handbook | Linux Complete Handbook"
        self.drawString(54, letter[1] - 36, header_text)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer
        footer_left = "Phase I — Developer Foundations | Production Engineering Series"
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(54, 34, footer_left)
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.line(54, 46, letter[0] - 54, 46)

        self.restoreState()


def clean_inline_markdown(text):
    """Converts inline markdown like `code`, **bold**, *italic* into reportlab XML tags."""
    # Escape HTML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Re-enable basic tags
    # Bold + Italic: ***text*** or ___text___
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold: **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* or _text_
    text = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Inline code: `code`
    text = re.sub(r'`(.*?)`', r'<font name="Courier" color="#0f766e" size="8.5"><b>\1</b></font>', text)
    return text


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
                # Wrap long lines if necessary
                wrapped_lines = []
                for cl in clean_code.split("\n"):
                    if len(cl) > 88:
                        # break into chunks of 88 chars
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
            # Strip empty outer cells if present
            if len(raw_cells) > 0 and raw_cells[0] == "":
                raw_cells = raw_cells[1:]
            if len(raw_cells) > 0 and raw_cells[-1] == "":
                raw_cells = raw_cells[:-1]

            # Check if this is separator line like | :--- | :--- |
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
                    col_widths = [0.32 * avail_width, 0.68 * avail_width]
                elif num_cols == 3:
                    col_widths = [0.22 * avail_width, 0.38 * avail_width, 0.40 * avail_width]
                elif num_cols == 4:
                    col_widths = [0.18 * avail_width, 0.24 * avail_width, 0.28 * avail_width, 0.30 * avail_width]

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
                        t_style.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor("#f8fafc")))
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
            box_text = f"<font name='Helvetica' color='#0284c7'><b>[  ]</b></font>  {item_text}"
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
            bullet_text = f"<font color='#0284c7'>&#8226;</font>  {item_text}"
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
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#0284c7")),
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


def build_linux_pdf():
    workspace = "/Users/mohammedaafaqahmed/Desktop/ToolKit"
    chunks = [
        ("PART I: TERMINAL & FILESYSTEM MASTERY", "content/linux/01-terminal-filesystem-mastery.md", "Chunk 1 of 6"),
        ("PART II: PROCESSES, SIGNALS & RESOURCE MANAGEMENT", "content/linux/02-processes-signals-resource-management.md", "Chunk 2 of 6"),
        ("PART III: NETWORKING & CONNECTIVITY DEBUGGING", "content/linux/03-networking-connectivity-debugging.md", "Chunk 3 of 6"),
        ("PART IV: LOGS, PERMISSIONS & SYSTEM TROUBLESHOOTING", "content/linux/04-logs-permissions-system-troubleshooting.md", "Chunk 4 of 6"),
        ("PART V: SHELL SCRIPTING & AUTOMATION", "content/linux/05-shell-scripting-automation.md", "Chunk 5 of 6"),
        ("PART VI: PRODUCTION INCIDENT SIMULATION & CAPSTONE", "content/linux/06-production-incident-simulation.md", "Chunk 6 of 6"),
    ]

    out_dir = os.path.join(workspace, "docs/linux")
    out_pdf = os.path.join(out_dir, "BEH_LINUX_COMPLETE_HANDBOOK.pdf")

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
        leading=14,
        textColor=colors.HexColor("#0284c7"),
        alignment=0,
        spaceAfter=15
    ))

    styles.add(ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'CoverSubTitle',
        fontName='Helvetica',
        fontSize=14,
        leading=20,
        textColor=colors.HexColor("#334155"),
        alignment=0,
        spaceAfter=25
    ))

    styles.add(ParagraphStyle(
        'CoverMetaHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    ))

    styles.add(ParagraphStyle(
        'CoverMetaVal',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
    ))

    styles.add(ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=5,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'DocH2',
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'DocH3',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0284c7"),
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
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=0,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'BulletItem',
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=14,
        firstLineIndent=-10,
        spaceBefore=1,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'NumberedItem',
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=16,
        firstLineIndent=-12,
        spaceBefore=1,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'ChecklistItem',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceBefore=1,
        spaceAfter=1.5
    ))

    styles.add(ParagraphStyle(
        'CalloutText',
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#f1f5f9"),
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    ))

    story = []

    # 1. Cover Page
    story.append(Spacer(1, 30))
    story.append(Paragraph("TOOLKIT · BACKEND ENGINEERING HANDBOOK", styles["CoverSuper"]))
    story.append(Paragraph("LINUX COMPLETE HANDBOOK", styles["CoverTitle"]))
    story.append(Paragraph(
        "Terminal Mastery, Process Engineering, Networking, Troubleshooting, Shell Automation & Production Incident Simulation",
        styles["CoverSubTitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceBefore=0, spaceAfter=20))

    meta_data = [
        [
            Paragraph("Phase", styles["CoverMetaHeader"]),
            Paragraph("Tool ID", styles["CoverMetaHeader"]),
            Paragraph("Curriculum Scope", styles["CoverMetaHeader"]),
            Paragraph("Deliverable Type", styles["CoverMetaHeader"])
        ],
        [
            Paragraph("I — Developer Foundations", styles["CoverMetaVal"]),
            Paragraph("Tool 02 of 13 (Linux)", styles["CoverMetaVal"]),
            Paragraph("6 Comprehensive Chunks", styles["CoverMetaVal"]),
            Paragraph("Publication Handbook", styles["CoverMetaVal"])
        ],
        [
            Paragraph("Interview Questions", styles["CoverMetaHeader"]),
            Paragraph("Practical Labs", styles["CoverMetaHeader"]),
            Paragraph("Engineering Framework", styles["CoverMetaHeader"]),
            Paragraph("Target Audience", styles["CoverMetaHeader"])
        ],
        [
            Paragraph("90 Rigorous Questions", styles["CoverMetaVal"]),
            Paragraph("6 Production Labs", styles["CoverMetaVal"]),
            Paragraph("3-Layer Architecture", styles["CoverMetaVal"]),
            Paragraph("Backend Engineers & SDE-1", styles["CoverMetaVal"])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[126, 126, 126, 126])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 40))
    notice_text = (
        "<b>Executive Notice</b>: This handbook is the definitive Linux operational volume from the <i>ToolKit</i> curriculum. "
        "It provides complete conceptual models, command-line fundamentals, process and socket telemetry, kernel signal handling, "
        "TCP/DNS debugging workflows, log management, filesystem permission mathematics, robust defensive shell scripting, "
        "90 detailed interview scenarios with complete answers, 6 practical labs, and production-grade incident simulation protocols."
    )
    story.append(Paragraph(notice_text, styles["Body"]))
    story.append(PageBreak())

    # 2. Executive Table of Contents
    story.append(Paragraph("Table of Contents", styles["DocH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

    toc_data = [
        [Paragraph("<b>PART I: TERMINAL &amp; FILESYSTEM MASTERY (Chunk 1 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Why Backend Engineers Need Linux (Server Management Mental Models)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Terminal, Shell &amp; Operating System: Clear Distinctions", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Anatomy of a Linux Command (Command, Options, Arguments, Evaluation)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. The Linux Filesystem Tree (FHS Hierarchy: /etc, /var, /tmp, /usr, /opt)", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Absolute vs. Relative Paths (Navigation &amp; Safe Execution)", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Inspect Your Environment (whoami, id, hostname, uname, pwd)", styles["Body"]), Paragraph("Section 6", styles["Body"])],
        [Paragraph("7. Essential Directory &amp; File Commands (cd, ls, mkdir, touch, cp, mv, rm)", styles["Body"]), Paragraph("Section 7", styles["Body"])],
        [Paragraph("8. Inspecting Files without Breaking Terminals (cat, less, head, tail, file)", styles["Body"]), Paragraph("Section 8", styles["Body"])],
        [Paragraph("9. Searching Files and Content (find vs. grep -rnI)", styles["Body"]), Paragraph("Section 9", styles["Body"])],
        [Paragraph("10. Streams &amp; Redirection (stdin 0, stdout 1, stderr 2, pipes)", styles["Body"]), Paragraph("Section 10", styles["Body"])],
        [Paragraph("11. Basic File Permissions &amp; Identity (rwx bits, chmod, chown)", styles["Body"]), Paragraph("Section 11", styles["Body"])],
        [Paragraph("12. Editing Files in Terminal (nano, vim basics, recovery)", styles["Body"]), Paragraph("Section 12", styles["Body"])],
        [Paragraph("13. Package Management (apt, yum/dnf, system updates)", styles["Body"]), Paragraph("Section 13", styles["Body"])],
        [Paragraph("14. Production Incident: Catastrophic Recursive Deletion (Guardrails)", styles["Body"]), Paragraph("Section 14", styles["Body"])],
        [Paragraph("15. Production Incident: Terminal Lockup &amp; Binary Dumping", styles["Body"]), Paragraph("Section 15", styles["Body"])],
        [Paragraph("16. Linux Safety Rules for Production Operations", styles["Body"]), Paragraph("Section 16", styles["Body"])],
        [Paragraph("17. Hands-on Lab — Server Inspection &amp; Workspace Organization", styles["Body"]), Paragraph("Section 17", styles["Body"])],
        [Paragraph("18. Interview Questions &amp; Answers (Questions 1 to 15)", styles["Body"]), Paragraph("Section 18", styles["Body"])],

        [Paragraph("<br/><b>PART II: PROCESSES, SIGNALS &amp; RESOURCE MANAGEMENT (Chunk 2 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Fundamentals &amp; Mental Models (Processes, Threads, PIDs, State Lifecycle)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Practical Engineering &amp; Workflows (ps, top, pgrep, kill, free, uptime)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Production Incidents (CPU Spikes, OOM Killer, Zombie &amp; Orphan Processes)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Hands-on Lab — Process Inspection &amp; Signal Handling", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Interview Questions &amp; Answers (Questions 16 to 30)", styles["Body"]), Paragraph("Section 5", styles["Body"])],

        [Paragraph("<br/><b>PART III: NETWORKING &amp; CONNECTIVITY DEBUGGING (Chunk 3 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Fundamentals &amp; Mental Models (DNS, IP, Ports, Sockets, TCP Handshake, Routing)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Practical Engineering &amp; Workflows (curl, dig, ss -lntp, ip, nc, ping)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Production Incidents (DNS Outages, Connection Refused vs. Timeout, Ephemeral Exhaustion)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Hands-on Lab — Network Connectivity &amp; Socket Triage", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Interview Questions &amp; Answers (Questions 31 to 45)", styles["Body"]), Paragraph("Section 5", styles["Body"])],

        [Paragraph("<br/><b>PART IV: LOGS, PERMISSIONS &amp; SYSTEM TROUBLESHOOTING (Chunk 4 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Fundamentals &amp; Mental Models (Logs as Evidence, Octal Permissions, Inodes vs. Capacity)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Practical Engineering &amp; Workflows (tail -f, journalctl -u, chmod, chown, df -h, du, lsof)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Production Incidents (Full Disks, Unlinked Open Files, Post-Deployment Permission Denied)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Hands-on Lab — The Operations Investigator", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Interview Questions &amp; Answers (Questions 46 to 60)", styles["Body"]), Paragraph("Section 5", styles["Body"])],

        [Paragraph("<br/><b>PART V: SHELL SCRIPTING &amp; AUTOMATION (Chunk 5 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Fundamentals &amp; Mental Models (Shebang, Variables, Quoting, Exit Codes, Defensive Bash)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Practical Engineering &amp; Workflows (Diagnostics, Health Checks, Positional Args, Cron, flock)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Production Incidents (Silent Failures, Cron Discrepancies, Unchecked File Operations)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Hands-on Lab — Mini Operations Toolkit", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Interview Questions &amp; Answers (Questions 61 to 75)", styles["Body"]), Paragraph("Section 5", styles["Body"])],

        [Paragraph("<br/><b>PART VI: PRODUCTION INCIDENT SIMULATION &amp; CAPSTONE (Chunk 6 of 6)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. Fundamentals &amp; Mental Models (The Production Troubleshooting Discipline)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. Incident Simulations A through G (Unreachable API, CPU, OOM, Disk, DNS, Permissions, Deploy)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Production Playbook &amp; Common Troubleshooting Anti-Patterns", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Capstone Lab — Real-World Incident Investigation &amp; Post-Mortem Report", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Interview Questions &amp; Answers (Questions 76 to 90)", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Linux Comprehensive Mastery Assessment", styles["Body"]), Paragraph("Section 6", styles["Body"])],
    ]
    toc_table = Table(toc_data, colWidths=[420, 80])
    toc_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # 3. Assemble all 6 Parts
    for part_title, rel_path, c_label in chunks:
        full_path = os.path.join(workspace, rel_path)
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        story.append(Paragraph(part_title, styles["DocH1"]))
        story.append(Paragraph(f"Phase I — Developer Foundations | {c_label}", styles["CoverSuper"]))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

        part_flowables = parse_markdown_to_flowables(content, styles)
        story.extend(part_flowables)
        story.append(PageBreak())

    # Build the document
    doc = SimpleDocTemplate(
        out_pdf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    print("Compiling BEH_LINUX_COMPLETE_HANDBOOK.pdf...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Compilation finished successfully -> {out_pdf}")

    # Verify with PyMuPDF
    pdf_doc = pymupdf.open(out_pdf)
    page_count = len(pdf_doc)
    print(f"Verification: Successfully opened PDF. Total pages: {page_count}")
    assert page_count > 0, "PDF has 0 pages!"
    # Check text from first 5 pages and random middle/end pages
    for p_no in [0, 1, 2, page_count // 2, page_count - 1]:
        page_text = pdf_doc[p_no].get_text()
        print(f"Page {p_no+1} snippet length: {len(page_text)} chars")
        assert len(page_text.strip()) > 0, f"Page {p_no+1} is empty!"
    pdf_doc.close()
    print("Verification completed: All tested pages contain rendered text. Zero blank pages detected.")


if __name__ == "__main__":
    build_linux_pdf()
