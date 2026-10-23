#!/usr/bin/env python3
"""
ToolKit Handbook PDF Compiler - JUnit 5 Complete Handbook
Compiles both authoritative JUnit 5 markdown source chunks into a single,
professional, publication-quality PDF deliverable: docs/junit5/BEH_JUNIT5_COMPLETE_HANDBOOK.pdf.
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
        header_text = "ToolKit — Backend Engineering Tools & Infrastructure Handbook | JUnit 5 Complete Handbook"
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

    # 3. Restore inline code
    for idx, code_content in enumerate(code_tokens):
        formatted_code = f'<font name="Courier" color="#0f766e" size="8.5"><b>{code_content}</b></font>'
        text = text.replace(f"__CODE_TOKEN_{idx}__", formatted_code)

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
                    col_widths = [0.32 * avail_width, 0.68 * avail_width]
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


def build_junit5_pdf():
    workspace = "/Users/mohammedaafaqahmed/Desktop/ToolKit"
    chunks = [
        ("PART I: FUNDAMENTALS & UNIT TESTING", "content/junit5/01-junit5-fundamentals-unit-testing.md", "Chunk 1 of 2"),
        ("PART II: ADVANCED TESTING & PRODUCTION MASTERY", "content/junit5/02-junit5-advanced-testing-production.md", "Chunk 2 of 2"),
    ]

    out_dir = os.path.join(workspace, "docs/junit5")
    out_pdf = os.path.join(out_dir, "BEH_JUNIT5_COMPLETE_HANDBOOK.pdf")

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
    story.append(Paragraph("JUNIT 5 COMPLETE HANDBOOK", styles["CoverTitle"]))
    story.append(Paragraph(
        "Unit Testing, Spring Boot Slices, Mockito, Integration Testing & Production Mastery",
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
            Paragraph("Tool 05 of 13 (JUnit 5)", styles["CoverMetaVal"]),
            Paragraph("2 Comprehensive Chunks", styles["CoverMetaVal"]),
            Paragraph("Publication Handbook", styles["CoverMetaVal"])
        ],
        [
            Paragraph("Interview Questions", styles["CoverMetaHeader"]),
            Paragraph("Practical Labs", styles["CoverMetaHeader"]),
            Paragraph("Engineering Framework", styles["CoverMetaHeader"]),
            Paragraph("Target Audience", styles["CoverMetaHeader"])
        ],
        [
            Paragraph("30 Rigorous Questions", styles["CoverMetaVal"]),
            Paragraph("Production Testing Labs", styles["CoverMetaVal"]),
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
        "<b>Executive Notice</b>: This handbook is the definitive automated Java testing volume from the <i>ToolKit</i> curriculum. "
        "It provides comprehensive coverage of JUnit 5 (Platform, Jupiter, Vintage), the Arrange-Act-Assert pattern, assertions, "
        "parameterized tests, test lifecycle callbacks, Mockito test doubles, Spring Boot test slices (@WebMvcTest, @DataJpaTest, @SpringBootTest), "
        "Testcontainers integration with real databases, flaky test remediation, 30 rigorous interview questions with detailed answers, "
        "and production engineering checklists."
    )
    story.append(Paragraph(notice_text, styles["Body"]))
    story.append(PageBreak())

    # 2. Executive Table of Contents
    story.append(Paragraph("Table of Contents", styles["DocH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceBefore=5, spaceAfter=15))

    toc_data = [
        [Paragraph("<b>PART I: FUNDAMENTALS &amp; UNIT TESTING (Chunk 1 of 2)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. What Is JUnit 5? (JUnit Platform, Jupiter, Vintage Architecture)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. What Is a Unit Test? (Arrange–Act–Assert AAA Pattern)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Why Unit Tests Matter (Regression Prevention &amp; Living Documentation)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Your First JUnit 5 Test (Maven Project Structure &amp; Visibility Rules)", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Assertions: Standard Ordering, Verification &amp; assertAll Grouping", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Test Names Should Describe Behavior (method_condition_expectedResult)", styles["Body"]), Paragraph("Section 6", styles["Body"])],
        [Paragraph("7. Build a Realistic Unit-Tested Class (PriceCalculator with Domain Contracts)", styles["Body"]), Paragraph("Section 7", styles["Body"])],
        [Paragraph("8. Test Exceptions (assertThrows, Exception Types &amp; Message Inspection)", styles["Body"]), Paragraph("Section 8", styles["Body"])],
        [Paragraph("9. Parameterized Tests (@ParameterizedTest, @CsvSource, @ValueSource)", styles["Body"]), Paragraph("Section 9", styles["Body"])],
        [Paragraph("10. Understand the Test Lifecycle (@BeforeAll, @BeforeEach, @AfterEach, @AfterAll)", styles["Body"]), Paragraph("Section 10", styles["Body"])],
        [Paragraph("11. Test Collections and Returned Data (Size, Presence &amp; Order Semantics)", styles["Body"]), Paragraph("Section 11", styles["Body"])],
        [Paragraph("12. Mocking Collaborators with Mockito (@Mock, when, thenReturn, verify)", styles["Body"]), Paragraph("Section 12", styles["Body"])],
        [Paragraph("13. Run Tests with Maven (Surefire Reports &amp; Filtered Test Execution)", styles["Body"]), Paragraph("Section 13", styles["Body"])],
        [Paragraph("14. Exercise: Test the Calculator (Complete Matrix of Cases)", styles["Body"]), Paragraph("Section 14", styles["Body"])],
        [Paragraph("15. F.I.R.S.T. Unit Test Reliability Principles", styles["Body"]), Paragraph("Section 15", styles["Body"])],
        [Paragraph("16. Unit Tests versus Integration Tests (Key Architectural Differences)", styles["Body"]), Paragraph("Section 16", styles["Body"])],
        [Paragraph("17. Test Behavior, Not Implementation Details (Avoiding Brittle Tests)", styles["Body"]), Paragraph("Section 17", styles["Body"])],
        [Paragraph("18. Common Testing Failure Scenarios (Triage &amp; Root Causes)", styles["Body"]), Paragraph("Section 18", styles["Body"])],
        [Paragraph("19. Interview Questions — 15 Core Fundamentals Questions &amp; Answers", styles["Body"]), Paragraph("Section 19", styles["Body"])],
        [Paragraph("20. Hands-on Mastery Checklist", styles["Body"]), Paragraph("Section 20", styles["Body"])],

        [Paragraph("<br/><b>PART II: ADVANCED TESTING &amp; PRODUCTION MASTERY (Chunk 2 of 2)</b>", styles["DocH3"]), Paragraph("", styles["DocH3"])],
        [Paragraph("1. The Testing Pyramid (Unit vs. Integration vs. End-to-End Distribution)", styles["Body"]), Paragraph("Section 1", styles["Body"])],
        [Paragraph("2. What Makes a Good Test? (Deterministic, Isolated, Readable, Behavior-focused)", styles["Body"]), Paragraph("Section 2", styles["Body"])],
        [Paragraph("3. Test Doubles: Dummy, Stub, Mock, Fake, and Spy (Trade-offs &amp; Pitfalls)", styles["Body"]), Paragraph("Section 3", styles["Body"])],
        [Paragraph("4. Spring Boot Testing Annotations (@WebMvcTest, @DataJpaTest, @SpringBootTest)", styles["Body"]), Paragraph("Section 4", styles["Body"])],
        [Paragraph("5. Unit-Test a Spring Service with Mockito (Constructor Injection &amp; Fail-Fast)", styles["Body"]), Paragraph("Section 5", styles["Body"])],
        [Paragraph("6. Test a Spring MVC Controller (@WebMvcTest, MockMvc, MockitoBean)", styles["Body"]), Paragraph("Section 6", styles["Body"])],
        [Paragraph("7. Test a Repository Against a Database (@DataJpaTest, flush, clear, Testcontainers)", styles["Body"]), Paragraph("Section 7", styles["Body"])],
        [Paragraph("8. Test Configuration &amp; External Dependencies (@DynamicPropertySource, Test Profiles)", styles["Body"]), Paragraph("Section 8", styles["Body"])],
        [Paragraph("9. Maven Testing Workflow (Surefire vs. Failsafe &amp; Triage Sequences)", styles["Body"]), Paragraph("Section 9", styles["Body"])],
        [Paragraph("10. Flaky Tests and CI Reliability (Awaitility, Clocks &amp; Mutable State Resets)", styles["Body"]), Paragraph("Section 10", styles["Body"])],
        [Paragraph("11. Common Production Testing Failures (Local vs. CI &amp; Context Leakage)", styles["Body"]), Paragraph("Section 11", styles["Body"])],
        [Paragraph("12. Testing Security &amp; Failure Paths (401, 403, RFC 7807 &amp; Idempotency)", styles["Body"]), Paragraph("Section 12", styles["Body"])],
        [Paragraph("13. Advanced Interview Questions — 15 Architectural &amp; Production Scenarios", styles["Body"]), Paragraph("Section 13", styles["Body"])],
        [Paragraph("14. Hands-On Capstone Lab &amp; Self-Assessment Mastery Check", styles["Body"]), Paragraph("Section 14", styles["Body"])],
        [Paragraph("15. JUnit 5 Complete Mastery Checklist &amp; Final Protocol", styles["Body"]), Paragraph("Section 15", styles["Body"])],
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

    # 3. Assemble Source Content Flowables
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

    print("Compiling BEH_JUNIT5_COMPLETE_HANDBOOK.pdf...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Compilation finished successfully -> {out_pdf}")

    # Verify with PyMuPDF
    pdf_doc = pymupdf.open(out_pdf)
    page_count = len(pdf_doc)
    print(f"Verification: Successfully opened PDF. Total pages: {page_count}")
    assert page_count > 0, "PDF has 0 pages!"
    blank_pages = [i+1 for i, page in enumerate(pdf_doc) if not page.get_text().strip()]
    print(f"Blank pages count: {len(blank_pages)}")
    assert len(blank_pages) == 0, f"Blank pages found: {blank_pages}"
    pdf_doc.close()
    print("Verification completed: All pages contain non-empty rendered text. Zero blank pages.")


if __name__ == "__main__":
    build_junit5_pdf()
