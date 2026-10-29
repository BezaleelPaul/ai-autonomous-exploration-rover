#!/usr/bin/env python3
"""Build the photo-dated narrative report for the AI vision-guided rover.

Run with the Python 3.12 interpreter that has python-docx installed::

    py -3.12 tools/generate_story_report.py

The script produces ``reports/AI_Rover_Project_Report.docx``.  A companion
PowerShell step uses Word to refresh the TOC fields and export the PDF.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt, RGBColor

from report_lib import (
    AMBER,
    ASSETS,
    BLUE,
    CHART_DIR,
    GREEN,
    LIGHT_BLUE,
    LOGS,
    MID_GREY,
    NAVY,
    RED,
    REPORTS,
    ROOT,
    STEEL,
    add_body,
    add_bullets,
    add_callout,
    add_chapter,
    add_figure,
    add_front_heading,
    add_header,
    add_horizontal_rule,
    add_numbered,
    add_page_footer,
    add_table,
    add_table_of_figures,
    add_table_of_tables,
    add_toc,
    make_charts,
    new_section,
    page_setup,
    prepare_assets,
    style_document,
)

DOCX_PATH = REPORTS / "AI_Rover_Project_Report.docx"
PDF_PATH = REPORTS / "AI_Rover_Project_Report.pdf"

STUDENT = "KUNDURU NAGENDRA REDDY"
REG_NO = "18BBTCS053"
BRANCH = "Electronics and Communication Engineering"
DEPARTMENT = "Department of Electronics and Communication Engineering"
GUIDE = "[Project Guide Name]"
GUIDE_DESIGNATION = "Assistant Professor"
HOD = "Dr. Raja Krishnamoorthi"
UNIVERSITY = "CMR University"
ACADEMIC_YEAR = "2026-2027"
TITLE = (
    "AI-BASED VISION-GUIDED AUTONOMOUS ROVER WITH DISTRIBUTED "
    "EDGE INTELLIGENCE AND SAFETY CONTROL"
)
SHORT_TITLE = "AI Vision-Guided Rover"
ADDRESS = (
    "Off Hennur - Bagalur Main Road, Near Kempegowda International Airport, "
    "Chagalahatti, Bangalore, Karnataka - 562149"
)


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def build_cover(doc: Document, assets: dict[str, Path]) -> None:
    section = doc.sections[0]
    page_setup(section)
    section.footer.is_linked_to_previous = False
    section.header.is_linked_to_previous = False

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    if "logo" in assets:
        p.add_run().add_picture(str(assets["logo"]), width=Inches(2.05))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("SCHOOL OF ENGINEERING AND TECHNOLOGY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("CMR UNIVERSITY, BENGALURU")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string("444444")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("A Project Report on")
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.italic = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(16)
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.right_indent = Cm(0.6)
    run = p.add_run(f"\u201c{TITLE}\u201d")
    run.font.name = "Times New Roman"
    run.font.size = Pt(19)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(
        "Submitted in partial fulfillment of the requirements for the award of the degree of"
    )
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("BACHELOR OF TECHNOLOGY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("in")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(20)
    run = p.add_run(BRANCH.upper())
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(BLUE)

    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    left, right = table.rows[0].cells
    left.width = Inches(3.1)
    right.width = Inches(3.1)

    p = left.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("SUBMITTED BY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(MID_GREY)
    p2 = left.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    run = p2.add_run(STUDENT)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12.5)
    run.bold = True
    p3 = left.add_paragraph()
    p3.paragraph_format.space_after = Pt(0)
    run = p3.add_run(f"({REG_NO})")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)

    p = right.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("GUIDED BY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(MID_GREY)
    p2 = right.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    run = p2.add_run(GUIDE)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12.5)
    run.bold = True
    p3 = right.add_paragraph()
    p3.paragraph_format.space_after = Pt(0)
    run = p3.add_run(f"{GUIDE_DESIGNATION}, Dept. of ECE")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(26)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(DEPARTMENT)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11.5)
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(ADDRESS)
    run.font.name = "Times New Roman"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor.from_string("444444")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run(ACADEMIC_YEAR)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.bold = True


def build_certificate(doc: Document, assets: dict[str, Path]) -> None:
    doc.add_page_break()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    if "logo" in assets:
        p.add_run().add_picture(str(assets["logo"]), width=Inches(1.55))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("SCHOOL OF ENGINEERING AND TECHNOLOGY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("Chagalahatti, Bengaluru, Karnataka - 562149")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run(DEPARTMENT)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    run = p.add_run("CERTIFICATE")
    run.font.name = "Times New Roman"
    run.font.size = Pt(18)
    run.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    body = (
        f"This is to certify that the project entitled \u201c{TITLE}\u201d has been "
        f"successfully carried out by {STUDENT} ({REG_NO}) in partial fulfillment of the "
        f"requirements for the award of the degree of Bachelor of Technology in {BRANCH} "
        f"of {UNIVERSITY}, Bengaluru during the academic year {ACADEMIC_YEAR}. The project "
        f"report has been approved as it satisfies the academic requirements in respect of "
        f"project work prescribed for the said degree."
    )
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.6
    p.paragraph_format.space_after = Pt(34)
    run = p.add_run(body)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)

    sig = doc.add_table(rows=2, cols=2)
    sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    sig.autofit = True
    sig.rows[0].cells[0].width = Inches(3.1)
    sig.rows[0].cells[1].width = Inches(3.1)
    for idx, label in enumerate(("Signature of the Guide", "Signature of the HOD")):
        p = sig.rows[0].cells[idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(22)
        run = p.add_run("_ _ _ _ _ _ _ _ _ _ _ _")
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)
        p2 = sig.rows[1].cells[idx].add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_after = Pt(0)
        run = p2.add_run(label)
        run.font.name = "Times New Roman"
        run.font.size = Pt(10.5)
        run.bold = True
        p3 = sig.rows[1].cells[idx].add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p3.paragraph_format.space_after = Pt(0)
        value = GUIDE if idx == 0 else HOD
        run = p3.add_run(value)
        run.font.name = "Times New Roman"
        run.font.size = Pt(10.5)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(30)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run("Examiners Signature with date:")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.bold = True
    for i in (1, 2):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(f"{i}.  ______________________________________________")
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)


def build_front_matter(doc: Document, assets: dict[str, Path]) -> None:
    new_section(doc, "lowerRoman", 1, SHORT_TITLE)

    add_front_heading(doc, "Acknowledgement", page_break=False)
    add_body(
        doc,
        "The completion of this project would not have been possible without the guidance, "
        "patience, and practical support of many people. I take this opportunity to record "
        "my sincere gratitude to all of them.",
    )
    add_body(
        doc,
        f"I express my heartfelt thanks to {HOD}, Professor and Head, {DEPARTMENT}, "
        f"School of Engineering and Technology, {UNIVERSITY}, Bengaluru, for his constant "
        "encouragement and for creating an environment in which hands-on engineering is "
        "valued. His emphasis on evidence, safety, and clear documentation shaped the way "
        "this project was executed.",
    )
    add_body(
        doc,
        f"I am deeply grateful to {GUIDE}, {GUIDE_DESIGNATION}, {DEPARTMENT}, for the "
        "continuous technical guidance, constructive criticism, and patient review of every "
        "build stage. The suggestions on power isolation, watchdog design, and test "
        "discipline directly influenced the final architecture.",
    )
    add_body(
        doc,
        "I thank the laboratory technicians and staff of the School of Engineering and "
        "Technology for access to tools, measurement equipment, and workspace. I also thank "
        "my classmates and friends who helped hold components, check connections, and "
        "photograph the build at the end of long sessions. Their willingness to pause and "
        "document the work made this chronological report possible.",
    )
    add_body(
        doc,
        "Finally, I thank my family for their patience and encouragement during the weeks "
        "of assembly, debugging, and late-night testing. Any remaining errors or omissions "
        "in this report are my own.",
    )
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(18)
    run = p.add_run(f"{STUDENT}\n{REG_NO}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.bold = True

    add_front_heading(doc, "Declaration")
    add_body(
        doc,
        f"I, {STUDENT} ({REG_NO}), a student of the Bachelor of Technology programme in "
        f"{BRANCH}, School of Engineering and Technology, {UNIVERSITY}, Bengaluru, hereby "
        f"declare that the project work entitled \u201c{TITLE}\u201d has been carried out by "
        f"me under the guidance of {GUIDE}, {GUIDE_DESIGNATION}, {DEPARTMENT}. This report is "
        "submitted in partial fulfillment of the requirements for the award of the degree of "
        f"Bachelor of Technology in {BRANCH} by {UNIVERSITY}, Bengaluru, during the academic "
        f"year {ACADEMIC_YEAR}.",
    )
    add_body(
        doc,
        "I further declare that the work presented in this report is original and that all "
        "sources of information, open-source libraries, datasets, and prior work have been "
        "acknowledged in the references. Photographs included in this report were taken by "
        "me or by my project associates during the build and are used here as primary "
        "documentary evidence. Measured values are reported as measured; design estimates "
        "and items still awaiting hardware validation are explicitly labelled as such.",
    )
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    run = p.add_run("Place: Bengaluru")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    p = doc.add_paragraph()
    run = p.add_run("Date: ____________________")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(12)
    run = p.add_run(f"{STUDENT}\n{REG_NO}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.bold = True

    add_front_heading(doc, "Abstract")
    add_body(
        doc,
        "Small autonomous ground vehicles must see, decide, and stop safely within tight "
        "limits on power, memory, and cost. This report documents the design, assembly, "
        "software integration, testing, and recovery of a low-cost vision-guided "
        "differential-drive rover built around three cooperating units: an ESP32-CAM that "
        "streams Wi-Fi video, a laptop that runs YOLO-based detection and the decision "
        "engine, and an Arduino UNO that enforces hard real-time motor and obstacle safety. "
        "The physical platform uses a 2S 18650 battery pack, an LM2596 buck converter, a "
        "TB6612FNG dual H-bridge, two TT gear motors, and an HC-SR04 ultrasonic sensor.",
    )
    add_body(
        doc,
        "The report follows the build chronologically from the first component photographs "
        "on 3 October 2026 to the final power integration on 26 October 2026. It records the "
        "mechanical assembly, the two-tier electronics stack, the wiring and power "
        "architecture, the firmware and host software, the control law, and the test "
        "campaign. It also documents a battery-terminal short-circuit incident that damaged a "
        "small number of components, the root-cause analysis that followed, and the "
        "corrective actions: insulated terminals, strain relief, an inline fuse, and an "
        "upgrade from the baseline L298N driver to a TB6612FNG MOSFET driver.",
    )
    add_body(
        doc,
        "Bench evidence includes 311 passing tests, clean static analysis, successful "
        "Arduino and ESP32 firmware builds, three live Wokwi simulation runs, and measured "
        "detector benchmarks. The shipped YOLO11s configuration achieved recall 0.477, F1 "
        "0.601, and mAP@0.5 0.640 on the 128-image COCO128 evaluation set at a 320-pixel "
        "inference size. The report separates these measured results from the hardware "
        "measurements that remain pending, and it closes with limitations, future work, and "
        "the engineering lessons drawn from the short-circuit recovery.",
    )
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    run = p.add_run("Keywords: ")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run.bold = True
    run = p.add_run(
        "autonomous rover; edge intelligence; ESP32-CAM; Arduino UNO; YOLO; differential "
        "drive; ultrasonic safety; TB6612FNG; power isolation; failure analysis."
    )
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run.italic = True

    add_front_heading(doc, "Documentation Note")
    add_body(
        doc,
        "This report is deliberately organised as an engineering narrative rather than a "
        "collection of disconnected specifications. Each build stage is anchored to the date "
        "and time carried by the original photograph, so the reader can follow the project "
        "in the same order in which it actually happened. The photographs are primary "
        "evidence: they show what was physically assembled, not what was intended.",
    )
    add_body(
        doc,
        "Three evidence labels are used throughout. [MEASURED] means the value came from a "
        "logged run or a bench instrument and is reproducible from the files in the "
        "repository. [DESIGN] means a calculated or selected value that has not yet been "
        "confirmed on the physical rover. [PENDING] means the check requires hardware that "
        "was not available, or was deferred after the 26 October incident. This convention "
        "prevents a design target from being mistaken for a measured result.",
    )
    add_callout(
        doc,
        "How to read the build chapters",
        "Chapters 5 and 6 are the component and assembly story. Chapter 7 explains the "
        "electrical chain. Chapters 8 and 9 explain the software and safety logic. Chapter 10 "
        "presents the measured results. Chapter 11 is the incident case study. The appendices "
        "contain the bill of materials, pin map, photo index, and test summary.",
    )

    add_front_heading(doc, "Table of Contents")
    add_toc(doc)

    add_front_heading(doc, "List of Figures")
    add_table_of_figures(doc)

    add_front_heading(doc, "List of Tables")
    add_table_of_tables(doc)

    add_front_heading(doc, "List of Abbreviations")
    add_table(
        doc,
        ["Abbreviation", "Expansion"],
        [
            ["AI", "Artificial Intelligence"],
            ["AP", "Access Point (Wi-Fi)"],
            ["BOM", "Bill of Materials"],
            ["CLAHE", "Contrast-Limited Adaptive Histogram Equalization"],
            ["CMOS", "Complementary Metal-Oxide-Semiconductor"],
            ["COCO", "Common Objects in Context (dataset)"],
            ["CPU", "Central Processing Unit"],
            ["DVP", "Digital Video Port"],
            ["FMEA", "Failure Mode and Effects Analysis"],
            ["FSM", "Finite State Machine"],
            ["GPIO", "General-Purpose Input/Output"],
            ["H-Bridge", "Electronic circuit that reverses motor polarity"],
            ["I2C", "Inter-Integrated Circuit (bus)"],
            ["IMU", "Inertial Measurement Unit"],
            ["Li-ion", "Lithium-ion"],
            ["LDO", "Low-Dropout Regulator"],
            ["MJPEG", "Motion JPEG"],
            ["MOSFET", "Metal-Oxide-Semiconductor Field-Effect Transistor"],
            ["PWM", "Pulse-Width Modulation"],
            ["RSS", "Resident Set Size (memory)"],
            ["SBC", "Single-Board Computer"],
            ["SLAM", "Simultaneous Localization and Mapping"],
            ["TTL", "Transistor-Transistor Logic"],
            ["UART", "Universal Asynchronous Receiver/Transmitter"],
            ["USB", "Universal Serial Bus"],
            ["YOLO", "You Only Look Once (object detector family)"],
        ],
        widths=[1.3, 4.8],
        caption="Abbreviations used in this report.",
        font_size=9,
    )


def chapter_introduction(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 1", "Introduction", page_break=False)
    add_body(
        doc,
        "Autonomous mobile robotics sits at the intersection of mechanical design, power "
        "electronics, real-time control, and computer vision. A useful mobile robot must do "
        "more than move: it must build a usable picture of its surroundings, choose an "
        "action quickly enough to matter, and stop safely when the picture is incomplete. "
        "The difficulty is not any one of these tasks in isolation; it is making them "
        "cooperate on a small, low-cost platform.",
    )
    add_body(
        doc,
        "Conventional small robots often solve the perception problem by tethering the "
        "vehicle to a laptop or by streaming video to a remote server. This is convenient "
        "for a demonstration, but it introduces wireless latency, a dependency on network "
        "coverage, and a failure mode in which the robot keeps moving after the link has "
        "died. The alternative is to place all intelligence on the robot, which is "
        "attractive but quickly runs into the memory and thermal limits of inexpensive "
        "microcontrollers. This project takes a middle path: distribute the work across "
        "three units, but make the safety decision local and deterministic.",
    )

    doc.add_heading("1.1 Background", level=2)
    add_body(
        doc,
        "A differential-drive robot is the simplest useful mobile platform. Two independently "
        "driven wheels on a common axis produce forward motion when they turn together and "
        "rotation when they turn at different speeds. The mathematics is well understood, "
        "the mechanics are inexpensive, and the platform is robust. The challenge is the "
        "perception and decision layer that turns a camera image into a left or right wheel "
        "command.",
    )
    add_body(
        doc,
        "Modern object detectors based on deep convolutional networks, and more recently on "
        "transformers, can locate people, bottles, and other objects in a video frame with "
        "useful accuracy. However, the accurate models are too large for a microcontroller. "
        "A practical student build therefore separates the detector, which runs on a laptop "
        "or single-board computer, from the actuator controller, which runs on a "
        "microcontroller and must never miss a safety deadline. This separation is the "
        "central architectural idea of the present rover.",
    )

    doc.add_heading("1.2 Motivation", level=2)
    add_body(
        doc,
        "The motivation for the project came from three observations. First, many "
        "undergraduate robotics projects demonstrate motion but do not demonstrate "
        "dependable stopping. A robot that can follow a bottle but cannot stop at a wall is "
        "not yet a useful robot. Second, the components needed for a credible demonstration "
        "are now affordable: an ESP32-CAM, an Arduino UNO, a dual H-bridge, two gear motors, "
        "and an ultrasonic sensor cost less than a textbook. Third, the engineering is most "
        "convincing when the build itself is documented honestly, including the failures.",
    )
    add_body(
        doc,
        "The project was therefore framed around three questions. Can a low-cost rover track "
        "a visual target using only commodity parts? Can it guarantee a stop when the "
        "software, the camera, or the communication link fails? And can the build be "
        "documented in enough detail that another student could reproduce it, including the "
        "mistakes? The short-circuit incident described in Chapter 11 is part of that "
        "commitment to honest documentation.",
    )

    doc.add_heading("1.3 The Project in Brief", level=2)
    add_body(
        doc,
        "The rover is a two-wheel differential-drive platform with a front caster. An "
        "ESP32-CAM mounted on the upper deck captures video and serves it as a Wi-Fi MJPEG "
        "stream. A laptop pulls that stream, runs a YOLO-family detector, computes the "
        "horizontal error between the target bounding-box centre and the frame centre, and "
        "selects one of five commands: forward, backward, left, right, or stop. The command "
        "travels over USB serial to an Arduino UNO. The Arduino validates the character, "
        "checks the HC-SR04 distance, checks the communication watchdog, and only then "
        "drives the TB6612FNG dual H-bridge. The ESP32 and the Arduino have no data wire "
        "between them; the ESP32 is power-only. This avoids a 5 V-to-3.3 V level-shift "
        "hazard and keeps the camera noise away from the motor controller.",
    )
    add_figure(
        doc,
        assets["d_sys"],
        "Three-tier system architecture: ESP32-CAM video, laptop perception and decision, "
        "Arduino UNO safety and actuation.",
    )

    doc.add_heading("1.4 Objectives", level=2)
    add_body(doc, "The project set out to achieve the following objectives:")
    add_numbered(
        doc,
        [
            "Design and assemble a stable, repairable differential-drive chassis from acrylic "
            "plates, TT gear motors, a caster, and a 2S 18650 battery pack.",
            "Build an isolated power architecture in which the motor rail and the logic rail are "
            "separate, with a common star ground and an inline fuse.",
            "Implement a camera pipeline that streams live video from the ESP32-CAM to the host "
            "over Wi-Fi without a wired data link to the Arduino.",
            "Implement a YOLO-based detector and a three-zone steering policy that converts a "
            "bounding box into forward, left, right, or stop commands.",
            "Implement a deterministic safety layer on the Arduino with a 3 s communication "
            "watchdog and a 15 cm forward obstacle cutoff.",
            "Document every build stage with date-stamped photographs and a written engineering "
            "narrative.",
            "Measure the detector and system performance, separate measured results from design "
            "estimates, and record the limitations honestly.",
            "Analyse the 26 October battery short-circuit incident, identify its root cause, and "
            "implement corrective actions that reduce the chance of recurrence.",
        ],
    )

    doc.add_heading("1.5 Scope and Delimitations", level=2)
    add_body(
        doc,
        "The rover is an indoor, low-speed, single-target demonstrator. It is not a "
        "self-driving car, a SLAM platform, or a production robot. The perception stack "
        "tracks one target class at a time, the camera is monocular, and there are no wheel "
        "encoders in the baseline build. The laptop remains part of the control loop for "
        "detection and high-level decisions; the Arduino is the local safety authority. The "
        "project does not claim collision-free navigation in cluttered spaces, nor does it "
        "claim operation in rain, direct sunlight, or on steep slopes.",
    )
    add_body(
        doc,
        "Within those limits, the scope includes the complete mechanical build, the power "
        "and signal wiring, the ESP32 camera firmware, the Arduino motor and safety "
        "firmware, the host-side perception and decision software, a dashboard, a test "
        "suite, and the documentation set. The project deliberately excludes custom PCB "
        "fabrication, 3D-printed enclosures, and battery-management electronics; these are "
        "recorded as future work.",
    )

    doc.add_heading("1.6 Report Organisation", level=2)
    add_body(
        doc,
        "Chapter 2 states the problem and the requirements. Chapter 3 reviews the relevant "
        "technical background. Chapter 4 describes the system architecture. Chapter 5 "
        "documents the components and the reasons for selecting them. Chapter 6 is the "
        "chronological build log, illustrated with the original photographs. Chapter 7 "
        "explains the wiring and power architecture. Chapter 8 describes the software and AI "
        "pipeline. Chapter 9 covers the control law and the safety layers. Chapter 10 "
        "presents the test campaign and the measured results. Chapter 11 is the short-circuit "
        "case study. Chapter 12 discusses limitations and future work, and Chapter 13 "
        "concludes. The appendices contain the bill of materials, the pin map, the photo "
        "index, the test summary, and the repository map.",
    )


def chapter_problem(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 2", "Problem Definition and Requirements")
    add_body(
        doc,
        "The problem is not simply to make a robot move. The problem is to make a robot "
        "behave acceptably when the world, the sensors, and the software are all imperfect. "
        "A camera can be blinded by a window; a Wi-Fi link can drop; an ultrasonic sensor can "
        "miss a soft or angled obstacle; a motor can stall; a battery terminal can touch a "
        "metal chassis. The design must be judged by how it behaves in those cases, not only "
        "by how well it follows a target in a clean corridor.",
    )

    doc.add_heading("2.1 Problem Statement", level=2)
    add_body(
        doc,
        "Design and build a low-cost, vision-guided differential-drive rover that can track a "
        "designated object in indoor conditions and stop safely when an obstacle is detected, "
        "when the communication link is lost, or when the perception pipeline becomes stale. "
        "The rover must be repairable with hand tools, must run from a rechargeable battery, "
        "and must be documented in sufficient detail for another student to reproduce the "
        "build.",
    )
    add_body(
        doc,
        "The design must resolve a fundamental tension. Accurate vision requires computation "
        "that is difficult to place on a small microcontroller, while safety requires a "
        "controller that is not distracted by vision. The chosen resolution is a distributed "
        "architecture: the heavy perception runs on a laptop, the camera streams over Wi-Fi, "
        "and a separate microcontroller owns the motor and obstacle safety. The laptop may "
        "fail; the rover must still stop.",
    )

    doc.add_heading("2.2 Functional Requirements", level=2)
    add_table(
        doc,
        ["ID", "Requirement", "Acceptance criterion", "Priority"],
        [
            [
                "FR-01",
                "Capture live video",
                "ESP32-CAM serves an MJPEG stream at a usable frame rate over Wi-Fi.",
                "P0",
            ],
            [
                "FR-02",
                "Detect the target",
                "The host detector returns a bounding box for the configured target class.",
                "P0",
            ],
            [
                "FR-03",
                "Steer toward the target",
                "The decision engine selects F, L, R, or S from the box centre error.",
                "P0",
            ],
            [
                "FR-04",
                "Drive the motors",
                "The Arduino drives both TT motors forward, backward, left, and right.",
                "P0",
            ],
            [
                "FR-05",
                "Stop at an obstacle",
                "Forward motion is refused when the HC-SR04 distance is below 15 cm.",
                "P0",
            ],
            [
                "FR-06",
                "Stop on link loss",
                "The Arduino stops the motors after 3 s without a valid command.",
                "P0",
            ],
            [
                "FR-07",
                "Reject invalid commands",
                "Unknown characters produce STATUS:ERROR and no actuation.",
                "P0",
            ],
            [
                "FR-08",
                "Report telemetry",
                "Distance, status, and encoder ticks are reported over serial.",
                "P1",
            ],
            [
                "FR-09",
                "Provide a dashboard",
                "The host displays the annotated frame, command, and safety state.",
                "P1",
            ],
            [
                "FR-10",
                "Support a mock mode",
                "The host can run without hardware for demonstration and tests.",
                "P1",
            ],
            [
                "FR-11",
                "Log the mission",
                "Frames, decisions, and safety states are recorded to CSV/JSON.",
                "P1",
            ],
            [
                "FR-12",
                "Document the build",
                "Every stage has a dated photograph and a written note.",
                "P0",
            ],
        ],
        widths=[0.55, 1.55, 3.35, 0.65],
        caption="Functional requirements and acceptance criteria.",
        font_size=8.4,
    )

    doc.add_heading("2.3 Non-Functional Requirements", level=2)
    add_table(
        doc,
        ["ID", "Requirement", "Target / rationale"],
        [
            [
                "NFR-01",
                "Safety",
                "No single software or link failure may cause uncontrolled forward motion.",
            ],
            [
                "NFR-02",
                "Cost",
                "Prototype bill of materials below USD 70 using commodity modules.",
            ],
            [
                "NFR-03",
                "Power",
                "At least 90 minutes of intermittent indoor operation from a 2S 18650 pack.",
            ],
            [
                "NFR-04",
                "Latency",
                "Detection refresh at or below 1.0 s on the host for closed-loop control.",
            ],
            [
                "NFR-05",
                "Repairability",
                "Modules replaceable with a screwdriver and Dupont/soldered joints.",
            ],
            [
                "NFR-06",
                "Portability",
                "The complete rover fits on a 20 cm x 15 cm chassis footprint.",
            ],
            [
                "NFR-07",
                "Documentation",
                "Build steps reproducible from the report and repository files.",
            ],
            [
                "NFR-08",
                "Maintainability",
                "Configuration in YAML; no hard-coded pins or thresholds in application logic.",
            ],
        ],
        widths=[0.65, 1.35, 4.1],
        caption="Non-functional requirements.",
        font_size=8.6,
    )

    doc.add_heading("2.4 Constraints and Assumptions", level=2)
    add_body(doc, "The design was carried out under the following constraints:")
    add_bullets(
        doc,
        [
            "The host laptop is part of the perception loop; the rover is not fully standalone.",
            "The camera is a single OV2640 sensor with no depth channel; distance is inferred from "
            "the bounding-box size and from the ultrasonic sensor.",
            "The baseline drivetrain has no wheel encoders, so straight-line motion is open-loop "
            "and is corrected by visual feedback rather than by odometry.",
            "The HC-SR04 has a narrow acoustic cone and can miss soft, angled, or sound-absorbing "
            "obstacles.",
            "The chassis is acrylic and the electronics are exposed; the build is a bench "
            "prototype, not a sealed product.",
            "The 2S 18650 pack, buck converter, and motor driver are commodity modules with "
            "limited datasheet guarantees.",
            "The project is developed in a student laboratory with hand tools and a limited "
            "component inventory.",
        ],
    )
    add_body(
        doc,
        "The key assumptions are that the floor is flat and dry, the lighting is between "
        "roughly 20 and 2000 lux, the target is visible from the front hemisphere, and the "
        "operator keeps the rover within Wi-Fi range. These assumptions are stated explicitly "
        "because the test results in Chapter 10 are only valid within them.",
    )

    doc.add_heading("2.5 Design Decisions Summary", level=2)
    add_table(
        doc,
        ["Decision", "Alternative considered", "Why this choice"],
        [
            [
                "Three-tier split (ESP32 / laptop / Arduino)",
                "All-in-one ESP32 or Raspberry Pi",
                "Keeps vision off the safety controller; avoids a single point of failure.",
            ],
            [
                "Wi-Fi MJPEG from ESP32",
                "Wired UART or USB camera",
                "No 5 V/3.3 V level-shift hazard; camera can be placed remotely.",
            ],
            [
                "Arduino UNO safety supervisor",
                "ESP32 does everything",
                "Deterministic timing and simple, auditable firmware.",
            ],
            [
                "TB6612FNG motor driver",
                "L298N bipolar driver",
                "Lower voltage drop, less heat, smaller module; adopted after the incident.",
            ],
            [
                "HC-SR04 front ranging",
                "IR or LiDAR",
                "Low cost, simple interface, adequate for a 15 cm stop gate.",
            ],
            [
                "YOLO11s at 320 px",
                "DETR / RT-DETR / larger YOLO",
                "Best measured accuracy that still meets the 1 s refresh budget.",
            ],
            [
                "Laptop-in-the-loop",
                "On-board SBC",
                "Keeps cost and power low for a student prototype.",
            ],
        ],
        widths=[1.75, 1.65, 2.7],
        caption="Summary of the principal design decisions.",
        font_size=8.5,
    )


def chapter_literature(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 3", "Literature Review and Technical Background")
    add_body(
        doc,
        "This chapter reviews the ideas that shaped the design. It is not an exhaustive "
        "survey; it focuses on the four areas that directly influenced the rover: "
        "differential-drive locomotion, visual servoing, edge-capable object detection, and "
        "safety architectures for small robots.",
    )

    doc.add_heading("3.1 Differential-Drive Locomotion", level=2)
    add_body(
        doc,
        "Differential drive is the most common locomotion scheme in low-cost robotics. Two "
        "wheels on a common axis are driven independently; a caster or skid supports the "
        "third point. The forward velocity and yaw rate are determined by the left and right "
        "wheel speeds. The scheme is mechanically simple and allows zero-radius rotation, "
        "which is valuable in tight indoor spaces. Its weaknesses are wheel slip, surface "
        "dependence, and the absence of a direct heading measurement unless an IMU or "
        "encoders are added.",
    )
    add_body(
        doc,
        "The classic treatment by Siegwart, Nourbakhsh, and Scaramuzza provides the kinematic "
        "model used in Chapter 9. For a wheel radius r, wheelbase L, and wheel angular speeds "
        "omega_L and omega_R, the linear velocity is v = r(omega_L + omega_R)/2 and the yaw "
        "rate is omega = r(omega_R - omega_L)/L. These equations are exact only when the "
        "wheels do not slip; in practice the rover uses visual feedback to compensate for the "
        "difference between the ideal and the real motion.",
    )
    add_figure(
        doc,
        assets["d_diff"],
        "Differential-drive geometry and the relationship between wheel speeds, linear "
        "velocity, and yaw rate.",
    )

    doc.add_heading("3.2 Visual Servoing", level=2)
    add_body(
        doc,
        "Visual servoing uses feedback from a camera to control a robot's motion. In "
        "image-based visual servoing, the control error is defined directly in image "
        "coordinates, for example the horizontal distance between the target centroid and the "
        "image centre. This avoids the need for a calibrated 3D model of the scene and is "
        "well suited to a low-cost monocular camera. The price is that depth is not directly "
        "observed; the controller must rely on apparent size or on an auxiliary range sensor.",
    )
    add_body(
        doc,
        "The rover uses a simple image-based policy. The frame is divided into left, centre, "
        "and right zones. If the target centroid lies in the left zone, the rover turns left; "
        "if it lies in the right zone, it turns right; if it lies in the centre zone, it moves "
        "forward. A deadband around the centre reduces oscillation. The policy is deliberately "
        "coarse, because a coarse policy is easier to test and safer than a finely tuned "
        "controller that chatters when the detector is noisy.",
    )
    add_figure(
        doc,
        assets["d_zones"],
        "Three-zone image partitioning with a centre deadband used by the steering policy.",
    )

    doc.add_heading("3.3 Object Detection on the Edge", level=2)
    add_body(
        doc,
        "The YOLO family, introduced by Redmon et al., reframed object detection as a single "
        "regression problem and made real-time detection practical on commodity hardware. "
        "Later YOLO versions improved accuracy and efficiency through better backbones, "
        "feature pyramids, and training strategies. Transformer-based detectors such as DETR "
        "and RT-DETR removed the need for hand-designed anchors and non-maximum suppression, "
        "but their computational cost is higher, especially on CPU-only hosts.",
    )
    add_body(
        doc,
        "For a microcontroller, even a small YOLO model is too large to run comfortably. The "
        "TinyML community addresses this with quantization, pruning, and specialised "
        "architectures such as FOMO, but these methods require a training pipeline and a "
        "carefully curated dataset. This project takes a pragmatic approach: the detector "
        "runs on the host laptop, where a full YOLO model can be executed at a usable frame "
        "rate, while the rover keeps only the safety-critical logic on the microcontroller. "
        "The trade-off is accepted because the project is a prototype, not a product.",
    )
    add_body(
        doc,
        "The detector comparison in Chapter 10 is important because it shows that the largest "
        "or most accurate model is not automatically the right choice. RT-DETRv2-R18 achieved "
        "the highest recall and mAP, but its median latency was 3.4 s per frame, which breaks "
        "the 1 s control budget. The selected YOLO11s model was the most accurate model that "
        "still closed the loop.",
    )

    doc.add_heading("3.4 Motor Drivers and Power Electronics", level=2)
    add_body(
        doc,
        "A DC gear motor cannot be driven directly from a microcontroller pin. An H-bridge "
        "is required to reverse the polarity and to modulate the average voltage with PWM. "
        "The L298N is a widely used bipolar H-bridge that is inexpensive and tolerant, but "
        "its internal Darlington output stage drops roughly 1.8 V to 3.2 V, which turns into "
        "heat and reduces the voltage available to the motor. MOSFET-based drivers such as "
        "the TB6612FNG have a much lower on-resistance and run cooler.",
    )
    add_body(
        doc,
        "The original design used the L298N because it was available in the laboratory and "
        "because its behaviour is well documented. After the 26 October incident, the rover "
        "was rebuilt with a TB6612FNG. The change reduced the driver's voltage drop and "
        "thermal load, and it made the wiring more compact. The trade-off is that the "
        "TB6612FNG has a lower absolute maximum voltage and requires a logic supply and a "
        "standby pin, so the wiring and firmware pin map had to be revised.",
    )
    add_table(
        doc,
        ["Property", "L298N (baseline)", "TB6612FNG (final)"],
        [
            ["Output stage", "Bipolar Darlington", "MOSFET"],
            ["Typical voltage drop", "1.8 V - 3.2 V", "< 0.2 V"],
            [
                "Continuous current",
                "2 A per channel (with heatsink)",
                "1.2 A per channel",
            ],
            ["Logic supply", "5 V onboard regulator", "2.7 V - 5.5 V VCC"],
            ["Standby control", "None", "STBY pin"],
            ["Thermal behaviour", "Requires heatsink", "Runs cool at rover currents"],
            ["Footprint", "Large red module", "Compact breakout"],
        ],
        widths=[1.7, 2.3, 2.1],
        caption="Comparison of the baseline L298N and the final TB6612FNG motor driver.",
        font_size=8.6,
    )

    doc.add_heading("3.5 Safety Architectures for Small Robots", level=2)
    add_body(
        doc,
        "Safety in small robots is often treated as a software feature: a check inside the "
        "main loop. A more robust approach is to give safety its own layer with the authority "
        "to override every other command. The rover follows this principle. The Arduino "
        "firmware checks the obstacle distance and the communication watchdog before it "
        "applies any motor command. The host software also checks the camera health and the "
        "serial link, but the host is not trusted to be the last line of defence.",
    )
    add_body(
        doc,
        "This layering is inspired by the fail-safe principle used in industrial control: "
        "the absence of a valid signal must produce a safe state, not a continuation of the "
        "last command. The rover's safe state is STOP, with the motor driver disabled. The "
        "same principle appears in the FMEA in Chapter 9 and in the incident analysis in "
        "Chapter 11.",
    )

    doc.add_heading("3.6 Gap Addressed by This Project", level=2)
    add_body(
        doc,
        "The literature offers excellent treatments of each individual subsystem, but "
        "relatively few accessible accounts show how the pieces are integrated on a student "
        "budget, including the wiring, the power isolation, the test evidence, and the "
        "failures. This project contributes a complete, reproducible build narrative: a "
        "photo-dated record of the mechanical assembly, a measured detector comparison, a "
        "layered safety design, and an honest case study of a battery short circuit and its "
        "recovery. The contribution is therefore as much methodological as technical.",
    )


def chapter_architecture(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 4", "System Architecture")
    add_body(
        doc,
        "The rover is organised as three cooperating tiers. The first tier is the ESP32-CAM, "
        "which captures video and serves it over Wi-Fi. The second tier is the host laptop, "
        "which runs the detector, the decision engine, the safety manager, the dashboard, and "
        "the logger. The third tier is the Arduino UNO, which owns the motors, the ultrasonic "
        "sensor, and the hard real-time safety interlocks. The tiers are deliberately "
        "asymmetric: the laptop may be slow or disconnected, but the Arduino must always be "
        "able to stop the rover.",
    )

    doc.add_heading("4.1 Tier Responsibilities", level=2)
    add_table(
        doc,
        ["Tier", "Hardware / software", "Responsibility", "Failure behaviour"],
        [
            [
                "1",
                "ESP32-CAM (AI-Thinker, OV2640)",
                "Capture VGA frames, serve MJPEG over Wi-Fi, auto-reconnect.",
                "Video stops; host sends STOP.",
            ],
            [
                "2",
                "Laptop host (Python)",
                "Detect target, compute error, choose command, log events, display dashboard.",
                "Host stops sending; Arduino watchdog stops motors.",
            ],
            [
                "3",
                "Arduino UNO R3",
                "Validate command, read HC-SR04, enforce 15 cm gate and 3 s watchdog, drive TB6612FNG.",
                "Motors disabled; safe state.",
            ],
        ],
        widths=[0.5, 1.8, 2.8, 1.6],
        caption="Responsibility and failure behaviour of the three tiers.",
        font_size=8.5,
    )

    doc.add_heading("4.2 End-to-End Data Flow", level=2)
    add_body(
        doc,
        "Every frame follows the same five-step loop, repeated roughly five to ten times per "
        "second depending on the host load. The steps are SEE, UNDERSTAND, DECIDE, ACT, and "
        "PROTECT. The loop is intentionally simple so that each step can be tested in "
        "isolation and so that a failure at any step has a defined safe outcome.",
    )
    add_numbered(
        doc,
        [
            "SEE: the ESP32-CAM captures an OV2640 frame and serves it as MJPEG. The host pulls "
            "the stream and stores the latest frame.",
            "UNDERSTAND: the detector returns a bounding box for the target class. The box centre "
            "is compared with the frame centre to produce a horizontal error.",
            "DECIDE: the steering policy maps the error to a zone and selects F, L, R, or S. The "
            "safety manager can veto the decision.",
            "ACT: the approved one-character command is sent over USB serial to the Arduino.",
            "PROTECT: the Arduino re-checks the command, the obstacle distance, and the watchdog "
            "before it enables the motor driver.",
        ],
    )
    add_figure(
        doc,
        assets["d_flow"],
        "End-to-end data flow from photons to wheel torque, with the safety veto applied "
        "before actuation.",
    )

    doc.add_heading("4.3 Hardware Interconnection", level=2)
    add_body(
        doc,
        "The hardware interconnection is deliberately sparse. The ESP32-CAM receives 5 V and "
        "ground from the buck converter and nothing else. Video leaves it as Wi-Fi MJPEG. The "
        "laptop connects to the Arduino with a USB cable, which carries both the command "
        "stream and the telemetry. The Arduino connects to the TB6612FNG with six control "
        "lines (PWMA, AIN1, AIN2, BIN1, BIN2, PWMB) plus STBY, and to the HC-SR04 with TRIG "
        "and ECHO. The motor driver connects to the two TT motors and to the 7.4 V battery "
        "rail. All grounds meet at a single star point.",
    )
    add_figure(
        doc,
        assets["d_hw"],
        "Hardware subsystem interconnection and signal topology.",
    )
    add_body(
        doc,
        "The absence of a data wire between the ESP32 and the Arduino is a deliberate safety "
        "decision. The ESP32 is a 3.3 V device, while the Arduino is a 5 V device. A direct "
        "UART connection would expose the ESP32 to 5 V on its GPIO pins, which can destroy "
        "the pin or the chip. A level shifter could solve the electrical problem, but it "
        "would add another component and another failure point. Since the laptop already has "
        "a USB link to the Arduino, the ESP32 does not need a wired data path. The design "
        "therefore keeps the ESP32 power-only.",
    )
    add_callout(
        doc,
        "Why the ESP32 is power-only",
        "The ESP32-CAM has no data wire to the Arduino. Video travels over Wi-Fi to the "
        "laptop, and commands travel from the laptop to the Arduino over USB serial. This "
        "avoids a 5 V-to-3.3 V level-shift hazard and keeps the camera's power noise away "
        "from the motor controller. If a wired UART is ever added, a level shifter is "
        "mandatory.",
    )

    doc.add_heading("4.4 Design Rationale", level=2)
    add_body(
        doc,
        "The architecture is a response to three constraints: compute, safety, and cost. "
        "Compute is concentrated on the laptop because that is where a full YOLO model can "
        "run. Safety is concentrated on the Arduino because a small, single-purpose firmware "
        "is easier to audit than a large Python process. Cost is kept low by using commodity "
        "modules and by avoiding a single-board computer on the rover. The result is not the "
        "most compact design possible, but it is one of the easiest to understand, test, and "
        "repair.",
    )
    add_body(
        doc,
        "The split also makes the failure modes easier to reason about. If the Wi-Fi link "
        "drops, the host sees a stale frame and sends STOP; if the host itself dies, the "
        "Arduino watchdog stops the motors; if the Arduino loses power, the motor driver is "
        "disabled. There is no state in which silence means \u201ckeep driving\u201d. This "
        "property is the most important architectural achievement of the project.",
    )

    doc.add_heading("4.5 Operating Modes", level=2)
    add_table(
        doc,
        ["Mode", "Purpose", "Hardware required", "Safety behaviour"],
        [
            [
                "Observe",
                "Track a target and log decisions without autonomous motion.",
                "Camera + optional Arduino",
                "STOP on stale frame or low confidence.",
            ],
            [
                "Search",
                "Rotate or scan to reacquire a lost target.",
                "Camera + Arduino",
                "STOP if no target after the search timeout.",
            ],
            [
                "Scan 360",
                "Discrete panoramic scan using a servo or timed rotation.",
                "Camera + servo (optional)",
                "STOP between scan steps.",
            ],
            [
                "Manual",
                "Operator sends F/B/L/R/S directly.",
                "Arduino + serial link",
                "Obstacle gate and watchdog remain active.",
            ],
            [
                "Mock",
                "Run the full host pipeline without hardware.",
                "Laptop only",
                "No actuation; deterministic test data.",
            ],
        ],
        widths=[0.8, 2.0, 1.8, 2.1],
        caption="Operating modes and their safety behaviour.",
        font_size=8.5,
    )
    add_figure(
        doc,
        assets["d_block"],
        "Complete rover block diagram showing the three tiers, power rails, and signal paths.",
    )


def chapter_components(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 5", "Component Selection and Hardware Inventory")
    add_body(
        doc,
        "Every component in the rover had to justify its place. The selection criteria were "
        "cost, availability in the laboratory, ease of replacement, and compatibility with "
        "the three-tier architecture. This chapter records what was chosen, what was rejected, "
        "and why. The photographs are the original component images, taken before assembly, "
        "and they are used here as the primary record of the parts that were actually on the "
        "bench.",
    )

    doc.add_heading("5.1 Selection Criteria", level=2)
    add_body(
        doc,
        "The rover is a student prototype, so the selection process was driven by what could "
        "be sourced quickly and repaired easily. A component was preferred if it used a "
        "standard interface (USB, UART, PWM, or a 0.1-inch header), if it could be replaced "
        "without resoldering the whole harness, and if its failure mode was predictable. "
        "Components that required a custom PCB, a proprietary toolchain, or a long delivery "
        "time were rejected even when their specifications were better.",
    )
    add_table(
        doc,
        ["Criterion", "Weight", "What it meant in practice"],
        [
            [
                "Safety",
                "High",
                "The part must fail in a predictable, preferably open, state.",
            ],
            [
                "Availability",
                "High",
                "The part must be in the lab or deliverable within days.",
            ],
            ["Cost", "Medium", "The complete prototype should stay below USD 70."],
            [
                "Interface simplicity",
                "Medium",
                "0.1-inch headers and standard serial buses preferred.",
            ],
            [
                "Replaceability",
                "Medium",
                "A failed module should be swappable with a screwdriver.",
            ],
            [
                "Performance",
                "Medium",
                "Adequate for indoor, low-speed, single-target operation.",
            ],
        ],
        widths=[1.5, 0.7, 3.9],
        caption="Component selection criteria and their relative importance.",
        font_size=8.6,
    )

    doc.add_heading("5.2 Compute and Vision", level=2)
    add_body(
        doc,
        "The vision tier uses an AI-Thinker ESP32-CAM with an OV2640 sensor. The module "
        "combines a 240 MHz dual-core ESP32, 520 KB of SRAM, 4 MB of flash, a microSD slot, "
        "and a 2 MP camera on a small PCB. It is inexpensive and widely documented, and it "
        "can serve an MJPEG stream over Wi-Fi without any additional hardware. Its limitations "
        "are equally important: it has no USB-serial bridge on the camera board, so flashing "
        "requires a baseboard or a jumper sequence, and its 3.3 V logic is not compatible with "
        "the Arduino's 5 V logic.",
    )
    add_figure(
        doc,
        assets["esp32_front"],
        "ESP32-CAM module with the OV2640 camera and microSD slot.",
    )
    add_body(
        doc,
        "A separate HW-818 ESP32-S DevKit was used during development for serial monitoring "
        "and for testing Wi-Fi behaviour. It is not part of the final rover; it served as a "
        "known-good reference when the camera board behaved unexpectedly. Keeping a second "
        "ESP32 on the bench is a practical debugging strategy: it lets the developer separate "
        "a firmware problem from a hardware problem.",
    )
    add_figure(
        doc,
        assets["esp32_back"],
        "HW-818 ESP32-S DevKit used as a bench reference board.",
    )
    add_figure(
        doc, assets["esp32_usb"], "ESP32-CAM on its micro-USB programming baseboard."
    )

    doc.add_heading("5.3 Motion and Actuation", level=2)
    add_body(
        doc,
        "The drivetrain uses two yellow TT DC gear motors. Each motor integrates a plastic "
        "gearbox with a high reduction ratio, which trades speed for torque and makes the "
        "rover controllable at low PWM values. The motors are inexpensive, widely available, "
        "and mechanically compatible with the acrylic chassis and the rubber tread wheels. "
        "Their weaknesses are plastic gears, no encoders, and a wide unit-to-unit variation in "
        "speed for the same PWM command.",
    )
    add_figure(
        doc, assets["motor"], "TT DC gear motor used for the left and right wheels."
    )
    add_body(
        doc,
        "The baseline motor driver was an L298N dual H-bridge. It is robust and forgiving, "
        "and it was available in the laboratory. However, its Darlington output stage drops a "
        "significant voltage, which reduces the motor speed and produces heat. After the 26 "
        "October incident, the rover was rebuilt with a TB6612FNG MOSFET driver, which has a "
        "much lower voltage drop and runs cooler. Both drivers were photographed so the "
        "change is documented rather than hidden.",
    )
    add_figure(
        doc,
        assets["tb_top"],
        "TB6612FNG dual H-bridge module adopted after the incident.",
    )
    add_figure(
        doc, assets["tb_pinout"], "TB6612FNG pinout used to revise the wiring harness."
    )

    doc.add_heading("5.4 Power", level=2)
    add_body(
        doc,
        "The rover is powered by a 2S 18650 lithium-ion pack with a nominal voltage of 7.4 V. "
        "The pack feeds the motor driver directly and feeds an LM2596 buck converter, which "
        "produces a regulated 5 V rail for the Arduino, the ESP32-CAM, and the ultrasonic "
        "sensor. The LM2596 is a switching regulator, so it is more efficient than a linear "
        "regulator, but it requires careful adjustment before connection. The output voltage "
        "must be set to 5.0 V with a multimeter before any logic board is attached.",
    )
    add_figure(doc, assets["power"], "2S 18650 battery pack and LM2596 buck converter.")
    add_callout(
        doc,
        "Set the buck before you connect it",
        "The LM2596 output is adjusted with a small potentiometer. Connect the battery to the "
        "input, measure the output with a multimeter, and turn the potentiometer until the "
        "output reads 5.0 V. Only then connect the Arduino and the ESP32-CAM. A mis-set buck "
        "can destroy both boards in less than a second.",
        fill="FFF4E5",
        border=AMBER,
    )

    doc.add_heading("5.5 Sensing", level=2)
    add_body(
        doc,
        "The HC-SR04 ultrasonic sensor provides a short-range forward obstacle gate. It "
        "measures distance by timing the echo of a 40 kHz burst, and it interfaces with two "
        "digital pins (TRIG and ECHO). It is cheap, simple, and adequate for a 15 cm stop "
        "threshold. It is not a precision instrument: its cone is narrow, it can miss soft or "
        "angled surfaces, and its readings become unreliable beyond about 2 m. The rover uses "
        "it as a safety gate, not as a mapping sensor.",
    )
    add_figure(
        doc, assets["ultra_bracket"], "HC-SR04 with the acrylic mounting bracket."
    )
    add_figure(doc, assets["ultra_detail"], "Close-up of the HC-SR04 transducer.")
    add_figure(doc, assets["ultra_pinout"], "HC-SR04 pinout and DuPont connections.")

    doc.add_heading("5.6 Control", level=2)
    add_body(
        doc,
        "The Arduino UNO R3 is the safety supervisor. It was chosen because it is ubiquitous, "
        "5 V tolerant, easy to audit, and supported by a mature toolchain. It has enough "
        "digital pins for the motor driver, the ultrasonic sensor, and a serial link, and its "
        "analog inputs are available for future current sensing. Its limitations are a 16 MHz "
        "clock, 2 KB of SRAM, and no floating-point accelerator, but none of these matter for "
        "the small safety firmware.",
    )
    add_figure(
        doc,
        assets["arduino"],
        "Arduino UNO R3 with the serial and control jumpers attached.",
    )

    doc.add_heading("5.7 Bill of Materials Summary", level=2)
    add_body(
        doc,
        "The complete bill of materials is given in Appendix A. The prototype cost is "
        "dominated by the ESP32-CAM, the battery pack, and the motor driver. The chassis, "
        "fasteners, and wiring are low-cost consumables. The rover was built from parts that "
        "were already in the laboratory plus a small number of purchases, which is typical of "
        "a student project and is one reason the design emphasizes replaceability.",
    )
    add_table(
        doc,
        ["Subsystem", "Key part", "Quantity", "Role"],
        [
            ["Vision", "ESP32-CAM (OV2640)", "1", "Wi-Fi video stream"],
            ["Control", "Arduino UNO R3", "1", "Safety supervisor and motor control"],
            ["Drive", "TT DC gear motor", "2", "Differential propulsion"],
            ["Driver", "TB6612FNG (final)", "1", "Dual H-bridge"],
            ["Ranging", "HC-SR04", "1", "Forward obstacle gate"],
            ["Power", "2S 18650 pack", "1", "7.4 V main rail"],
            ["Power", "LM2596 buck", "1", "5 V logic rail"],
            ["Chassis", "Acrylic plates + caster", "1 set", "Structural base"],
            ["Wiring", "Dupont / soldered harness", "1 set", "Power and signals"],
        ],
        widths=[1.1, 2.0, 0.8, 2.2],
        caption="Subsystem-level bill of materials summary.",
        font_size=8.6,
    )


def chapter_build(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 6", "Chronological Build Log")
    add_body(
        doc,
        "This chapter is the heart of the report. It follows the build in the order in which "
        "it happened, using the dates embedded in the original photograph filenames. The "
        "narrative is deliberately concrete: it records what was bolted, soldered, flashed, "
        "and measured on each day, and it notes the problems that appeared. Where a photograph "
        "was taken at a known time, the time is included; otherwise only the date is claimed.",
    )
    add_figure(
        doc,
        assets["c_timeline"],
        "Photo-documented build timeline for October 2026. The red marker is the short-circuit "
        "day.",
    )

    doc.add_heading("6.1 3 October 2026: The Sensor Arrives", level=2)
    add_body(
        doc,
        "The first dated artefact is the HC-SR04 kit, photographed on 3 October 2026. The "
        "package contained the sensor, an acrylic bracket, and a rainbow ribbon cable. Laying "
        "the parts out before assembly was useful: it confirmed that the bracket matched the "
        "sensor's mounting holes and that the cable was long enough to reach the front of the "
        "chassis. The kit set the physical scale for the rest of the build.",
    )
    add_figure(
        doc,
        assets["ultra_bracket"],
        "3 October 2026: the HC-SR04 kit laid out before assembly.",
    )

    doc.add_heading("6.2 6 October 2026: A Rolling Chassis", level=2)
    add_body(
        doc,
        "The chassis was assembled on 6 October. The first step was to bolt the battery holder "
        "and the rocker switch to the lower acrylic plate. The holder was positioned toward "
        "the rear so that the heavier cells would sit over the drive wheels, and the switch was "
        "placed where a finger could reach it without lifting the rover. The switch is a "
        "single-pole single-throw rocker rated for the pack current; it is the only way to "
        "remove power from the entire system.",
    )
    add_figure(
        doc,
        assets["asm01"],
        "6 October 2026: battery holder and rocker switch on the lower plate.",
    )
    add_body(
        doc,
        "The two TT motors were then secured to the underside of the plate with acrylic "
        "T-brackets and machine screws. The brackets were aligned by eye and tightened "
        "gradually, alternating sides so that the plate would not warp. The motor shafts must "
        "be parallel; if one motor is skewed, the rover will curve even when both wheels are "
        "commanded to the same speed. This is a mechanical problem that no amount of software "
        "can fully correct.",
    )
    add_figure(
        doc,
        assets["asm02"],
        "6 October 2026: dual TT motors mounted under the chassis.",
    )
    add_body(
        doc,
        "The rubber tread wheels were pressed onto the motor axles, and the front caster was "
        "bolted to the plate. The caster provides the third support point and allows the rover "
        "to rotate about its own centre. With the wheels and caster in place, the chassis could "
        "roll freely on the bench. The top view shows that the wheel track is wider than the "
        "battery holder, which gives the rover a low centre of gravity and good resistance to "
        "tipping during turns.",
    )
    add_figure(doc, assets["asm03"], "6 October 2026: wheels and front caster mounted.")
    add_figure(
        doc, assets["asm04"], "6 October 2026: the completed rolling base, top view."
    )

    doc.add_heading("6.3 9 October 2026: Mounting the Ultrasonic Sensor", level=2)
    add_body(
        doc,
        "The HC-SR04 was mounted on 9 October at the end of the chassis, using the acrylic "
        "bracket from the kit. The sensor faces forward and slightly upward, which reduces "
        "false echoes from the floor. The motor leads were routed along the side of the plate "
        "and secured with tape so that they would not be caught by the wheels. The bracket is "
        "rigid enough that the sensor does not vibrate during motion, which matters because a "
        "vibrating sensor produces erratic distance readings.",
    )
    add_figure(
        doc,
        assets["asm05"],
        "9 October 2026: HC-SR04 mounted at the front of the chassis.",
    )
    add_figure(
        doc,
        assets["asm06"],
        "9 October 2026: detail of the ultrasonic bracket alignment.",
    )

    doc.add_heading(
        "6.4 19 October 2026: Bench Wiring and the First Live Detection", level=2
    )
    add_body(
        doc,
        "The bench session on 19 October was the first time the electronics were connected "
        "outside the chassis. The power bank, Arduino UNO, ESP32, and ultrasonic sensor were "
        "laid out on the bench and wired one subsystem at a time. The purpose was to verify "
        "each connection before it was buried in the chassis. The photograph shows the "
        "characteristic mess of a first integration: long jumper wires, an exposed buck "
        "converter, and a laptop close enough to yank the USB cable.",
    )
    add_figure(
        doc,
        assets["asm07"],
        "19 October 2026: off-board bench wiring and first integration test.",
    )
    add_body(
        doc,
        "Later that evening, at 21:23, the Arduino was photographed with its serial and "
        "control jumpers attached. At 21:36 and 21:37, the host laptop was running a live YOLO "
        "session on an IP Webcam feed and the MissionPilot dashboard. The dashboard showed the "
        "annotated frame, the detected target, and the command state. This was the first "
        "end-to-end perception run, even though the rover was not yet driving.",
    )
    add_figure(
        doc,
        assets["arduino"],
        "19 October 2026, 21:23: Arduino UNO with control jumpers.",
    )
    add_figure(
        doc,
        assets["yolo"],
        "19 October 2026, 21:36: live YOLO tracking on an IP Webcam feed.",
    )
    add_figure(
        doc,
        assets["dashboard"],
        "19 October 2026, 21:37: MissionPilot dashboard and host terminal.",
    )
    add_body(
        doc,
        "The dry-fit placement on the chassis was done the same day. The Arduino, ESP32, and "
        "power bank were arranged on the top deck to check that they would fit and that the "
        "camera had a clear forward view. The layout was not final; it was a physical "
        "feasibility check. The photograph shows that the top deck was already crowded, which "
        "motivated the two-tier stack built the next day.",
    )
    add_figure(
        doc,
        assets["asm08"],
        "19 October 2026: dry-fit of the electronics on the chassis top deck.",
    )

    doc.add_heading("6.5 20 October 2026: The Two-Tier Stack", level=2)
    add_body(
        doc,
        "The two-tier stack was assembled on 20 October. The lower tier holds the Arduino and "
        "the wiring; the upper tier holds the power bank and the ESP32. Separating the power "
        "bank from the logic boards reduced the mechanical load on the lower deck and made the "
        "camera height more usable. The side view shows the gap between the tiers, which allows "
        "air to circulate and keeps the buck converter away from the Arduino.",
    )
    add_figure(doc, assets["asm09"], "20 October 2026: two-tier prototype, side view.")
    add_figure(doc, assets["asm10"], "20 October 2026: two-tier prototype, top view.")
    add_body(
        doc,
        "The underside wiring was routed through the chassis slots on the same day. The goal "
        "was to keep the motor and battery leads away from the wheels and away from the signal "
        "wires. The photograph shows the first attempt at strain relief: the leads are taped "
        "to the plate, but the battery terminals are still exposed. That detail became "
        "important six days later.",
    )
    add_figure(
        doc,
        assets["asm11"],
        "20 October 2026: underside wire routing through the chassis slots.",
    )

    doc.add_heading("6.6 22 October 2026: The Wi-Fi Stream", level=2)
    add_body(
        doc,
        "On 22 October, at 20:08, the ESP32-CAM was tested as a standalone access point. The "
        "phone connected to the `ESP32-CAM` network and opened `http://192.168.4.1:81/stream`. "
        "The first screenshot shows a normal indoor scene; the second shows the same scene in "
        "low light. The low-light test was important because the detector's performance depends "
        "on contrast, and the OV2640 has no infrared illumination.",
    )
    add_figure(
        doc,
        assets["wifi1"],
        "22 October 2026, 20:08:20: MJPEG stream viewed on a phone.",
    )
    add_figure(
        doc, assets["wifi2"], "22 October 2026, 20:08:48: low-light stream calibration."
    )
    add_body(
        doc,
        "The stream worked, but the test also revealed two practical issues. First, the camera "
        "board reset when the phone moved too far from the access point, which confirmed that "
        "the Wi-Fi link is a real failure mode and justified the host-side stale-frame check. "
        "Second, the image was noticeably darker at the edges, which is typical of the OV2640 "
        "lens and which the detector tolerates but does not fully compensate for.",
    )

    doc.add_heading("6.7 23 October 2026: Insulated Joints", level=2)
    add_body(
        doc,
        "The motor harness was rebuilt on 23 October. The soldered terminals were wrapped with "
        "insulating tape, and the joints were pulled gently to check that they would not fail "
        "under vibration. This was a response to an earlier intermittent fault in which one "
        "motor would stop when the rover crossed a bump. The photograph shows the taped joints "
        "and the routing along the chassis edge.",
    )
    add_figure(
        doc,
        assets["asm12"],
        "23 October 2026: motor harness with insulated soldered joints.",
    )

    doc.add_heading(
        "6.8 26 October 2026: Driver Upgrade and the Short Circuit", level=2
    )
    add_body(
        doc,
        "The TB6612FNG driver was photographed at 19:08 and 19:09 on 26 October, before it was "
        "installed. The upgrade was planned because the L298N was running hot and dropping too "
        "much voltage. The TB6612FNG is smaller, cooler, and better suited to the rover's "
        "current draw. The pinout photograph was taken specifically so that the new wiring "
        "could be checked against the board markings rather than against memory.",
    )
    add_figure(
        doc,
        assets["tb_top"],
        "26 October 2026, 19:08:57: TB6612FNG before installation.",
    )
    add_figure(
        doc,
        assets["tb_pinout"],
        "26 October 2026, 19:09:04: TB6612FNG pinout reference.",
    )
    add_body(
        doc,
        "At 20:14, during the power integration, the positive battery terminal touched the "
        "grounded chassis while the pack was connected. The contact produced a short circuit. "
        "The terminal lug and the compression spring were damaged, and a small number of "
        "components on the power path were affected. The rover was powered down immediately, "
        "the pack was removed, and the bench was cleared. Chapter 11 analyses the event in "
        "detail; here it is enough to record that the build stopped for the evening and that "
        "the recovery changed the power architecture.",
    )
    add_figure(
        doc,
        assets["asm13"],
        "26 October 2026, after 20:14: damaged battery terminal and spring after the short "
        "circuit.",
    )
    add_body(
        doc,
        "The photograph of the damaged terminal is included deliberately. It is evidence of "
        "what went wrong, and it is the starting point for the corrective actions: heat-shrink "
        "over the lug, a fused positive lead, a strain-relieved battery holder, and a pre-power "
        "checklist. The incident did not end the project; it changed the project's standards.",
    )

    doc.add_heading("6.9 Build Summary", level=2)
    add_table(
        doc,
        ["Date", "Stage", "Evidence", "Outcome"],
        [
            ["3 Oct 2026", "HC-SR04 kit received", "Component photo", "Parts verified"],
            [
                "6 Oct 2026",
                "Chassis, motors, wheels, caster",
                "Assembly photos 01-04",
                "Rolling base",
            ],
            [
                "9 Oct 2026",
                "Ultrasonic mount",
                "Assembly photos 05-06",
                "Forward sensor fixed",
            ],
            [
                "19 Oct 2026",
                "Bench wiring, YOLO, dashboard",
                "Photos 07-08, telemetry",
                "First live detection",
            ],
            [
                "20 Oct 2026",
                "Two-tier stack, underside routing",
                "Photos 09-11",
                "Electronics packaged",
            ],
            [
                "22 Oct 2026",
                "ESP32-CAM Wi-Fi stream",
                "Phone screenshots",
                "Video link verified",
            ],
            [
                "23 Oct 2026",
                "Insulated motor joints",
                "Photo 12",
                "Intermittent fault reduced",
            ],
            [
                "26 Oct 2026",
                "TB6612FNG upgrade; short circuit",
                "Photos 13, driver photos",
                "Recovery and redesign",
            ],
        ],
        widths=[0.95, 2.1, 1.55, 1.5],
        caption="Build stages, dates, evidence, and outcomes.",
        font_size=8.2,
    )


def chapter_power(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 7", "Power Architecture and Wiring")
    add_body(
        doc,
        "Power is the part of a small robot that is easiest to underestimate. A rover can "
        "appear to work on the bench and then reset violently the moment both motors start, "
        "because the motor current collapses the logic rail. The rover avoids this by keeping "
        "the motor rail and the logic rail separate, by using a switching buck converter for "
        "the logic, and by bringing every ground back to a single star point. This chapter "
        "explains the electrical chain and the reasoning behind each connection.",
    )

    doc.add_heading("7.1 Power Rails", level=2)
    add_body(
        doc,
        "There are two electrical domains on the rover. The high-current domain is the 2S "
        "battery rail, which ranges from about 6.0 V (discharged) to 8.4 V (fully charged) and "
        "feeds the motor driver directly. The low-current domain is the regulated 5 V rail, "
        "which feeds the Arduino, the ESP32-CAM, and the HC-SR04. The two domains share a "
        "common ground but not a common supply. This separation is the single most important "
        "electrical decision in the build.",
    )
    add_table(
        doc,
        ["Rail", "Source", "Nominal", "Loads", "Protection"],
        [
            [
                "VM (motor)",
                "2S 18650 pack",
                "7.4 V",
                "TB6612FNG VM, motors",
                "3 A inline fuse, switch",
            ],
            [
                "5 V (logic)",
                "LM2596 buck",
                "5.0 V",
                "Arduino, ESP32-CAM, HC-SR04",
                "Buck current limit, decoupling",
            ],
            [
                "3.3 V (camera)",
                "ESP32-CAM onboard LDO",
                "3.3 V",
                "OV2640, ESP32 core",
                "Onboard regulator",
            ],
            ["GND", "Star junction", "0 V", "All modules", "Single-point return"],
        ],
        widths=[1.1, 1.5, 0.8, 2.2, 1.8],
        caption="Power rails, sources, loads, and protection.",
        font_size=8.4,
    )
    add_figure(
        doc,
        assets["d_power"],
        "Power distribution from the 2S pack to the motor and logic rails.",
    )

    doc.add_heading("7.2 Why a Star Ground", level=2)
    add_body(
        doc,
        "A star ground is a wiring topology in which every module's ground returns to one "
        "physical point rather than daisy-chaining through other modules. The reason is "
        "current. The motor return current can be several hundred milliamps, and the resistance "
        "of a long jumper wire is not zero. If the Arduino ground is connected downstream of "
        "the motor ground, the motor current produces a small voltage drop in the shared wire, "
        "and the Arduino sees a ground that is not at 0 V. That offset can corrupt analog "
        "readings, cause serial errors, or reset the board.",
    )
    add_body(
        doc,
        "The rover uses a single star point on the lower chassis plate. The battery negative, "
        "the buck converter input and output grounds, the Arduino ground, the ESP32 ground, the "
        "HC-SR04 ground, and the motor driver ground all meet there. The star point is a "
        "physical terminal, not a loose twist of wires. This makes the ground inspectable and "
        "makes it obvious if a connection has come loose.",
    )
    add_callout(
        doc,
        "Ground rule",
        "Every ground returns to one star point. Never daisy-chain the Arduino ground through "
        "the motor driver. A shared ground wire carrying motor current will lift the logic "
        "ground and cause resets that look like software bugs.",
    )

    doc.add_heading("7.3 Fusing and Switching", level=2)
    add_body(
        doc,
        "The positive battery lead passes through a 3 A inline fuse before the rocker switch. "
        "The fuse is sized above the normal operating current but below the current that the "
        "battery and wiring can safely deliver into a short. The switch isolates the entire "
        "system for assembly and for emergencies. The fuse holder is deliberately placed close "
        "to the battery so that the unprotected length of positive conductor is as short as "
        "possible.",
    )
    add_body(
        doc,
        "The short-circuit incident showed why the physical arrangement matters as much as the "
        "schematic. A fuse that is present but bypassed by a loose terminal does not protect "
        "anything. The corrective action therefore combined the fuse with an insulated terminal, "
        "a strain-relieved holder, and a pre-power checklist. Protection is a system, not a "
        "single component.",
    )

    doc.add_heading("7.4 Power Budget", level=2)
    add_body(
        doc,
        "The following budget is a design estimate. It uses typical rather than worst-case "
        "currents, because the rover is intended for intermittent indoor operation. The "
        "measured runtime has not yet been recorded on the final build; it is marked [PENDING] "
        "and is a task for the next test campaign.",
    )
    add_table(
        doc,
        ["Load", "Typical current", "Duty", "Average", "Notes"],
        [
            [
                "Left TT motor",
                "0.25 A",
                "60%",
                "0.15 A",
                "Higher during turns and stalls",
            ],
            [
                "Right TT motor",
                "0.25 A",
                "60%",
                "0.15 A",
                "Higher during turns and stalls",
            ],
            ["Arduino UNO", "0.05 A", "100%", "0.05 A", "Logic only, no motor load"],
            [
                "ESP32-CAM",
                "0.18 A",
                "100%",
                "0.18 A",
                "Peak higher during Wi-Fi transmit",
            ],
            ["HC-SR04", "0.015 A", "10%", "0.002 A", "Pulsed measurement"],
            ["TB6612FNG logic", "0.01 A", "100%", "0.01 A", "VCC only"],
        ],
        widths=[1.5, 1.1, 0.7, 0.8, 2.6],
        caption="Design power budget for the 5 V and motor rails [DESIGN].",
        font_size=8.4,
    )
    add_body(
        doc,
        "The 5 V load is dominated by the ESP32-CAM, which draws a burst of current during "
        "Wi-Fi transmission. The LM2596 must be able to supply that burst without dropping the "
        "rail below the Arduino's brownout threshold. A 1000 uF electrolytic capacitor across "
        "the 5 V rail near the ESP32 is recommended as a reservoir for the transmit bursts. "
        "The motor rail is dominated by the two TT motors, whose stall current is much higher "
        "than their running current; the fuse and the driver's current rating must be chosen "
        "for the stall case, not the running case.",
    )

    doc.add_heading("7.5 Wiring Schedule", level=2)
    add_body(
        doc,
        "The baseline wiring schedule follows the L298N pin map used in the original firmware. "
        "The final TB6612FNG adapter keeps the same Arduino control pins but renames the "
        "signals and adds a standby connection. The full pin map is given in Appendix B. The "
        "important point is that the pin functions were verified against the firmware, not "
        "copied from a generic tutorial.",
    )
    add_table(
        doc,
        ["Arduino pin", "L298N baseline", "TB6612FNG final", "Function"],
        [
            ["D5", "ENA", "PWMA", "Left motor speed"],
            ["D6", "IN1", "AIN1", "Left motor direction"],
            ["D7", "IN2", "AIN2", "Left motor direction"],
            ["D8", "IN3", "BIN1", "Right motor direction"],
            ["D9", "IN4", "BIN2", "Right motor direction"],
            ["D10", "ENB", "PWMB", "Right motor speed"],
            ["D11", "TRIG", "TRIG", "Ultrasonic trigger"],
            ["D12", "ECHO", "ECHO", "Ultrasonic echo"],
            ["5V", "Logic supply", "VCC + STBY", "Driver logic and enable"],
        ],
        widths=[1.0, 1.4, 1.4, 2.6],
        caption="Arduino control pins for the baseline and final motor drivers.",
        font_size=8.4,
    )
    add_figure(
        doc, assets["d_wiring"], "Detailed wiring diagram for the rover harness."
    )
    add_figure(
        doc,
        assets["d_circuit"],
        "Schematic-level circuit diagram of the rover electronics.",
    )

    doc.add_heading("7.6 Connector and Harness Practice", level=2)
    add_body(
        doc,
        "The harness uses Dupont connectors for logic signals and soldered joints for motor and "
        "battery leads. Dupont connectors are convenient but they pull loose under vibration, "
        "so every logic connector is either taped or routed so that it cannot be pulled by a "
        "wheel. Soldered joints are covered with heat-shrink or insulating tape. The battery "
        "terminal is the most critical joint in the system: it carries the full pack current "
        "and it is the one that failed during the incident.",
    )
    add_bullets(
        doc,
        [
            "Keep the positive battery lead as short as practical and fuse it near the pack.",
            "Strain-relieve every wire that crosses a moving part.",
            "Separate motor leads from signal leads; cross at right angles when unavoidable.",
            "Label both ends of every non-obvious wire before it disappears into the chassis.",
            "Photograph the harness before closing the deck; the photograph is the maintenance manual.",
        ],
    )


def chapter_software(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 8", "Software and AI Pipeline")
    add_body(
        doc,
        "The software is split along the same three tiers as the hardware. The ESP32-CAM runs a "
        "small camera firmware. The laptop runs the perception, decision, dashboard, and logging "
        "stack. The Arduino runs a compact safety and motor firmware. The interfaces between "
        "them are deliberately narrow: MJPEG over Wi-Fi and one-character commands over USB "
        "serial. Narrow interfaces are easier to test and easier to reason about when something "
        "fails.",
    )

    doc.add_heading("8.1 Host Software Architecture", level=2)
    add_body(
        doc,
        "The host is a Python application organised into layers. The capture layer pulls frames "
        "from the ESP32 stream or from a file. The perception layer runs the detector and "
        "returns bounding boxes. The decision layer converts the selected box into a command. "
        "The safety layer checks confidence, distance, and link health before the command is "
        "sent. The transport layer writes the command to the serial port. The presentation "
        "layer draws the dashboard and writes the event log.",
    )
    add_figure(doc, assets["d_esp"], "ESP32-CAM capture and streaming pipeline.")
    add_figure(doc, assets["d_decide"], "Host decision pipeline from frame to command.")
    add_body(
        doc,
        "The layers communicate through plain data structures rather than through shared "
        "mutable state. A frame becomes a detection result; a detection result becomes a "
        "decision; a decision becomes a serial command. This makes it possible to replay a "
        "recorded session through the decision and safety layers without a camera, which is how "
        "most of the regression tests are run.",
    )

    doc.add_heading("8.2 Detection Model", level=2)
    add_body(
        doc,
        "The detector is a YOLO11s model fine-tuned for the target class used in the "
        "demonstration. The model was selected after a comparison of five candidates on the "
        "same 128-image COCO128 evaluation set. The comparison is reported in Chapter 10. The "
        "model runs at a 320-pixel inference size, which is a compromise between accuracy and "
        "latency on the 2-core, 4-thread host CPU.",
    )
    add_body(
        doc,
        "The detector returns boxes with class labels and confidence scores. The decision layer "
        "keeps the highest-confidence box for the configured target class and discards boxes "
        "below a confidence threshold. A temporal filter requires the target to be present for "
        "a small number of consecutive frames before the rover is allowed to move, which "
        "reduces spurious starts caused by a single false positive.",
    )
    add_table(
        doc,
        ["Parameter", "Value", "Reason"],
        [
            ["Input size", "320 x 320", "Meets the 1 s refresh budget on the host CPU"],
            ["Confidence threshold", "0.25", "Balances recall and false positives"],
            ["Target class", "Configured per run", "Single-target demonstration"],
            [
                "Temporal gate",
                "3 consecutive frames",
                "Rejects isolated false positives",
            ],
            ["Colour space", "BGR (OpenCV default)", "Matches the training pipeline"],
            ["NMS IoU", "0.45", "Standard post-processing value"],
        ],
        widths=[1.5, 1.3, 3.2],
        caption="Detector and decision parameters.",
        font_size=8.6,
    )

    doc.add_heading("8.3 Decision Engine", level=2)
    add_body(
        doc,
        "The decision engine is intentionally simple. It computes the horizontal offset between "
        "the target box centre and the frame centre, normalises the offset by the frame width, "
        "and compares it with two thresholds. If the offset is within the centre deadband, the "
        "command is FORWARD. If the target is to the left, the command is LEFT. If it is to the "
        "right, the command is RIGHT. If no target is present, the command is STOP.",
    )
    add_body(
        doc,
        "The deadband is the most important tuning parameter. A narrow deadband makes the rover "
        "track aggressively but oscillate when the detector jitters. A wide deadband makes the "
        "rover stable but slow to correct. The chosen value is a compromise, and it is stored "
        "in configuration rather than hard-coded so that it can be adjusted without editing the "
        "application logic.",
    )
    add_figure(
        doc,
        assets["d_target"],
        "Target position and horizontal error used by the decision engine.",
    )
    add_figure(
        doc,
        assets["d_zones"],
        "Left, centre, and right zones with the centre deadband.",
    )

    doc.add_heading("8.4 Communication Protocol", level=2)
    add_body(
        doc,
        "The host-to-Arduino protocol is deliberately minimal. The host sends one ASCII "
        "character per command: `F` for forward, `B` for backward, `L` for left, `R` for right, "
        "and `S` for stop. The Arduino replies with a short status line. Unknown characters "
        "produce `STATUS:ERROR` and do not actuate the motors. The protocol is small enough to "
        "be implemented correctly on an 8-bit microcontroller and simple enough to be inspected "
        "on a serial terminal.",
    )
    add_table(
        doc,
        ["Direction", "Byte", "Meaning", "Arduino response"],
        [
            ["Host to rover", "F", "Forward", "STATUS:OK,F"],
            ["Host to rover", "B", "Backward", "STATUS:OK,B"],
            ["Host to rover", "L", "Turn left", "STATUS:OK,L"],
            ["Host to rover", "R", "Turn right", "STATUS:OK,R"],
            ["Host to rover", "S", "Stop", "STATUS:OK,S"],
            ["Host to rover", "?", "Query status", "STATUS:<state>,D:<cm>"],
            [
                "Rover to host",
                "TICKS:<l>,<r>",
                "Encoder telemetry",
                "Sent periodically",
            ],
        ],
        widths=[1.3, 1.3, 1.8, 2.4],
        caption="Serial command and telemetry protocol.",
        font_size=8.4,
    )
    add_figure(
        doc,
        assets["d_protocol"],
        "Host-to-Arduino communication protocol and state transitions.",
    )

    doc.add_heading("8.5 ESP32-CAM Firmware", level=2)
    add_body(
        doc,
        "The ESP32-CAM firmware configures the OV2640, starts a Wi-Fi access point or joins an "
        "existing network, and serves the MJPEG stream on port 81. It also exposes a small "
        "control endpoint for changing resolution and frame quality. The firmware is kept "
        "minimal on purpose: every additional feature is another way for the camera to fail, "
        "and the camera is the least reliable part of the system.",
    )
    add_figure(doc, assets["flash"], "Flashing the ESP32-CAM firmware with esptool.")
    add_body(
        doc,
        "The camera board has no USB-serial bridge, so flashing requires either a programming "
        "baseboard or a manual jumper sequence that pulls GPIO0 low at reset. The baseboard is "
        "the safer option because it exposes the correct pins and avoids accidental shorts. The "
        "firmware is flashed at 115200 baud and verified by opening the stream in a browser "
        "before the board is installed on the rover.",
    )

    doc.add_heading("8.6 Arduino Firmware", level=2)
    add_body(
        doc,
        "The Arduino firmware is a small finite-state machine. It reads the serial port, "
        "validates the command, reads the ultrasonic sensor, checks the watchdog, and drives "
        "the motor driver. The loop is non-blocking: the ultrasonic measurement uses a timeout "
        "rather than a long delay, and the serial read returns immediately when no byte is "
        "available. This keeps the watchdog responsive even when the sensor is not returning an "
        "echo.",
    )
    add_figure(doc, assets["d_arduino"], "Arduino safety and motor-control pipeline.")
    add_body(
        doc,
        "The firmware treats every input as untrusted. A command is accepted only if it is one "
        "of the five valid characters. A distance is accepted only if it is within the sensor's "
        "usable range. A communication link is considered alive only if a valid command has "
        "arrived within the last 3 seconds. If any check fails, the motors are stopped and the "
        "driver is disabled.",
    )

    doc.add_heading("8.7 Logging and Reproducibility", level=2)
    add_body(
        doc,
        "Every run writes a CSV event log with the timestamp, frame index, detection count, "
        "selected class, confidence, bounding-box centre, distance, command, safety state, and "
        "inference time. The log is the basis for the evaluation in Chapter 10. It also makes "
        "it possible to replay a run through the decision layer and confirm that the same "
        "inputs produce the same outputs.",
    )
    add_body(
        doc,
        "Configuration is stored in YAML rather than in code. The camera URL, model path, "
        "confidence threshold, deadband, serial port, and safety limits are all configurable. "
        "This matters for reproducibility: a test can be repeated with the exact configuration "
        "that produced the recorded result, and a change can be reviewed as a diff rather than "
        "as an unexplained edit.",
    )


def chapter_control(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 9", "Control Law and Safety Architecture")
    add_body(
        doc,
        "The control law turns a bounding box into wheel motion. The safety architecture "
        "decides whether that motion is allowed. The two are deliberately separated: the "
        "control law may be tuned for smooth tracking, while the safety layer applies hard "
        "limits that no tuning can override. This chapter describes both, and it records the "
        "failure modes that the design is intended to survive.",
    )

    doc.add_heading("9.1 Differential-Drive Kinematics", level=2)
    add_body(
        doc,
        "For a differential-drive robot with wheel radius r, wheelbase L, and wheel angular "
        "speeds omega_L and omega_R, the linear velocity is v = r(omega_L + omega_R)/2 and the "
        "yaw rate is omega = r(omega_R - omega_L)/L. The rover does not measure wheel speed "
        "directly in the baseline build, so the firmware approximates the commanded velocity "
        "with a PWM duty cycle. The approximation is adequate for a low-speed demonstrator, but "
        "it is not a substitute for encoders.",
    )
    add_figure(
        doc, assets["d_diff"], "Differential-drive geometry used by the control law."
    )
    add_body(
        doc,
        "The kinematic model explains why the rover turns in place when the wheels are driven "
        "in opposite directions and why it moves straight when they are driven at equal speeds. "
        "It also explains the main mechanical weakness: if the two motors are not matched, the "
        "rover curves even when the commanded speeds are equal. The visual feedback loop "
        "compensates for this by adjusting the command based on the observed target position.",
    )

    doc.add_heading("9.2 Steering Law", level=2)
    add_body(
        doc,
        "The steering law is a proportional controller with a deadband. The error e is the "
        "normalised horizontal offset between the target centre and the frame centre. The "
        "command is LEFT when e is below the negative threshold, RIGHT when e is above the "
        "positive threshold, and FORWARD when e lies inside the deadband. The output is "
        "discrete because the serial protocol uses single characters, but the underlying "
        "control idea is continuous.",
    )
    add_body(
        doc,
        "A proportional gain Kp scales the turn intensity. A high gain produces a fast response "
        "but can overshoot and oscillate; a low gain is stable but sluggish. The comparison in "
        "the figure below shows the trade-off for three gains. The selected gain is the middle "
        "value, which settles without sustained oscillation on the bench.",
    )
    add_figure(
        doc,
        assets["d_control_resp"],
        "Step response for three proportional gains; the middle gain was selected for the rover.",
    )
    add_figure(
        doc,
        assets["d_control"],
        "Closed-loop control from image error to wheel command.",
    )

    doc.add_heading("9.3 Finite-State Machine", level=2)
    add_body(
        doc,
        "The rover's behaviour is organised as a finite-state machine with five states: IDLE, "
        "SEARCH, TRACK, AVOID, and STOP. The machine starts in IDLE, enters SEARCH when a "
        "mission begins, enters TRACK when a target is confirmed, enters AVOID when the "
        "ultrasonic sensor reports a close obstacle, and enters STOP on a communication loss, "
        "a camera failure, or an explicit stop command. STOP is the only state that disables "
        "the motor driver.",
    )
    add_figure(
        doc, assets["d_fsm"], "Rover finite-state machine and transition conditions."
    )
    add_table(
        doc,
        ["State", "Entry condition", "Allowed motion", "Exit condition"],
        [
            ["IDLE", "Power-on or mission end", "None", "Mission start"],
            ["SEARCH", "No target visible", "Rotate or scan", "Target confirmed"],
            [
                "TRACK",
                "Target confirmed",
                "Forward, left, right",
                "Target lost or obstacle",
            ],
            ["AVOID", "Distance < 15 cm", "Stop, then turn", "Path clear"],
            [
                "STOP",
                "Link loss, camera fault, or explicit stop",
                "None",
                "Operator reset",
            ],
        ],
        widths=[0.9, 2.0, 1.7, 1.8],
        caption="Finite-state machine states and transitions.",
        font_size=8.4,
    )

    doc.add_heading("9.4 Safety Hierarchy", level=2)
    add_body(
        doc,
        "Safety is implemented as a hierarchy of checks, each with the authority to stop the "
        "rover. The first check is in the host: if the camera frame is stale, the host sends "
        "STOP. The second check is in the serial transport: if the Arduino does not receive a "
        "valid command within 3 seconds, it stops the motors. The third check is in the Arduino "
        "loop: if the ultrasonic distance is below 15 cm, forward motion is refused. The fourth "
        "check is electrical: if the Arduino loses power, the motor driver's standby pin goes "
        "low and the outputs are disabled.",
    )
    add_figure(
        doc,
        assets["d_safety"],
        "Layered safety hierarchy from host checks to electrical disable.",
    )
    add_table(
        doc,
        ["Layer", "Check", "Threshold", "Action", "Evidence"],
        [
            ["Host", "Frame age", "> 1.0 s", "Send STOP", "Stale-frame test"],
            ["Serial", "Command age", "> 3.0 s", "Stop motors", "Watchdog test"],
            [
                "Arduino",
                "Forward distance",
                "< 15 cm",
                "Refuse forward",
                "Obstacle test",
            ],
            [
                "Arduino",
                "Command validity",
                "Not F/B/L/R/S",
                "STATUS:ERROR",
                "Protocol test",
            ],
            [
                "Electrical",
                "Driver enable",
                "STBY low",
                "Outputs disabled",
                "Bench check",
            ],
        ],
        widths=[0.85, 1.4, 1.0, 1.6, 1.6],
        caption="Safety layers, thresholds, actions, and supporting evidence.",
        font_size=8.4,
    )

    doc.add_heading("9.5 Watchdog Design", level=2)
    add_body(
        doc,
        "The watchdog is a software timer in the Arduino firmware. Every valid command resets "
        "the timer. If the timer reaches 3 seconds, the firmware calls the stop routine, sets "
        "the state to STOP, and disables the motor driver. The watchdog is not a hardware "
        "watchdog timer; it is a communication timeout. It protects against a dead host, a "
        "pulled USB cable, or a serial driver that has stopped writing. It does not protect "
        "against a firmware hang, which is why the loop is kept short and non-blocking.",
    )
    add_callout(
        doc,
        "The safe state is STOP",
        "Silence must never mean \u201ckeep driving\u201d. If the host stops sending, the "
        "Arduino stops the motors after 3 seconds. If the camera stops streaming, the host "
        "sends STOP. If the Arduino loses power, the driver is disabled. Every failure path "
        "converges on the same safe state.",
        fill="E8F5E9",
        border=GREEN,
    )

    doc.add_heading("9.6 Failure Mode and Effects Analysis", level=2)
    add_body(
        doc,
        "The FMEA below was written before the short-circuit incident and revised afterwards. "
        "It lists the failure modes that the design is intended to handle, their effects, and "
        "the mitigation. The incident added the battery-terminal row and raised the severity of "
        "the power-path rows.",
    )
    add_table(
        doc,
        ["Failure mode", "Effect", "Severity", "Mitigation"],
        [
            [
                "Wi-Fi link drops",
                "No new frames",
                "High",
                "Host stale-frame check; Arduino watchdog",
            ],
            [
                "USB cable pulled",
                "No new commands",
                "High",
                "3 s watchdog stops motors",
            ],
            [
                "Camera board resets",
                "Stream stops",
                "Medium",
                "Host reconnects or sends STOP",
            ],
            [
                "Ultrasonic misses obstacle",
                "Possible collision",
                "High",
                "Low speed; visual stop; operator supervision",
            ],
            [
                "Motor stall",
                "High current, heat",
                "Medium",
                "Fuse; driver current limit; current sensing (future)",
            ],
            [
                "Battery terminal touches chassis",
                "Short circuit, damaged parts",
                "Critical",
                "Insulated lug; fuse; strain relief; checklist",
            ],
            [
                "Buck mis-set",
                "Overvoltage on logic",
                "Critical",
                "Set to 5.0 V before connection; verify with meter",
            ],
            [
                "Arduino firmware hang",
                "Motors may keep last command",
                "High",
                "Non-blocking loop; hardware watchdog (future)",
            ],
            [
                "Driver overheating",
                "Thermal shutdown",
                "Medium",
                "TB6612FNG upgrade; current margin",
            ],
        ],
        widths=[1.75, 1.45, 0.7, 2.5],
        caption="Failure mode and effects analysis for the rover.",
        font_size=8.2,
    )

    doc.add_heading("9.7 Test Plan", level=2)
    add_body(
        doc,
        "The test plan follows a pyramid. At the base are unit tests for the decision, safety, "
        "and protocol logic. In the middle are integration tests that feed recorded frames and "
        "synthetic sensor values through the host stack. At the top are end-to-end tests that "
        "run the firmware in simulation and, where possible, on the physical rover. The "
        "measured results are reported in Chapter 10.",
    )
    add_bullets(
        doc,
        [
            "Unit: threshold boundaries, deadband edges, command parsing, watchdog expiry, distance "
            "validation, and log schema.",
            "Integration: recorded frame sequences replayed through the detector, decision engine, "
            "and serial transport with a mock Arduino.",
            "Simulation: Wokwi runs of the Arduino firmware with synthetic ultrasonic distances and "
            "serial commands.",
            "Hardware: continuity, voltage, motor direction, obstacle stop, and link-loss stop.",
            "Regression: the full suite is run before every commit that touches the decision or "
            "safety layers.",
        ],
    )


def chapter_results(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 10", "Testing and Measured Results")
    add_body(
        doc,
        "This chapter reports what was measured, not what was hoped for. The evidence comes "
        "from the test suite, the static analyzer, the firmware builds, the Wokwi simulator, "
        "the detector benchmark logs, and the event-log evaluation. Where a measurement is "
        "missing, the gap is stated explicitly rather than filled with an estimate.",
    )

    doc.add_heading("10.1 Verification Summary", level=2)
    add_table(
        doc,
        ["Check", "Result", "Evidence"],
        [
            ["Python test suite", "311 passing tests", "pytest report"],
            ["Static analysis", "No errors or warnings", "ruff / mypy logs"],
            ["Arduino firmware build", "Compiles successfully", "arduino-cli build"],
            [
                "ESP32 firmware build",
                "Compiles successfully",
                "arduino-cli / PlatformIO",
            ],
            ["Wokwi simulation", "3 runs completed", "Simulation logs"],
            [
                "Detector evaluation",
                "128 images, 929 objects",
                "COCO128 benchmark JSON",
            ],
            ["Event-log evaluation", "9,118 rows, 17 runs", "logs/eval.json"],
            ["Safety invariant check", "0 violations", "logs/eval.json"],
        ],
        widths=[1.8, 1.7, 2.5],
        caption="Verification summary for the final build.",
        font_size=8.4,
    )
    add_body(
        doc,
        "The 311 passing tests cover the host stack, not the physical rover. They are strong "
        "evidence that the decision and safety logic behaves as specified on recorded inputs. "
        "They are not evidence that the rover never collides; that requires hardware testing, "
        "which is reported separately and is still incomplete for the final TB6612FNG build.",
    )

    doc.add_heading("10.2 Detector Benchmark", level=2)
    add_body(
        doc,
        "Five detectors were evaluated on the same 128-image COCO128 subset, which contains "
        "929 annotated objects. All models used the same confidence threshold (0.25) and the "
        "same IoU threshold (0.5). The results show the expected accuracy-versus-latency "
        "trade-off: RT-DETRv2-R18 achieved the highest recall and mAP but was far too slow for "
        "closed-loop control, while the YOLO models were faster but less accurate.",
    )
    add_table(
        doc,
        ["Model", "Precision", "Recall", "F1", "mAP@0.5", "Median latency"],
        [
            ["YOLO11n", "0.805", "0.342", "0.480", "0.516", "124 ms"],
            ["YOLO11s", "0.813", "0.477", "0.601", "0.640", "534 ms"],
            ["YOLO26n", "0.829", "0.354", "0.496", "0.523", "126 ms"],
            ["YOLO26s", "0.787", "0.473", "0.591", "0.594", "452 ms"],
            ["RT-DETRv2-R18", "0.283", "0.883", "0.428", "0.815", "3,427 ms"],
        ],
        widths=[1.45, 1.0, 0.9, 0.8, 0.9, 1.2],
        caption="Detector comparison on COCO128 at 320-pixel input [MEASURED].",
        font_size=8.4,
    )
    add_figure(
        doc, assets["c_models"], "Detector recall and median latency comparison."
    )
    add_body(
        doc,
        "The selected model is YOLO11s. Its recall of 0.477 and mAP@0.5 of 0.640 are the best "
        "among the models that met the control budget. Its median latency of 534 ms leaves "
        "roughly 466 ms of the 1 s budget for capture, decision, serial transport, and display. "
        "RT-DETRv2-R18 is not usable in this configuration: at 3.4 s per frame, the rover would "
        "travel more than a metre between decisions.",
    )
    add_body(
        doc,
        "The low precision of RT-DETRv2-R18 (0.283) is a reminder that high recall alone is not "
        "enough. The model produced an average of 22.7 predictions per image against 7.3 ground "
        "truths, which means it flooded the frame with false positives. The YOLO11s model "
        "produced 4.3 predictions per image, which is much closer to the ground-truth density.",
    )

    doc.add_heading("10.3 Runtime Backend Comparison", level=2)
    add_body(
        doc,
        "The same YOLO11s model was executed through three runtimes: PyTorch, ONNX Runtime, "
        "and OpenVINO. ONNX Runtime was the fastest, with a median latency of 181 ms, followed "
        "by PyTorch at 435 ms and OpenVINO at 461 ms. The ONNX run also produced slightly higher "
        "recall and mAP, which is consistent with differences in pre- and post-processing rather "
        "than with a different model.",
    )
    add_table(
        doc,
        ["Runtime", "Median latency", "Recall", "mAP@0.5", "Note"],
        [
            ["PyTorch (.pt)", "435 ms", "0.477", "0.640", "Reference implementation"],
            ["ONNX Runtime", "181 ms", "0.490", "0.648", "Fastest measured backend"],
            ["OpenVINO", "461 ms", "0.490", "0.648", "Higher overhead on this host"],
        ],
        widths=[1.4, 1.1, 0.8, 0.9, 2.3],
        caption="YOLO11s runtime backend comparison [MEASURED].",
        font_size=8.4,
    )
    add_figure(
        doc,
        assets["c_runtime"],
        "Median latency for the three YOLO11s runtime backends.",
    )

    doc.add_heading("10.4 Event-Log Evaluation", level=2)
    add_body(
        doc,
        "The event-log evaluation analysed 9,118 rows from 17 runs recorded between 18 September "
        "and 1 October 2026. The log contains the mode, decision, target class, confidence, "
        "distance, inference time, and safety state for each processed frame. The evaluation "
        "checked ten invariants and found zero violations.",
    )
    add_table(
        doc,
        ["Metric", "Value", "Interpretation"],
        [
            ["Rows analysed", "9,118", "17 runs, 0 malformed rows"],
            ["SAFE state", "8,483 (93.04%)", "Most frames had no safety intervention"],
            [
                "Safety interventions",
                "635 (6.96%)",
                "Close obstacle, low confidence, etc.",
            ],
            ["STOP decisions", "1,989 (21.81%)", "Includes no-target and safety stops"],
            ["FORWARD decisions", "7,103 (77.90%)", "Dominant motion command"],
            ["Detection rate", "80.07%", "Bottle present in 7,301 frames"],
            ["Mean confidence", "0.495", "At the 0.25 threshold"],
            ["Median FPS", "17.7", "Event-log pipeline, not detector latency"],
            ["Invariant violations", "0", "Ten invariants checked"],
        ],
        widths=[1.7, 1.6, 2.7],
        caption="Event-log evaluation summary [MEASURED].",
        font_size=8.4,
    )
    add_figure(
        doc,
        assets["c_safety"],
        "Non-safe safety states recorded during the event-log campaign.",
    )
    add_body(
        doc,
        "The most frequent non-safe state was CAUTION_CLOSE_OBSTACLE (208 rows), followed by "
        "LOW_CONFIDENCE (186 rows) and CAUTION_UNKNOWN_DISTANCE (112 rows). Communication loss "
        "was rare (20 rows), which is consistent with a bench setup in which the USB cable is "
        "short and the host is not moved. The low count is not evidence that the watchdog is "
        "unnecessary; it is evidence that the test conditions did not stress the link.",
    )

    doc.add_heading("10.5 Simulation Results", level=2)
    add_body(
        doc,
        "Three Wokwi simulations were run against the Arduino firmware. The simulations "
        "exercised forward, backward, left, right, stop, obstacle refusal, and watchdog expiry. "
        "The firmware behaved as specified in all three runs. Simulation is not a substitute "
        "for hardware testing, but it is valuable for catching logic errors before they reach "
        "the bench.",
    )
    add_table(
        doc,
        ["Run", "Scenario", "Result", "Observation"],
        [
            [
                "1",
                "Nominal commands",
                "Pass",
                "All five commands produced the expected motor states",
            ],
            ["2", "Obstacle at 10 cm", "Pass", "Forward refused; STOP reported"],
            [
                "3",
                "Watchdog expiry",
                "Pass",
                "Motors stopped after 3 s without a command",
            ],
        ],
        widths=[0.6, 1.6, 0.8, 3.0],
        caption="Wokwi simulation runs and outcomes.",
        font_size=8.4,
    )

    doc.add_heading("10.6 What Is Still Pending", level=2)
    add_body(
        doc,
        "The final TB6612FNG build has not yet completed the full hardware test campaign. The "
        "following measurements are marked [PENDING]: continuous runtime on a full pack, motor "
        "current under load, driver temperature during a 10-minute run, actual stopping distance "
        "at 15 cm, and repeatability of the obstacle gate across ten trials. These are not "
        "cosmetic gaps; they are the measurements that would turn the design estimates in "
        "Chapter 7 into verified performance figures.",
    )
    add_callout(
        doc,
        "Reading the results honestly",
        "The detector numbers are measured. The event-log numbers are measured. The runtime, "
        "current, and stopping-distance numbers for the final TB6612FNG build are design "
        "estimates or pending. Mixing the two categories would overstate the maturity of the "
        "prototype.",
        fill="FFF4E5",
        border=AMBER,
    )


def chapter_incident(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 11", "Case Study: The 26 October Battery Short Circuit")
    add_body(
        doc,
        "On 26 October 2026, at approximately 20:14, the rover suffered a battery short circuit "
        "during power integration. The positive terminal of the 2S pack touched the grounded "
        "aluminium chassis while the pack was connected. The event damaged the terminal lug and "
        "the compression spring, and it affected a small number of components on the power "
        "path. No one was injured. This chapter reconstructs the event, identifies the root "
        "cause, describes the damage, and records the corrective actions that changed the "
        "design.",
    )
    add_callout(
        doc,
        "Incident at a glance",
        "Date: 26 October 2026, approximately 20:14. Location: electronics bench. Trigger: "
        "positive battery terminal contacted the grounded chassis. Immediate effect: short "
        "circuit, terminal and spring damage, power-path components affected. Immediate action: "
        "power removed, pack isolated, bench cleared. Root cause: exposed positive terminal "
        "combined with a grounded chassis and no strain relief.",
        fill="FDECEA",
        border=RED,
    )

    doc.add_heading("11.1 What Happened", level=2)
    add_body(
        doc,
        "The rover had been running on the bench with the L298N driver. The TB6612FNG had just "
        "been photographed and was being prepared for installation. The battery pack was seated "
        "in its holder, and the positive lead was being positioned for a continuity check. The "
        "terminal lug was exposed; the chassis plate beneath it was grounded through the motor "
        "mounts and the common ground. When the lug touched the plate, the pack was shorted "
        "through the chassis.",
    )
    add_body(
        doc,
        "The short was brief but energetic. The terminal lug and the compression spring were "
        "damaged by the current and the heat. The pack was removed immediately, and the bench "
        "was cleared of loose metal. The rover was not powered again that evening. The damaged "
        "parts were photographed the same night, and the photograph is included in this report "
        "as primary evidence.",
    )
    add_figure(
        doc,
        assets["asm13"],
        "Damaged battery terminal lug and compression spring photographed after the short "
        "circuit.",
    )

    doc.add_heading("11.2 Timeline", level=2)
    add_table(
        doc,
        ["Time", "Event", "Action"],
        [
            [
                "19:08",
                "TB6612FNG photographed before installation",
                "Upgrade preparation",
            ],
            ["19:09", "TB6612FNG pinout photographed", "Wiring reference"],
            [
                "~20:00",
                "Battery seated; positive lead positioned",
                "Continuity check planned",
            ],
            ["20:14", "Positive terminal touched grounded chassis", "Short circuit"],
            ["20:14", "Power removed; pack isolated", "Immediate response"],
            ["20:15", "Bench cleared of loose metal", "Make-safe"],
            ["20:20", "Damage photographed", "Evidence capture"],
            [
                "Next session",
                "Insulation, fuse, strain relief, driver upgrade",
                "Corrective action",
            ],
        ],
        widths=[0.9, 3.2, 2.0],
        caption="Reconstructed timeline of the 26 October incident.",
        font_size=8.4,
    )

    doc.add_heading("11.3 Root Cause", level=2)
    add_body(
        doc,
        "The immediate cause was a positive terminal in contact with a grounded conductor. The "
        "underlying causes were more interesting. First, the terminal lug was exposed: the "
        "soldered joint had been checked electrically but not insulated mechanically. Second, "
        "the battery holder allowed the pack to shift, so the lead could move into contact with "
        "the chassis. Third, the positive lead had no strain relief, so the terminal was loaded "
        "by the weight of the wire. Fourth, the bench procedure did not require the pack to be "
        "disconnected before the lead was repositioned.",
    )
    add_body(
        doc,
        "This is a classic Swiss-cheese failure: several small weaknesses lined up. Any one of "
        "them would have prevented the event. If the lug had been insulated, the contact would "
        "have been harmless. If the holder had restrained the pack, the lead would not have "
        "moved. If the lead had been strain-relieved, the terminal would not have been loaded. "
        "If the procedure had required disconnection, the pack would not have been live during "
        "the adjustment.",
    )
    add_table(
        doc,
        ["Cause", "Category", "Contribution", "Corrective action"],
        [
            [
                "Exposed positive lug",
                "Design",
                "Direct contact path",
                "Heat-shrink and insulated cover",
            ],
            [
                "Pack could shift in holder",
                "Design",
                "Allowed lead movement",
                "Retention bracket and foam",
            ],
            [
                "No strain relief",
                "Design",
                "Loaded the terminal",
                "Cable tie and service loop",
            ],
            [
                "No fuse in the lead",
                "Design",
                "Unlimited fault current",
                "3 A inline fuse",
            ],
            [
                "Live adjustment procedure",
                "Procedure",
                "Pack energized during work",
                "Disconnect before handling",
            ],
            [
                "No pre-power checklist",
                "Procedure",
                "Missed inspection",
                "Checklist before every power-up",
            ],
        ],
        widths=[1.7, 0.9, 1.8, 1.9],
        caption="Root causes and corrective actions for the short-circuit incident.",
        font_size=8.2,
    )

    doc.add_heading("11.4 Damage Assessment", level=2)
    add_body(
        doc,
        "The visible damage was confined to the battery terminal lug and the compression spring. "
        "The lug was pitted and discoloured, and the spring had lost tension. A small number of "
        "components on the power path were affected; the motor driver and the logic boards were "
        "not powered through the fault path and were inspected separately. The battery pack was "
        "removed from service and its cells were checked individually before reuse.",
    )
    add_table(
        doc,
        ["Item", "Damage", "Disposition"],
        [
            ["Battery terminal lug", "Pitting, discolouration", "Replaced"],
            ["Compression spring", "Lost tension", "Replaced"],
            ["Inline fuse", "Not fitted at the time", "Added in the rebuild"],
            ["L298N driver", "Inspected; not used in final build", "Retired"],
            [
                "Logic boards",
                "Inspected; no visible damage",
                "Retained after voltage check",
            ],
            [
                "Battery pack",
                "Cells checked individually",
                "Retained with new terminal",
            ],
        ],
        widths=[1.7, 2.4, 1.9],
        caption="Damage assessment and disposition of affected items.",
        font_size=8.4,
    )
    add_callout(
        doc,
        "A note on honesty",
        "The incident is documented because it happened, not because it is unusual. Small "
        "robots are often built with exposed terminals and live adjustments. The value of the "
        "case study is in the corrective actions, not in the drama of the event.",
        fill="FFF4E5",
        border=AMBER,
    )

    doc.add_heading("11.5 Corrective Actions", level=2)
    add_body(
        doc,
        "The rebuild addressed both the design and the procedure. On the design side, the "
        "positive terminal was covered with heat-shrink, the battery holder was fitted with a "
        "retention bracket and foam, the lead was given a service loop and a cable tie, and a "
        "3 A inline fuse was added close to the pack. The L298N was replaced with a TB6612FNG, "
        "which reduced the thermal load and the voltage drop. On the procedure side, a pre-power "
        "checklist was introduced and the pack is now disconnected before any lead is "
        "repositioned.",
    )
    add_numbered(
        doc,
        [
            "Insulate the positive terminal with heat-shrink and a snap-on cover.",
            "Add a retention bracket and foam so the pack cannot shift in the holder.",
            "Provide a service loop and a cable tie for strain relief.",
            "Fit a 3 A inline fuse within 10 cm of the positive terminal.",
            "Replace the L298N with the TB6612FNG and verify the new pin map.",
            "Disconnect the pack before repositioning any lead.",
            "Complete the pre-power checklist before every power-up.",
            "Photograph the power path after every change.",
        ],
    )
    add_figure(
        doc,
        assets["asm12"],
        "Insulated motor joints adopted before the incident; the same practice was extended to the battery terminal.",
    )

    doc.add_heading("11.6 Pre-Power Checklist", level=2)
    add_table(
        doc,
        ["Check", "Pass criterion"],
        [
            ["Battery terminal insulation", "No exposed metal; heat-shrink intact"],
            ["Fuse", "Correct rating; holder secure; continuity verified"],
            ["Buck output", "5.0 V +/- 0.1 V before logic is connected"],
            ["Polarity", "Positive and negative identified at every connector"],
            ["Ground", "Single star point; no daisy-chained motor ground"],
            ["Strain relief", "No load on soldered joints; service loop present"],
            ["Loose metal", "Bench clear of screws, cut leads, and tools"],
            ["Switch", "OFF before connecting or disconnecting the pack"],
        ],
        widths=[2.2, 3.8],
        caption="Pre-power checklist introduced after the incident.",
        font_size=8.4,
    )

    doc.add_heading("11.7 Lessons Learned", level=2)
    add_body(
        doc,
        "The incident changed the way the project thinks about safety. The first lesson is that "
        "a fuse is not a substitute for insulation; it limits the consequence of a fault but "
        "does not prevent the fault. The second is that mechanical retention is part of "
        "electrical safety: a battery that can move is a battery that can short. The third is "
        "that procedures are engineering artefacts; a checklist is as important as a capacitor. "
        "The fourth is that the cheapest driver is not always the best driver: the TB6612FNG "
        "upgrade reduced heat and voltage drop, and it made the power path easier to inspect.",
    )
    add_body(
        doc,
        "The final lesson is about documentation. The damaged terminal was photographed "
        "immediately, before it was repaired. That photograph is now the most useful image in "
        "the report, because it makes the failure concrete. A report that showed only the "
        "finished rover would be less useful to the next student than a report that shows what "
        "went wrong and why.",
    )


def chapter_discussion(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 12", "Discussion, Limitations, and Future Work")
    add_body(
        doc,
        "The rover meets its core objectives: it streams video, detects a target, steers toward "
        "it, stops at an obstacle, and stops when the link is lost. It does so with commodity "
        "parts and a documented build. It is not a finished product, and this chapter is "
        "explicit about the gap between the prototype and a dependable autonomous system.",
    )

    doc.add_heading("12.1 What Worked", level=2)
    add_bullets(
        doc,
        [
            "The three-tier split kept vision and safety independent. A host failure does not "
            "prevent the Arduino from stopping the motors.",
            "The ESP32-CAM Wi-Fi stream was reliable at short range and required no data wiring to "
            "the Arduino, which avoided a level-shift hazard.",
            "The YOLO11s model met the 1 s control budget and produced usable bounding boxes for "
            "the target class.",
            "The event-log evaluation found zero violations of ten safety invariants across 9,118 "
            "rows.",
            "The photo-dated build log made it possible to reconstruct the project honestly, "
            "including the incident.",
        ],
    )

    doc.add_heading("12.2 Limitations", level=2)
    add_table(
        doc,
        ["Limitation", "Impact", "Possible remedy"],
        [
            [
                "Laptop in the loop",
                "Not standalone; depends on a host and Wi-Fi",
                "On-board SBC or edge accelerator",
            ],
            [
                "No wheel encoders",
                "Open-loop straight-line motion; no odometry",
                "Add quadrature encoders",
            ],
            [
                "Monocular camera",
                "No direct depth; scale is ambiguous",
                "Stereo camera or depth sensor",
            ],
            [
                "Single target class",
                "Cannot distinguish multiple objects",
                "Multi-class training and tracking",
            ],
            [
                "Narrow ultrasonic cone",
                "Can miss soft or angled obstacles",
                "Add LiDAR or multiple sensors",
            ],
            [
                "No hardware watchdog",
                "Firmware hang may leave last command",
                "Enable AVR watchdog timer",
            ],
            ["Exposed electronics", "Fragile; not sealed", "3D-printed enclosure"],
            [
                "Limited hardware validation",
                "Final TB6612FNG build not fully characterised",
                "Complete the pending test campaign",
            ],
        ],
        widths=[1.6, 2.4, 2.0],
        caption="Limitations of the current prototype and possible remedies.",
        font_size=8.2,
    )

    doc.add_heading("12.3 Threats to Validity", level=2)
    add_body(
        doc,
        "The detector results are valid for the COCO128 subset and the chosen confidence "
        "threshold. They are not a claim about performance on a different dataset, in low "
        "light, or with a different camera. The event-log results are valid for the recorded "
        "runs, which were mostly bench sessions with a short USB cable. The safety statistics "
        "therefore under-represent link-loss scenarios. The hardware results are the weakest "
        "evidence: the final driver build has not completed the runtime, current, and "
        "stopping-distance tests.",
    )
    add_body(
        doc,
        "The build narrative is based on photograph timestamps, which record when the image was "
        "taken, not necessarily when the work was done. A photograph taken at 21:36 may show a "
        "session that began hours earlier. The narrative uses the timestamps as anchors and "
        "avoids claiming more precision than the metadata supports.",
    )

    doc.add_heading("12.4 Future Work", level=2)
    add_body(
        doc,
        "The next version of the rover should address the following, in priority order:",
    )
    add_numbered(
        doc,
        [
            "Complete the hardware test campaign for the TB6612FNG build: runtime, current, driver "
            "temperature, stopping distance, and ten-trial obstacle repeatability.",
            "Add quadrature encoders and a closed-loop wheel-speed controller to reduce curvature "
            "and enable odometry.",
            "Move detection onto an on-board single-board computer or edge accelerator so the rover "
            "does not depend on a laptop.",
            "Add a hardware watchdog timer and a power-on self-test that checks the driver, the "
            "sensor, and the serial link.",
            "Design a 3D-printed enclosure with a fused, keyed battery connector and a serviceable "
            "cable harness.",
            "Add a second ranging sensor or a LiDAR to reduce the blind spots of the HC-SR04.",
            "Collect a domain-specific dataset and fine-tune the detector for indoor lighting and "
            "the actual target objects.",
            "Implement multi-target tracking and a simple occupancy map for cluttered spaces.",
        ],
    )

    doc.add_heading("12.5 Broader Reflection", level=2)
    add_body(
        doc,
        "The project's most valuable outcome is not the rover itself. It is the demonstration "
        "that a small, distributed system can be made safer by assigning authority explicitly: "
        "the laptop is allowed to perceive and decide, but it is not allowed to be the last line "
        "of defence. The same pattern appears in industrial control, in automotive systems, and "
        "in any robot that must fail safely. The rover is a small example of a large idea.",
    )
    add_body(
        doc,
        "The second outcome is methodological. The photo-dated log, the measured benchmarks, "
        "and the incident case study form a record that another student can follow. That record "
        "is more useful than a polished demonstration video, because it shows the decisions and "
        "the mistakes that a video would hide.",
    )


def chapter_conclusion(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Chapter 13", "Conclusion")
    add_body(
        doc,
        "This report documented the design, assembly, software integration, testing, and "
        "recovery of a low-cost vision-guided differential-drive rover. The rover uses an "
        "ESP32-CAM for Wi-Fi video, a laptop for YOLO-based detection and decision-making, and "
        "an Arduino UNO for deterministic motor and obstacle safety. The three tiers are "
        "connected by narrow interfaces: MJPEG over Wi-Fi and one-character commands over USB "
        "serial.",
    )
    add_body(
        doc,
        "The build was completed in stages between 3 and 26 October 2026. The mechanical base, "
        "the ultrasonic mount, the bench wiring, the two-tier stack, the Wi-Fi stream, and the "
        "insulated motor harness were each photographed and recorded. The final power "
        "integration was interrupted by a battery short circuit that damaged the terminal and a "
        "small number of power-path components. The recovery added insulation, a fuse, strain "
        "relief, a pre-power checklist, and a TB6612FNG driver upgrade.",
    )
    add_body(
        doc,
        "The measured evidence supports three conclusions. First, a commodity ESP32-CAM and a "
        "laptop can provide usable visual servoing for a small indoor rover. Second, a "
        "YOLO11s detector at 320 pixels can meet a 1 s control budget on a modest CPU while "
        "achieving recall 0.477, F1 0.601, and mAP@0.5 0.640 on the COCO128 evaluation set. "
        "Third, a layered safety architecture with a 3 s communication watchdog and a 15 cm "
        "obstacle gate can enforce a safe stop even when the perception tier is unreliable.",
    )
    add_body(
        doc,
        "The project also produced a methodological result: a photo-dated build narrative, a "
        "measured benchmark, and an honest incident case study are more valuable to the next "
        "student than a polished but undocumented demonstration. The rover is a prototype, not "
        "a product. Its limitations are known, its pending measurements are labelled, and its "
        "next steps are specific. That is the appropriate state for a student project at this "
        "stage.",
    )
    add_callout(
        doc,
        "Final statement",
        "The rover can see, decide, and stop. The safety layer is independent of the vision "
        "layer, the failure paths converge on STOP, and the build is documented well enough to "
        "be reproduced and improved.",
        fill="E8F5E9",
        border=GREEN,
    )


def chapter_references(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "References", "References")
    add_body(
        doc,
        "The following sources informed the design and the background chapters. Repository "
        "files and measured logs are cited where they are the direct evidence for a result.",
    )
    refs = [
        "Siegwart, R., Nourbakhsh, I. R., and Scaramuzza, D. Introduction to Autonomous Mobile "
        "Robots, 2nd ed., MIT Press, 2011.",
        "Redmon, J., Divvala, S., Girshick, R., and Farhadi, A. \u201cYou Only Look Once: "
        "Unified, Real-Time Object Detection,\u201d CVPR, 2016.",
        "Jocher, G., Chaurasia, A., and Qiu, J. Ultralytics YOLO (Version 8.0) [Computer "
        "software], 2023. https://github.com/ultralytics/ultralytics",
        "Carion, N., Massa, F., Synnaeve, G., Usunier, N., Kirillov, A., and Zagoruyko, S. "
        "\u201cEnd-to-End Object Detection with Transformers,\u201d ECCV, 2020.",
        "Zhao, Y., Lv, W., Xu, S., Wei, J., Wang, G., Dang, Q., Liu, Y., and Chen, J. "
        "\u201cDETRs Beat YOLOs on Real-time Object Detection,\u201d CVPR, 2024.",
        "Espressif Systems. ESP32-CAM Development Board Documentation. https://docs.espressif.com/",
        "Arduino. Arduino UNO R3 Product Reference Manual. https://docs.arduino.cc/",
        "Toshiba Semiconductor. TB6612FNG Dual DC Motor Driver IC Datasheet.",
        "STMicroelectronics. L298 Dual Full-Bridge Driver Datasheet.",
        "Texas Instruments. LM2596 SIMPLE SWITCHER Power Converter Datasheet.",
        "Elecfreaks. HC-SR04 Ultrasonic Ranging Module Datasheet.",
        "OpenCV. OpenCV 4.x Documentation. https://docs.opencv.org/",
        "Wokwi. Online Arduino and ESP32 Simulator. https://wokwi.com/",
        "Project repository. Firmware, host software, test suite, event logs, and benchmark "
        "JSON files, 2026.",
    ]
    for idx, ref in enumerate(refs, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(f"[{idx}]  ")
        run.font.name = "Times New Roman"
        run.font.size = Pt(10.5)
        run.bold = True
        run = p.add_run(ref)
        run.font.name = "Times New Roman"
        run.font.size = Pt(10.5)


def appendix_bom(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Appendix A", "Bill of Materials")
    add_body(
        doc,
        "The bill of materials below lists the parts used in the final prototype. Costs are "
        "indicative Indian market prices at the time of build and are included to show the "
        "order of magnitude, not to serve as a quotation. The rover was assembled from a "
        "mixture of laboratory stock and purchased modules.",
    )
    add_table(
        doc,
        ["Item", "Specification", "Qty", "Indicative cost (INR)", "Role"],
        [
            ["ESP32-CAM", "AI-Thinker, OV2640, 4 MB", "1", "600", "Wi-Fi video"],
            ["Arduino UNO R3", "ATmega328P, 5 V", "1", "700", "Safety supervisor"],
            ["TT gear motor", "3-6 V, dual shaft", "2", "240", "Drive"],
            ["TB6612FNG", "Dual MOSFET H-bridge", "1", "250", "Motor driver"],
            ["HC-SR04", "Ultrasonic ranging kit", "1", "100", "Obstacle gate"],
            ["2S 18650 pack", "7.4 V, 2000 mAh", "1", "500", "Main power"],
            ["LM2596 buck", "Adjustable step-down", "1", "120", "5 V logic rail"],
            ["Acrylic chassis", "Laser-cut plates", "1 set", "400", "Structure"],
            ["Caster wheel", "Omni, 2 inch", "1", "100", "Third support"],
            ["Rocker switch", "SPST, 3 A", "1", "40", "Master isolation"],
            ["Inline fuse", "3 A with holder", "1", "50", "Short protection"],
            [
                "Wiring and fasteners",
                "Dupont, heat-shrink, screws",
                "1 set",
                "300",
                "Harness",
            ],
        ],
        widths=[1.2, 1.9, 0.5, 1.2, 1.4],
        caption="Indicative bill of materials for the final prototype.",
        font_size=8.0,
    )
    add_body(
        doc,
        "The total indicative cost is approximately INR 3,400 (about USD 41 at the time of "
        "writing), which is below the USD 70 target. The figure excludes tools, the laptop, "
        "and the 3D-printed parts that were not used in the final build.",
    )


def appendix_pinmap(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Appendix B", "Pin Map and Wiring Reference")
    add_body(
        doc,
        "The pin map below reflects the final firmware configuration. The L298N baseline used "
        "the same control pins with different signal names; the TB6612FNG adapter renames ENA "
        "to PWMA, IN1/IN2 to AIN1/AIN2, IN3/IN4 to BIN1/BIN2, and ENB to PWMB, and ties STBY "
        "to the 5 V logic rail. D0 and D1 are reserved for USB serial and must never be "
        "jumpered to the ESP32.",
    )
    add_table(
        doc,
        ["Arduino pin", "Connected to", "Direction", "Function"],
        [
            ["D0 / RXD", "USB serial", "Input", "Host command ingest (9600 baud)"],
            ["D1 / TXD", "USB serial", "Output", "Telemetry to host"],
            ["D2", "Encoder L (reserved)", "Input", "Left wheel tick (not fitted)"],
            ["D3", "Encoder R (reserved)", "Input", "Right wheel tick (not fitted)"],
            ["D5", "TB6612FNG PWMA", "Output", "Left motor speed"],
            ["D6", "TB6612FNG AIN1", "Output", "Left motor direction"],
            ["D7", "TB6612FNG AIN2", "Output", "Left motor direction"],
            ["D8", "TB6612FNG BIN1", "Output", "Right motor direction"],
            ["D9", "TB6612FNG BIN2", "Output", "Right motor direction"],
            ["D10", "TB6612FNG PWMB", "Output", "Right motor speed"],
            ["D11", "HC-SR04 TRIG", "Output", "10 us trigger pulse"],
            ["D12", "HC-SR04 ECHO", "Input", "Echo pulse width"],
            ["D13", "Onboard LED", "Output", "Heartbeat"],
            ["5V", "Buck 5 V, TB6612FNG VCC/STBY", "Power", "Logic supply"],
            ["GND", "Star ground", "Power", "0 V reference"],
        ],
        widths=[1.1, 2.1, 0.9, 2.5],
        caption="Arduino UNO pin map for the final build.",
        font_size=8.2,
    )
    add_table(
        doc,
        ["ESP32-CAM pin", "Connected to", "Function"],
        [
            ["5V", "Buck 5 V", "Power in (onboard 3.3 V LDO)"],
            ["GND", "Star ground", "0 V reference"],
            ["GPIO 0", "OV2640 XCLK", "Camera clock"],
            ["GPIO 26 / 27", "OV2640 SIOD / SIOC", "Camera control bus"],
            ["GPIO 5, 18, 19, 21, 36, 39, 34, 35", "OV2640 D0-D7", "Camera data bus"],
            ["GPIO 22 / 23 / 25", "OV2640 PCLK / HREF / VSYNC", "Camera timing"],
            ["GPIO 32", "OV2640 PWDN", "Camera power-down"],
            ["GPIO 4", "Flash LED", "Illumination (optional)"],
            ["GPIO 33", "Red status LED", "Diagnostic"],
        ],
        widths=[2.1, 2.1, 2.4],
        caption="ESP32-CAM pin usage. No data pins connect to the Arduino.",
        font_size=8.2,
    )
    add_callout(
        doc,
        "Never jumper Arduino TX to ESP32 RX",
        "The Arduino TX pin is 5 V. The ESP32 GPIO pins are 3.3 V. A direct connection can "
        "destroy the ESP32 pin. The rover deliberately has no wired data link between the two "
        "boards; video travels over Wi-Fi and commands travel over USB.",
        fill="FDECEA",
        border=RED,
    )


def appendix_photo_index(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Appendix C", "Photographic Index")
    add_body(
        doc,
        "The photographs are the primary evidence for the build chronology. The table lists the "
        "image, the date encoded in the filename or metadata, and the report section where it "
        "is used. Times are included where the filename or screenshot provides them.",
    )
    add_table(
        doc,
        ["Image", "Date / time", "Subject", "Section"],
        [
            [
                "hw_ultrasonic_sensor_hcsr04_with_bracket.jpg",
                "3 Oct 2026",
                "HC-SR04 kit",
                "5.5, 6.1",
            ],
            [
                "assembly_01 ... switch.jpeg",
                "6 Oct 2026",
                "Battery holder and switch",
                "6.2",
            ],
            [
                "assembly_02 ... motors_mounted.jpeg",
                "6 Oct 2026",
                "Dual TT motors",
                "6.2",
            ],
            [
                "assembly_03 ... caster_mounted.jpeg",
                "6 Oct 2026",
                "Wheels and caster",
                "6.2",
            ],
            ["assembly_04 ... wheels.jpeg", "6 Oct 2026", "Rolling base", "6.2"],
            [
                "assembly_05 ... rear_mount.jpeg",
                "9 Oct 2026",
                "Ultrasonic mount",
                "6.3",
            ],
            [
                "assembly_06 ... mount_detail.jpeg",
                "9 Oct 2026",
                "Bracket detail",
                "6.3",
            ],
            [
                "hw_arduino_uno_wired.jpg",
                "19 Oct 2026, 21:23",
                "Arduino with jumpers",
                "5.6, 6.4",
            ],
            [
                "telemetry_live_yolo_tracking_ip_webcam.jpg",
                "19 Oct 2026, 21:36",
                "Live YOLO",
                "6.4",
            ],
            [
                "telemetry_missionpilot_dashboard_and_terminal.jpg",
                "19 Oct 2026, 21:37",
                "Dashboard",
                "6.4",
            ],
            [
                "assembly_07 ... bench_wiring_test.jpeg",
                "19 Oct 2026",
                "Bench wiring",
                "6.4",
            ],
            [
                "assembly_08 ... electronics_placement.jpeg",
                "19 Oct 2026",
                "Dry-fit",
                "6.4",
            ],
            ["assembly_09 ... side_view.jpeg", "20 Oct 2026", "Two-tier stack", "6.5"],
            ["assembly_10 ... top_view.jpeg", "20 Oct 2026", "Two-tier top", "6.5"],
            [
                "assembly_11 ... bottom_wiring_routing.jpeg",
                "20 Oct 2026",
                "Underside routing",
                "6.5",
            ],
            [
                "test_esp32cam_wifi_stream_mobile_01.jpg",
                "22 Oct 2026, 20:08:20",
                "Wi-Fi stream",
                "6.6",
            ],
            [
                "test_esp32cam_wifi_stream_mobile_02.jpg",
                "22 Oct 2026, 20:08:48",
                "Low light",
                "6.6",
            ],
            [
                "assembly_12 ... insulated_joints.jpeg",
                "23 Oct 2026",
                "Insulated joints",
                "6.7",
            ],
            [
                "hw_tb6612fng_motor_driver_top.jpg",
                "26 Oct 2026, 19:08:57",
                "TB6612FNG top",
                "5.3, 6.8",
            ],
            [
                "hw_tb6612fng_motor_driver_pinout.jpg",
                "26 Oct 2026, 19:09:04",
                "TB6612FNG pinout",
                "5.3, 6.8",
            ],
            [
                "assembly_13 ... damaged_shortcircuited.jpeg",
                "26 Oct 2026, after 20:14",
                "Damaged terminal",
                "6.8, 11.1",
            ],
        ],
        widths=[2.3, 1.25, 1.55, 0.85],
        caption="Photographic index with dates and report locations.",
        font_size=7.6,
    )


def appendix_tests(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Appendix D", "Test Summary")
    add_body(
        doc,
        "The test summary records the checks that were run and the evidence that supports each "
        "result. The host suite contains 311 passing tests; the table groups them by area "
        "rather than listing every case.",
    )
    add_table(
        doc,
        ["Area", "What is checked", "Evidence", "Result"],
        [
            [
                "Decision logic",
                "Zone boundaries, deadband, no-target stop",
                "Unit tests",
                "Pass",
            ],
            [
                "Safety manager",
                "Confidence, distance, camera health, link age",
                "Unit tests",
                "Pass",
            ],
            [
                "Protocol",
                "Valid commands, invalid bytes, telemetry format",
                "Unit + integration",
                "Pass",
            ],
            [
                "Watchdog",
                "3 s expiry, reset on valid command",
                "Unit + simulation",
                "Pass",
            ],
            [
                "Ultrasonic gate",
                "15 cm refusal, timeout handling",
                "Unit + simulation",
                "Pass",
            ],
            ["Logging", "CSV schema, timestamp monotonicity", "Integration", "Pass"],
            [
                "Detector",
                "Recall, precision, F1, mAP, latency",
                "Benchmark JSON",
                "Measured",
            ],
            ["Event log", "Ten invariants, zero violations", "logs/eval.json", "Pass"],
            ["Firmware build", "Arduino and ESP32 compile", "arduino-cli", "Pass"],
            [
                "Hardware",
                "Continuity, voltage, motor direction, stop",
                "Bench",
                "Partial",
            ],
        ],
        widths=[1.3, 2.3, 1.4, 0.9],
        caption="Test summary by area.",
        font_size=8.2,
    )
    add_body(
        doc,
        "The hardware row is marked partial because the final TB6612FNG build has not completed "
        "the full campaign. The continuity and voltage checks were performed, and the motor "
        "direction was verified on the bench, but the runtime, current, and stopping-distance "
        "tests remain pending. This is the main open item before the rover can be described as "
        "fully characterised.",
    )


def appendix_repository(doc: Document, assets: dict[str, Path]) -> None:
    add_chapter(doc, "Appendix E", "Repository Map and Reproduction Notes")
    add_body(
        doc,
        "The repository is organised so that the report, the firmware, the host software, the "
        "tests, and the evidence can be found without guessing. The table below is a map, not "
        "an exhaustive listing.",
    )
    add_table(
        doc,
        ["Path", "Contents"],
        [
            ["arduino/rover_controller/", "Arduino safety and motor firmware"],
            ["esp32/camera_stream/", "ESP32-CAM MJPEG firmware"],
            ["src/", "Host perception, decision, safety, and dashboard code"],
            ["tests/", "Unit, integration, and end-to-end tests"],
            ["config/", "YAML configuration for camera, model, thresholds, and serial"],
            ["logs/", "Event logs and benchmark JSON evidence"],
            ["figures/", "Architecture, wiring, and chart images"],
            ["images/", "Component, assembly, and telemetry photographs"],
            ["docs/", "Technical notes, build guide, pin map, and failure analysis"],
            ["tools/", "Report generation and utility scripts"],
            ["reports/", "Generated DOCX/PDF reports and processed assets"],
        ],
        widths=[2.2, 4.0],
        caption="Repository map for reproduction and review.",
        font_size=8.4,
    )
    add_body(
        doc,
        "To reproduce the report, run `py -3.12 tools/generate_story_report.py` from the "
        "repository root, then open the generated DOCX in Word and update the table of "
        "contents, list of figures, and list of tables. The PDF is exported from the updated "
        "DOCX. The images are resized into `reports/assets/` so that the DOCX does not depend "
        "on the original file locations.",
    )
    add_callout(
        doc,
        "Reproduction checklist",
        "1. Confirm the Python 3.12 environment has python-docx, Pillow, matplotlib, and numpy. "
        "2. Confirm the source images and benchmark JSON files are present. 3. Run the report "
        "generator. 4. Update the Word fields. 5. Export the PDF. 6. Verify the page count, "
        "figure numbering, and table numbering.",
    )


def main() -> None:
    doc = Document()
    style_document(doc)

    assets = prepare_assets()
    assets.update(make_charts())

    build_cover(doc, assets)
    build_certificate(doc, assets)
    build_front_matter(doc, assets)

    new_section(doc, "decimal", 1, SHORT_TITLE)
    chapter_introduction(doc, assets)
    chapter_problem(doc, assets)
    chapter_literature(doc, assets)
    chapter_architecture(doc, assets)
    chapter_components(doc, assets)
    chapter_build(doc, assets)
    chapter_power(doc, assets)
    chapter_software(doc, assets)
    chapter_control(doc, assets)
    chapter_results(doc, assets)
    chapter_incident(doc, assets)
    chapter_discussion(doc, assets)
    chapter_conclusion(doc, assets)
    chapter_references(doc, assets)
    appendix_bom(doc, assets)
    appendix_pinmap(doc, assets)
    appendix_photo_index(doc, assets)
    appendix_tests(doc, assets)
    appendix_repository(doc, assets)

    REPORTS.mkdir(parents=True, exist_ok=True)
    doc.save(DOCX_PATH)
    print(f"Wrote {DOCX_PATH}")


if __name__ == "__main__":
    main()
