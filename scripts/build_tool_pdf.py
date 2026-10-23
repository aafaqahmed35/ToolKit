#!/usr/bin/env python3
"""
ToolKit Handbook PDF Compiler
Compiles authoritative markdown source chunks into professional, publication-quality PDFs.
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
        header_text = "ToolKit — Backend Engineering Tools & Infrastructure Handbook | Git Complete Handbook"
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
                # Render code block
                # Wrap in Preformatted or Table
                clean_code = code_text.replace("\t", "    ")
                code_p = Preformatted(
                    clean_code,
                    styles["CodeBlock"]
                )
                code_table = Table([[code_p]], colWidths=[letter[0] - 108])
                code_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(code_table)
                flowables.append(Spacer(1, 8))
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
                # Render table
                num_cols = max(len(r) for r in table_rows)
                # Normalize row cell count
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
                # Specific sizing for 2-col tables
                col_widths = [col_w] * num_cols
                if num_cols == 2:
                    col_widths = [0.35 * avail_width, 0.65 * avail_width]
                elif num_cols == 3:
                    col_widths = [0.25 * avail_width, 0.35 * avail_width, 0.40 * avail_width]
                elif num_cols == 4:
                    col_widths = [0.20 * avail_width, 0.25 * avail_width, 0.25 * avail_width, 0.30 * avail_width]

                t = Table(norm_rows, colWidths=col_widths, repeatRows=1)
                t_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
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
                flowables.append(Spacer(1, 6))
                flowables.append(t)
                flowables.append(Spacer(1, 8))
            # Continue processing current line

        stripped = line.strip()

        # Empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped in ["---", "***", "___", "⸻"]:
            flowables.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#cbd5e1"), spaceBefore=10, spaceAfter=10))
            i += 1
            continue

        # Headings
        if stripped.startswith("# "):
            title_text = clean_inline_markdown(stripped[2:].strip())
            flowables.append(Spacer(1, 14))
            flowables.append(Paragraph(title_text, styles["DocH1"]))
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        if stripped.startswith("## "):
            title_text = clean_inline_markdown(stripped[3:].strip())
            flowables.append(Spacer(1, 12))
            flowables.append(Paragraph(title_text, styles["DocH2"]))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        if stripped.startswith("### "):
            title_text = clean_inline_markdown(stripped[4:].strip())
            flowables.append(Spacer(1, 8))
            flowables.append(Paragraph(title_text, styles["DocH3"]))
            flowables.append(Spacer(1, 3))
            i += 1
            continue

        if stripped.startswith("#### "):
            title_text = clean_inline_markdown(stripped[5:].strip())
            flowables.append(Spacer(1, 6))
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
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(c_table)
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Standard Paragraph
        para_text = clean_inline_markdown(stripped)
        flowables.append(Paragraph(para_text, styles["Body"]))
        flowables.append(Spacer(1, 4))
        i += 1

    return flowables


def build_git_pdf():
    workspace = "/Users/mohammedaafaqahmed/Desktop/ToolKit"
    chunk1_path = os.path.join(workspace, "content/git/01-git-fundamentals.md")
    chunk2_path = os.path.join(workspace, "content/git/02-git-collaboration-recovery-advanced-workflows.md")
    out_dir = os.path.join(workspace, "docs/git")
    out_pdf = os.path.join(out_dir, "BEH_GIT_COMPLETE_HANDBOOK.pdf")

    if not os.path.exists(chunk1_path) or not os.path.exists(chunk2_path):
        print(f"Error: Required source files missing!")
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    with open(chunk1_path, "r", encoding="utf-8") as f:
        c1_content = f.read()

    with open(chunk2_path, "r", encoding="utf-8") as f:
        c2_content = f.read()

    # Document Styles
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'CoverSuper',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0284c7"),
        alignment=0, # Left
        spaceAfter=15
    ))

    styles.add(ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'CoverSubTitle',
        fontName='Helvetica',
        fontSize=16,
        leading=22,
        textColor=colors.HexColor("#334155"),
        alignment=0,
        spaceAfter=25
    ))

    styles.add(ParagraphStyle(
        'CoverMetaHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    ))

    styles.add(ParagraphStyle(
        'CoverMetaVal',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
    ))

    styles.add(ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
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
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=18,
        firstLineIndent=-14,
        spaceBefore=1.5,
        spaceAfter=1.5
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#f8fafc"),
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
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

    styles.add(ParagraphStyle(
        'CalloutText',
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0f172a"),
    ))

    story = []

    # 1. Professional Cover Page
    story.append(Spacer(1, 40))
    story.append(Paragraph("TOOLKIT : BACKEND ENGINEERING TOOLS &amp; INFRASTRUCTURE HANDBOOK", styles["CoverSuper"]))
    story.append(Paragraph("Git Complete Handbook", styles["CoverTitle"]))
    story.append(Paragraph("Developer Foundations, Collaboration, Recovery &amp; Production Engineering Protocols", styles["CoverSubTitle"]))

    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceBefore=0, spaceAfter=30))

    meta_data = [
        [
            Paragraph("CURRICULUM PHASE", styles["CoverMetaHeader"]),
            Paragraph("SCOPE &amp; COVERAGE", styles["CoverMetaHeader"]),
        ],
        [
            Paragraph("Phase I — Developer Foundations (Tool 01 / 13)", styles["CoverMetaVal"]),
            Paragraph("Chunks 1 &amp; 2 Complete (Full 32-Chunk Curriculum)", styles["CoverMetaVal"]),
        ],
        [
            Paragraph("<br/>TARGET AUDIENCE", styles["CoverMetaHeader"]),
            Paragraph("<br/>DELIVERABLE SPECIFICATION", styles["CoverMetaHeader"]),
        ],
        [
            Paragraph("Aspiring Backend Engineers &amp; SDE-1 Candidates", styles["CoverMetaVal"]),
            Paragraph("BEH_GIT_COMPLETE_HANDBOOK.pdf", styles["CoverMetaVal"]),
        ],
        [
            Paragraph("<br/>METHODOLOGY", styles["CoverMetaHeader"]),
            Paragraph("<br/>QUALITY STANDARD", styles["CoverMetaHeader"]),
        ],
        [
            Paragraph("3-Layer Model: Fundamentals, Workflows, Production", styles["CoverMetaVal"]),
            Paragraph("Authoritative, Zero-Omission Reference", styles["CoverMetaVal"]),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[240, 260])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 60))
    notice_text = (
        "<b>Notice</b>: This handbook is an authoritative educational deliverable from the <i>ToolKit</i> curriculum. "
        "It integrates complete conceptual foundations, step-by-step terminal workflows, practical command usage, "
        "production incident diagnostics, 30 rigorous interview questions with model answers, hands-on laboratory exercises, "
        "and exhaustive operational readiness checklists."
    )
    story.append(Paragraph(notice_text, styles["Body"]))
    story.append(PageBreak())

    # 2. Executive Table of Contents
    story.append(Paragraph("Table of Contents", styles["DocH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

    toc_data = [
        [
            Paragraph("<b>PART I: GIT FUNDAMENTALS &amp; ESSENTIAL WORKFLOWS (Chunk 1 of 2)</b>", styles["DocH3"]),
            Paragraph("", styles["DocH3"])
        ],
        [Paragraph("1. What Is Git? (Mental Models, Git vs. GitHub)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. The Three Main Areas of Git (Working Tree, Staging Area, Local Repository)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Git’s Core Vocabulary (Repository, Commit, Branch, HEAD, Remote, Merge)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Configure Git (Global vs. Local Identity Configuration)", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Create or Obtain a Repository (git init vs. git clone)", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Your First Complete Git Workflow (Inspect, Edit, Review, Stage, Commit)", styles["Body"]), Paragraph("Section 6", styles["Body"])],
        [Paragraph("7. Essential Git Commands (Quick Reference Table)", styles["Body"]), Paragraph("Section 7", styles["Body"])],
        [Paragraph("8. Branching for Backend Development (Feature Isolation)", styles["Body"]), Paragraph("Section 8", styles["Body"])],
        [Paragraph("9. Understand fetch, pull, and push (Remote Synchronization Protocols)", styles["Body"]), Paragraph("Section 9", styles["Body"])],
        [Paragraph("10. Merge Conflicts (Detection, Conflict Markers &amp; Step-by-Step Resolution)", styles["Body"]), Paragraph("Section 10", styles["Body"])],
        [Paragraph("11. restore, revert, and reset (Safe Undos &amp; Destructive Modes)", styles["Body"]), Paragraph("Section 11", styles["Body"])],
        [Paragraph("12. Temporarily Store Work with git stash (Context Switching)", styles["Body"]), Paragraph("Section 12", styles["Body"])],
        [Paragraph("13. .gitignore and Secret Protection (Credential Leakage Prevention)", styles["Body"]), Paragraph("Section 13", styles["Body"])],
        [Paragraph("14. Pull Requests and Code Review (Collaboration Guidelines)", styles["Body"]), Paragraph("Section 14", styles["Body"])],
        [Paragraph("15. Common Git Mistakes (Root Causes &amp; Preventions)", styles["Body"]), Paragraph("Section 15", styles["Body"])],
        [Paragraph("16. Practical Lab — Create a Clean Git Repository (Hands-On Lab Tasks A-H)", styles["Body"]), Paragraph("Section 16", styles["Body"])],
        [Paragraph("17. Git Interview Questions and Answers (Q1 to Q15 with Detailed Rationale)", styles["Body"]), Paragraph("Section 17", styles["Body"])],
        [Paragraph("18. Mastery Checklist (Phase I Core Readiness Verification)", styles["Body"]), Paragraph("Section 18", styles["Body"])],
        [
            Paragraph("<br/><b>PART II: COLLABORATION, RECOVERY &amp; PRODUCTION ENGINEERING (Chunk 2 of 2)</b>", styles["DocH3"]),
            Paragraph("", styles["DocH3"])
        ],
        [Paragraph("1. The Mission: From Using Git to Engineering with Git (The 3-Layer Architecture)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("LAYER 1 — FUNDAMENTALS &amp; MENTAL MODELS", styles["DocH4"]), Paragraph("", styles["DocH4"])],
        [Paragraph("2. Git Collaboration: Understand the Repository You’re Working In (Remotes, Upstreams)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Understand History Before Manipulating It (Topology, Ancestry, Hashes)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Merge, Rebase, and Cherry-Pick: Three Different Decisions (Trade-offs &amp; Decision Table)", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("LAYER 2 — PRACTICAL ENGINEERING &amp; WORKFLOWS", styles["DocH4"]), Paragraph("", styles["DocH4"])],
        [Paragraph("5. The Professional Feature-Branch Workflow (8-Step Production Protocol)", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Scenario: Your Push Is Rejected (Non-Fast-Forward Diagnosis &amp; Remediation)", styles["Body"]), Paragraph("Section 6", styles["Body"])],
        [Paragraph("7. Scenario: You Committed to the Wrong Branch (Unpublished vs. Shared History)", styles["Body"]), Paragraph("Section 7", styles["Body"])],
        [Paragraph("8. Scenario: A Commit Introduced a Regression (Revision Inspection Techniques)", styles["Body"]), Paragraph("Section 8", styles["Body"])],
        [Paragraph("9. Find the Problematic Commit with git bisect (Binary Search for Bugs)", styles["Body"]), Paragraph("Section 9", styles["Body"])],
        [Paragraph("10. Recovery: You Cannot Find a Commit (reflog Investigation &amp; Recovery Branches)", styles["Body"]), Paragraph("Section 10", styles["Body"])],
        [Paragraph("11. Recovery: Choosing Between Reset and Revert (Decision Matrix)", styles["Body"]), Paragraph("Section 11", styles["Body"])],
        [Paragraph("LAYER 3 — PRODUCTION ENGINEERING &amp; INTERVIEW MASTERY", styles["DocH4"]), Paragraph("", styles["DocH4"])],
        [Paragraph("12. Production Incident: A Bad Configuration Reaches Production (Incident Simulation)", styles["Body"]), Paragraph("Section 12", styles["Body"])],
        [Paragraph("13. Git Safety Rules for Production Teams (Six Golden Operational Rules)", styles["Body"]), Paragraph("Section 13", styles["Body"])],
        [Paragraph("14. Practical Engineering Lab (Advanced Hands-On Labs A through E)", styles["Body"]), Paragraph("Section 14", styles["Body"])],
        [Paragraph("15. Advanced Interview Questions (15 Architectural &amp; Production Scenarios Q1-Q15)", styles["Body"]), Paragraph("Section 15", styles["Body"])],
        [Paragraph("16. Git Mastery Assessment (Full 3-Layer Competency Matrix)", styles["Body"]), Paragraph("Section 16", styles["Body"])],
        [Paragraph("17. Git Handbook Completion Protocol &amp; Next Curriculum Milestones", styles["Body"]), Paragraph("Section 17", styles["Body"])],
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

    # 3. Assemble Part I Flowables
    story.append(Paragraph("PART I: GIT FUNDAMENTALS &amp; ESSENTIAL WORKFLOWS", styles["DocH1"]))
    story.append(Paragraph("Phase I — Developer Foundations | Chunk 1 of 2", styles["CoverSuper"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

    c1_flowables = parse_markdown_to_flowables(c1_content, styles)
    # Skip the original document title if it repeats
    story.extend(c1_flowables)

    # 4. Assemble Part II Flowables
    story.append(PageBreak())
    story.append(Paragraph("PART II: COLLABORATION, RECOVERY &amp; PRODUCTION ENGINEERING", styles["DocH1"]))
    story.append(Paragraph("Phase I — Developer Foundations | Chunk 2 of 2", styles["CoverSuper"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

    c2_flowables = parse_markdown_to_flowables(c2_content, styles)
    story.extend(c2_flowables)

    # Build the document using NumberedCanvas
    doc = SimpleDocTemplate(
        out_pdf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    print("Compiling BEH_GIT_COMPLETE_HANDBOOK.pdf...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Compilation finished successfully -> {out_pdf}")

    # Verify with PyMuPDF
    pdf_doc = pymupdf.open(out_pdf)
    page_count = len(pdf_doc)
    print(f"Verification: Successfully opened PDF. Total pages: {page_count}")
    assert page_count > 0, "PDF has 0 pages!"
    # Check text from first 3 pages
    for p_no in range(min(3, page_count)):
        page_text = pdf_doc[p_no].get_text()
        print(f"Page {p_no+1} snippet length: {len(page_text)} chars")
    pdf_doc.close()

if __name__ == "__main__":
    build_git_pdf()
