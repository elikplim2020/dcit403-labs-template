"""Build the Lab 2 report as a .docx, following DCIT403_Lab_Report_Template.docx.

Run from the ``lab02`` folder with the bundled Python::

    python report/build_report.py

Placeholders that only the student can fill (name, ID, repository) are highlighted
in yellow so they cannot be missed. The report is kept to three pages.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent

STUDENT_NAME = "Kimathi Sedegah"
STUDENT_ID = "22237205"
OUT_DOCX = HERE / f"DCIT403_Lab02_{STUDENT_ID}.docx"

ACCENT = RGBColor(0x1F, 0x38, 0x64)
GREY = RGBColor(0x59, 0x59, 0x59)

# The nine traces in evidence/, with the results of the recorded run.
TRACES = [
    ("trace_1_budget", "Budget question, calculator only", "finished", "3/6",
     "calculator x2"),
    ("trace_2_maize_both_tools", "Maize and transport, then a capital city", "finished",
     "4/6", "calculator x2, wiki x1"),
    ("trace_3_price_both_tools", "Price per bag, then Kintampo", "finished", "3/6",
     "calculator x1, wiki x1"),
    ("trace_4_wiki_missing", "A page that does not exist", "finished", "3/6",
     "wiki x2"),
    ("trace_5_no_tool", "A greeting, no tool needed", "finished", "1/3", "none"),
    ("trace_6_badly_worded", "Badly worded; unknown tool recovered", "finished", "3/6",
     "calculator x1"),
    ("trace_7_unparseable_reply", "No Action line; format corrected", "finished", "3/6",
     "calculator x1"),
    ("trace_8_max_steps", "Model that never finishes", "max_steps", "3/3",
     "calculator x3"),
    ("trace_9_repeat_guard", "The same call over and over", "finished", "5/6",
     "calculator x2"),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def shade(cell, hex_fill: str) -> None:
    """Fill a table cell with a solid colour."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def no_split(row) -> None:
    """Keep a table row on one page instead of breaking it across two."""
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def add_page_number(paragraph) -> None:
    """Put a PAGE field in the footer."""
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def placeholder(paragraph, text: str) -> None:
    """A yellow-highlighted run that the student must replace."""
    run = paragraph.add_run(text)
    run.bold = True
    run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def body(document, text: str):
    paragraph = document.add_paragraph()
    paragraph.add_run(text)
    paragraph.paragraph_format.space_after = Pt(4)
    return paragraph


def code_block(document, lines: list[str]) -> None:
    """Monospaced excerpt with a light background."""
    table_obj = document.add_table(rows=1, cols=1)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    no_split(table_obj.rows[0])
    cell = table_obj.cell(0, 0)
    shade(cell, "F2F2F2")
    cell.paragraphs[0].text = ""
    for index, line in enumerate(lines):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        run = paragraph.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 0.6


def caption(document, text: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(8)
    run.italic = True
    run.font.color.rgb = GREY
    paragraph.paragraph_format.space_after = Pt(8)


def table(document, headers: list[str], rows: list[list[str]], widths=None):
    table_obj = document.add_table(rows=1, cols=len(headers))
    table_obj.style = "Table Grid"
    table_obj.autofit = False
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, header in enumerate(headers):
        cell = table_obj.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.size = Pt(8)
        shade(cell, "DCE6F1")
    for row in rows:
        cells = table_obj.add_row().cells
        no_split(table_obj.rows[-1])
        for index, value in enumerate(row):
            cells[index].text = ""
            paragraph = cells[index].paragraphs[0]
            run = paragraph.add_run(value)
            run.font.size = Pt(8)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
    if widths:
        for row in table_obj.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Cm(width)
    return table_obj


# --------------------------------------------------------------------------- #
# The document
# --------------------------------------------------------------------------- #

def build() -> Path:
    document = Document()

    section = document.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(1.7), Cm(1.6)
    section.left_margin = section.right_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.06
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    for name, size in (("Heading 1", 12.5), ("Heading 2", 10.5)):
        style = document.styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = ACCENT
        style.paragraph_format.space_before = Pt(9)
        style.paragraph_format.space_after = Pt(3)

    # ---- cover block ------------------------------------------------------- #
    def centred(text: str, size: float, bold: bool = True, colour=ACCENT,
                space_after: float = 0):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        run.font.color.rgb = colour
        paragraph.paragraph_format.space_after = Pt(space_after)

    centred("UNIVERSITY OF GHANA", 12.5)
    centred("DEPARTMENT OF COMPUTER SCIENCE", 10, space_after=8)
    centred("DCIT 403: DESIGNING INTELLIGENT AGENTS", 10, space_after=12)
    centred("LAB 2 REPORT", 16, space_after=1)
    centred("Architectures: A ReAct Agent From Scratch", 11, bold=False,
            colour=GREY, space_after=12)

    cover_rows = [
        ("Student name", STUDENT_NAME),
        ("Student ID", STUDENT_ID),
        ("Lab number and title", "Lab 2 - Architectures: A ReAct Agent From Scratch"),
        ("Lab repository link", ""),
        ("Date submitted", date.today().strftime("%d %B %Y")),
    ]
    cover = document.add_table(rows=0, cols=2)
    cover.style = "Table Grid"
    for label, value in cover_rows:
        cells = cover.add_row().cells
        no_split(cover.rows[-1])
        run = cells[0].paragraphs[0].add_run(label)
        run.bold = True
        run.font.size = Pt(9)
        shade(cells[0], "F2F2F2")
        cells[0].width = Cm(5.0)
        cells[1].width = Cm(12.0)
        cells[1].paragraphs[0].paragraph_format.space_after = Pt(0)
        if value:
            run = cells[1].paragraphs[0].add_run(value)
            run.font.size = Pt(9)
        else:
            placeholder(cells[1].paragraphs[0], "[fill in]")

    document.add_paragraph().paragraph_format.space_after = Pt(0)

    # ---- 1. Objective ------------------------------------------------------ #
    document.add_heading("1. Objective", level=1)
    body(
        document,
        "This lab builds a ReAct agent from scratch, with no agent framework, for a "
        "trader at Makola Market who needs costing and quick facts. The agent is a "
        "loop: the model writes a Thought, chooses an Action from two tools (a "
        "calculator and a Wikipedia lookup), and the code returns the result as an "
        "Observation. A second aim is to measure what the same model does with no "
        "tools at all, so the value of the loop can be stated as a number.",
    )

    # ---- 2. Concept and classical root ------------------------------------- #
    document.add_heading("2. Concept and Classical Root", level=1)
    body(
        document,
        "The classical architectures differ in what the agent does with a percept. A "
        "reactive agent maps the current percept straight to an action through a "
        "condition-action rule: a thermostat heats when the room is cold, is fast, and "
        "keeps no memory and no plan. A deliberative agent holds an internal model of "
        "the world, reasons about goals and plans before acting; a chess engine "
        "searching a game tree is the clean example, and its cost is time. BDI is a "
        "practical form of deliberation, with beliefs for what the agent holds true, "
        "desires for the goals it wants and intentions for the plans it has committed "
        "to, cycling through perceive, update beliefs, choose intentions, execute one "
        "step. A hybrid agent keeps a fast reactive layer over a deliberative one.",
    )
    body(
        document,
        "ReAct is a hybrid in exactly that sense, and the trace shows it. The Thought "
        "line is deliberation: before acting, the agent states a plan, \u201cI need the "
        "total cost first \u2026 now I subtract it from the budget\u201d. The Action and "
        "Observation lines are reactive: each step answers the newest observation, and "
        "the model re-decides from scratch instead of executing a fixed programme. Read "
        "against BDI, the conversation so far is the belief base (the question, then "
        "the observations 1025 and 175), the trader's question is the desire, and the "
        "one-step plan in the Thought is the intention, discharged by finish. That is "
        "why the loop needs a step limit: a deliberative cycle that never commits is a "
        "runaway, so max_steps is the classical termination condition made explicit.",
    )
    body(
        document,
        "The build keeps the layers apart: the prompt supplies the reasoning frame, the "
        "parser is the boundary between deliberation and action, and the tools are the "
        "only part that touches the world. The mapping predicts this split, because the "
        "model plans and chooses while the code acts and perceives.",
    )

    # ---- 3. Implementation ------------------------------------------------- #
    document.add_heading("3. Implementation", level=1)
    body(
        document,
        "tools.py holds two actuators, both returning text because the result goes "
        "straight back into the conversation. calculator parses the expression with ast "
        "and walks a whitelist of five node types, so __import__('os') raises instead of "
        "running; every failure, from code to division by zero to an unsupported "
        "operator, comes back as an Error string, because an exception inside a tool "
        "would kill the loop. wiki_lookup uses the REST summary endpoint, turns a "
        "missing page into a sentence the model can pass on, and cuts the extract at 800 "
        "characters on a word boundary. A registry plus run_tool dispatches by name and "
        "offers the nearest name with difflib when the model misspells one.",
    )
    lead_in = body(
        document,
        "react_agent.py is the loop. The system prompt names the tools, fixes the three "
        "labels and forbids the model from writing observations; "
        "stop=[\"Observation:\"] enforces that boundary at the API. The parser is the "
        "manual's regex, applied after normalise_labels has removed decoration that "
        "models add:",
    )
    # The code block cannot split, so let Word break the page before it if needed.
    code_block(
        document,
        [
            "ACTION_RE = re.compile(r\"Action:\\s*(\\w+)\\s*\\nAction Input:\\s*(.*)\", re.DOTALL)",
            "",
            "def parse(text):",
            "    m = ACTION_RE.search(normalise_labels(text))   # labels cleaned first",
            "    if not m:",
            "        return None, None",
            "    payload = re.split(r\"(?i)\\bObservation\\s*:\", m.group(2))[0]",
            "    return m.group(1).strip(), payload.strip()",
        ],
    )
    caption(
        document,
        "Excerpt 1. The parser. The regex is the lab's; normalisation is the only "
        "addition, and the Observation cut stops a model inventing its own result.",
    )
    body(
        document,
        "Every failure ends as an observation, never as an exception: an unreadable "
        "reply receives the format template back; an unknown tool receives the list of "
        "real names; finish with no answer is rejected once; the same call three times is "
        "intercepted rather than executed again; max_steps ends the run with the last "
        "thing the agent saw; a model outage is reported in words. HTTP 429 waits two "
        "seconds, then four, then gives up. Each run is written to evidence/ with a "
        "header recording the model source, the step limit, timings per tool call, token "
        "totals and the final status, so a trace is evidence rather than a transcript.",
    )

    # ---- 4. Evidence ------------------------------------------------------- #
    document.add_heading("4. Evidence", level=1)
    body(
        document,
        "The budget question is answered in three steps, with the calculator called "
        "twice (1025, then 175). The hand trace from Part A and the machine trace agree "
        "line for line, including both sub-expressions. Table 1 lists the nine runs.",
    )
    table(
        document,
        ["Trace", "Question", "Status", "Steps", "Tools"],
        [[t[0], t[1], t[2], t[3], t[4]] for t in TRACES],
        widths=[5.2, 4.8, 1.7, 1.2, 3.5],
    )
    caption(
        document,
        "Table 1. The nine traces in evidence/. All six lab questions reach a final "
        "answer; traces 7 to 9 are the robustness drills.",
    )
    body(
        document,
        "On the budget question the baseline was given three attempts against the live "
        "model and answered GHS 175 correctly all three times. The agent's advantage is "
        "therefore not raw accuracy on this question: it is auditability. The trace shows "
        "the expression and the tool's result, so a wrong answer would be visible as a "
        "wrong expression, whereas the baseline's arithmetic can only be checked by "
        "re-doing it by hand. Table 2 records both.",
    )
    table(
        document,
        ["Path", "Budget question", "Evidence"],
        [
            ["Model alone (no tools), 3 attempts", "3/3 correct: GHS 175 each time",
             "evidence/baseline_live_groq.md"],
            ["ReAct agent, 1 attempt", "Correct: GHS 175, calculator x2",
             "evidence/trace_1_budget.txt"],
        ],
        widths=[6.0, 6.1, 4.3],
    )
    caption(
        document,
        "Table 2. Baseline against ReAct on the same question. Both reach the right "
        "answer; only the agent's route is checkable from the evidence.",
    )
    body(
        document,
        "Provenance. The nine traces shipped with this build come from the rehearsal "
        "harness (scripted_model.py), which replays fixed model replies, because LiteLLM "
        "could not be installed on the machine that built the folder. The loop, the "
        "parser, the tools, their timings and the Wikipedia observations in those files "
        "are real, and each file is stamped MODEL SOURCE: scripted rehearsal. A live run "
        "was attempted against Groq's gpt-oss-20b: the baseline succeeded (the numbers in "
        "Table 2 are from it) and every ReAct call failed with tool_use_failed, recorded "
        "in evidence/live_groq_attempt.md. The nine live traces must therefore be "
        "produced in the Codespace with python run_evidence.py.",
    )

    # ---- 5. Failure and fix ------------------------------------------------ #
    document.add_heading("5. Failure and Fix", level=1)
    body(
        document,
        "What happened. The loop parsed the first replies correctly, then sent the "
        "corrective format message to a model that had answered in perfect Markdown: "
        "\u201c**Action:** calculator\u201d. The same happened when the model numbered "
        "its three lines, \u201c2. Action: calculator / 3. Action Input: 1+1\u201d. In "
        "both cases parse() returned (None, None), although the action and the input were "
        "unambiguous to a reader.",
    )
    body(
        document,
        "Why it happened. ACTION_RE is anchored on the literal label text: it expects "
        "\u201cAction Input:\u201d to begin the line directly after the action name. "
        "Markdown adds two asterisks after the colon, which \\s* cannot absorb, and "
        "numbering puts \u201c3. \u201d in front of the label, which \\n cannot skip. The "
        "model complied with the protocol's meaning but not with its spelling, and the "
        "parser tested spelling only. That is the reactive layer reacting to a "
        "formatting token while the deliberative plan was sound.",
    )
    body(
        document,
        "The fix. normalise_labels() runs before the regex and does three things: it "
        "removes Markdown decoration, it strips leading list enumerators and bullets "
        "where a label follows, and it rewrites label spelling and spacing to the "
        "canonical form. The regex itself is unchanged, so the manual's parser is still "
        "the thing parsing, and the Observation cut stays in parse(). The change is "
        "guarded by tests written before the fix: test_rejects_decorated_labels asserts "
        "that the bare regex fails on four decorated replies, and "
        "test_normalise_then_parse_reads_them asserts that the real parser reads the "
        "same text.",
    )
    body(
        document,
        "The result. The suite is 35 tests and all pass, and trace_7_unparseable_reply "
        "shows the recovery from the inside: a reply with no Action line is answered with "
        "the format template and the model complies on the next step, so the run still "
        "finishes in three. What the fix does not cover is a reply that puts both labels "
        "on one line (\u201cAction: calculator Action Input: 4*185\u201d); that still "
        "returns (None, None) and costs one corrective step, which is the behaviour I "
        "would keep, because guessing which text belongs to which label is how a parser "
        "starts executing the wrong expression.",
    )

    body(
        document,
        "A second failure appeared only on the live run, and it is the more interesting "
        "one. Every ReAct call against Groq's gpt-oss-20b returned HTTP 400, "
        "tool_use_failed: the model answered the prompt by emitting a native tool call "
        "for the calculator instead of a Thought/Action/Action Input reply, and it did so "
        "in all nine runs, while the same model answered the tool-free baseline correctly "
        "in the same session. The cause is that gpt-oss-20b is trained to call declared "
        "tools, and the Lab 2 prompt describes tools in prose while the request declares "
        "none, so the call is rejected before the loop can parse anything. The loop "
        "behaved correctly: nine runs ended with STATUS model_error and a readable "
        "message, and none crashed. The text protocol and native function calling are "
        "the same idea behind two interfaces, and this is the seam between them that Lab "
        "3 opens up. The record is evidence/live_groq_attempt.md.",
    )

    # ---- 6. Project link --------------------------------------------------- #
    document.add_heading("6. Project Link", level=1)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run("Team repository: ")
    run.bold = True
    placeholder(paragraph, "[paste team repository URL]")

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run("My contribution this week: ")
    run.bold = True
    placeholder(paragraph, "[one line: team formed, roles agreed, problem-owner shortlist started]")

    # ---- footer ------------------------------------------------------------ #
    footer = section.footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_paragraph.add_run(
        f"DCIT 403 Lab 2 - {STUDENT_NAME} ({STUDENT_ID}) - page "
    )
    run.font.size = Pt(8)
    run.font.color.rgb = GREY
    add_page_number(footer_paragraph)
    for run in footer_paragraph.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = GREY

    document.core_properties.title = "DCIT 403 Lab 2 - ReAct Agent From Scratch"
    document.core_properties.subject = "Lab report"
    document.save(OUT_DOCX)
    return OUT_DOCX


def word_count(path: Path) -> int:
    """Words in Sections 1 to 5 of the saved report, tables excluded."""
    document = Document(path)
    counting, total = False, 0
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if paragraph.style.name.startswith("Heading"):
            counting = text.startswith(("1.", "2.", "3.", "4.", "5."))
            continue
        if counting and text and not text.startswith(("Table ", "Excerpt ")):
            total += len(text.split())
    return total


if __name__ == "__main__":
    path = build()
    print(f"[written] {path}")
    print(f"[words]   Sections 1-5: {word_count(path)} (tables excluded)")
