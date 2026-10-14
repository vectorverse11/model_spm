"""
Stub column test — figures shared by the page and the PDF report.

    section_figure(inp, r)   upright profile with the y–z axes and the CG
    axial_figure(r)          axial load vs axial displacement
    build_report(...)        PDF report (with or without the graph) as bytes
"""

import io
import os
from datetime import date

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from stub import E, nodes

NAVY = "#1f3a5f"
GREEN = "#1e7b45"
SOFT = "#f3f6f9"
LINE = "#c9d3de"


# ---------------------------------------------------------------- figures

def section_figure(inp, r):
    """Upright cross-section with the y-y / z-z axes and the CG (web on the right)."""
    P = nodes(inp)
    xs, zs = -(P[:, 0]), P[:, 1]                     # y positive to the left (towards lips)
    fig, ax = plt.subplots(figsize=(5, 4.6))
    ax.plot(xs, zs, "-", color=NAVY, lw=max(2.5, inp.t * 2.2), solid_capstyle="butt")
    yc = -r["x_cg"]
    span = max(abs(xs).max(), abs(zs).max()) * 1.35
    arrow = dict(arrowstyle="-|>", lw=1.2, color="#333")
    ax.annotate("", xy=(yc - span * 0.75, 0), xytext=(yc + span * 0.75, 0), arrowprops=arrow)
    ax.annotate("", xy=(yc + span * 0.75, 0), xytext=(yc, 0), arrowprops=arrow)
    ax.annotate("", xy=(yc, span * 0.8), xytext=(yc, -span * 0.8), arrowprops=arrow)
    ax.annotate("", xy=(yc, -span * 0.8), xytext=(yc, 0), arrowprops=arrow)
    ax.text(yc - span * 0.78, span * 0.05, "y (+)", ha="right", fontsize=10)
    ax.text(yc + span * 0.78, span * 0.05, "y (−)", ha="left", fontsize=10)
    ax.text(yc + span * 0.04, span * 0.82, "z", fontsize=11)
    ax.text(yc + span * 0.04, -span * 0.88, "z", fontsize=11)
    ax.plot(yc, 0, "o", ms=11, mfc="none", mec="#d62728", mew=2)
    ax.plot(yc, 0, "o", ms=3, color="#d62728")
    ax.annotate(f"C.G.\ny_CG = {r['x_cg']:.2f} mm\n"
                f"({'user value' if r['cg_custom'] else 'calculated'})",
                xy=(yc, 0), xytext=(yc - span * 0.95, span * 0.55), fontsize=9,
                color="#d62728", arrowprops=dict(arrowstyle="-", color="#d62728", lw=1))
    ax.annotate("", xy=(yc, -span * 0.55), xytext=(0, -span * 0.55),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color="#d62728"))
    ax.text(yc / 2, -span * 0.62, f"{r['x_cg']:.2f}", ha="center", fontsize=8, color="#d62728")
    ax.text(span * 0.06, -zs.max() * 0.5, "web", rotation=90, va="center", fontsize=8,
            color="#555")
    ax.set_aspect("equal")
    ax.set_xlim(yc - span, yc + span)
    ax.set_ylim(-span, span)
    ax.axis("off")
    ax.set_title("Upright section — axes and CG", fontsize=10)
    return fig


def axial_figure(r, figsize=(7, 4.6)):
    """Axial load vs axial displacement up to the failure load."""
    rows = r["rows"]
    N_kN = np.array([x["N"] for x in rows]) / 1000
    delta = np.array([x["delta"] for x in rows])
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(delta, N_kN, "-", lw=2, color="#1f77b4")
    ax.plot(delta[-1], N_kN[-1], "o", color="#d62728")
    ax.annotate(f"Failure {N_kN[-1]:.2f} kN", (delta[-1], N_kN[-1]), textcoords="offset points",
                xytext=(-90, 8), fontsize=8, color="#d62728")
    ax.axhline(r["N_proof"] / 1000, color="grey", lw=0.8, ls=":")
    ax.text(delta[-1] * 0.02, r["N_proof"] / 1000, "Proof load", va="bottom", fontsize=8,
            color="grey")
    ax.set(xlabel="Axial displacement δ (mm)", ylabel="Axial load N (kN)",
           title="Axial Load vs Axial Displacement", xlim=(0, delta[-1] * 1.08),
           ylim=(0, N_kN[-1] * 1.12))
    ax.grid(alpha=0.3)
    return fig


def _png(fig, dpi=200):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- PDF report

def _scaled(buf, width):
    """Image flowable at the given width, keeping the PNG aspect ratio."""
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=width, height=width * h / w)


_FONTS_READY = False


def _fonts():
    global _FONTS_READY
    if not _FONTS_READY:
        d = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        pdfmetrics.registerFont(TTFont("RPT", os.path.join(d, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("RPT-B", os.path.join(d, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("RPT", normal="RPT", bold="RPT-B", italic="RPT",
                                      boldItalic="RPT-B")
        _FONTS_READY = True


def _table(rows, widths, header=True, zebra=True, size=9):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    st = [("FONT", (0, 0), (-1, -1), "RPT", size),
          ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#22313f")),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(LINE)),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("FONT", (0, 0), (-1, 0), "RPT-B", 9)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(SOFT)))
    t.setStyle(TableStyle(st))
    return t


def input_rows(inp, r, grade, cg_mode, ecc=None, column=False):
    """(group, parameter, value) for every value the user gave on the page."""
    alt_name = {1: "Alternative 1 — ball bearings", 2: "Alternative 2 — clamped platen",
                3: "Alternative 3 — CUFSM + DSM"}[inp.alternative]
    rows = [
        ("Specimen", "Width W (web)", f"{inp.W:g} mm"),
        ("Specimen", "Depth D (flange)", f"{inp.D:g} mm"),
        ("Specimen", "Thickness t", f"{inp.t:g} mm"),
        ("Specimen", "Lip length", f"{inp.lip:g} mm"),
        *([("Specimen", "Length L1 (between plates)", f"{inp.c:g} mm"),
           ("Specimen", "L = L1 + 2a + 2b", f"{r['b']:g} mm")] if column else
          [("Specimen", "Length c (cold-formed section)", f"{inp.c:g} mm")]),
        ("Centre of Gravity", "Method", cg_mode),
        ("Centre of Gravity", "y_CG from web centreline", f"{r['x_cg']:.3f} mm"),
        ("Perforations", "Pitch", f"{inp.pitch:g} mm"),
        ("Perforations", "Holes across the web / width", f"{inp.n_web} × {inp.d_web:g} mm"),
        ("Perforations", "Holes across each flange / width", f"{inp.n_fl} × {inp.d_fl:g} mm"),
        ("Cap plate (a)", "Depth × width × thickness",
         f"{inp.cap_L:g} × {inp.cap_W:g} × {inp.cap_t:g} mm"),
        ("Base plate (b)", "Depth × width × thickness",
         f"{inp.base_L:g} × {inp.base_W:g} × {inp.base_t:g} mm"),
        ("Material", "Grade designation", grade),
        ("Material", "Yield stress f_y", f"{inp.fy:g} N/mm²"),
        ("Material", "γ_M0", f"{inp.gamma_M0:g}"),
        ("Test", "Arrangement / method", alt_name),
    ]
    if inp.alternative == 3:
        rows.append(("Test", "Distortional buckling in strength",
                     "included" if inp.distortional else "not included"))
    rows += [("Test", "Dial gauge least count", f"{inp.least_count:g} mm/div")]
    if ecc is not None:
        rows.append(("Test", "Eccentricity e from CG", f"{ecc['e']:g} mm"))
    return rows


def build_report(inp, r, client, grade, cg_mode, increment, ecc=None, with_graph=True,
                 column=False) -> bytes:
    _fonts()
    buf = io.BytesIO()
    W_page, H_page = A4
    margin = 16 * mm
    content_w = W_page - 2 * margin

    title = ParagraphStyle("t", fontName="RPT-B", fontSize=20, leading=24,
                           textColor=colors.white)
    sub = ParagraphStyle("s", fontName="RPT", fontSize=9, leading=12,
                         textColor=colors.HexColor("#dbe6f1"))
    h2 = ParagraphStyle("h2", fontName="RPT-B", fontSize=11.5, leading=15,
                        textColor=colors.HexColor(NAVY), spaceBefore=10, spaceAfter=5)
    body = ParagraphStyle("b", fontName="RPT", fontSize=9, leading=12.5,
                          textColor=colors.HexColor("#22313f"), alignment=TA_LEFT)
    small = ParagraphStyle("sm", parent=body, fontSize=7.8, leading=10,
                           textColor=colors.HexColor("#5b6b7b"))

    story = []
    # ---- header band
    name = "Column Buckling Test Report" if column else "Stub Column Test Report"
    head = Table([[Paragraph(name, title)],
                  [Paragraph("Virtual compression test of a perforated rack upright · "
                             "EN 15512 Annex A.2.1"
                             + (" · buckling lengths L/2, L = L1 + 2a + 2b" if column else ""), sub)]],
                 colWidths=[content_w])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(NAVY)),
                              ("LEFTPADDING", (0, 0), (-1, -1), 12),
                              ("TOPPADDING", (0, 0), (0, 0), 12),
                              ("BOTTOMPADDING", (0, -1), (-1, -1), 11)]))
    story += [head, Spacer(1, 8)]

    meta = _table([["Client", client or "—", "Date", date.today().strftime("%d %b %Y")],
                   ["Test", {1: "Alternative 1", 2: "Alternative 2",
                             3: "Alternative 3 (CUFSM + DSM)"}[inp.alternative],
                    "Load step", f"{increment:g} kN"]],
                  [24 * mm, content_w / 2 - 24 * mm, 24 * mm, content_w / 2 - 24 * mm],
                  header=False, zebra=False)
    meta.setStyle(TableStyle([("FONT", (0, 0), (0, -1), "RPT-B", 9),
                              ("FONT", (2, 0), (2, -1), "RPT-B", 9),
                              ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(NAVY)),
                              ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor(NAVY))]))
    story.append(meta)

    # ---- profile diagram
    story.append(Paragraph("Upright profile", h2))
    img = Image(_png(section_figure(inp, r)), width=74 * mm, height=68 * mm)
    g = r["gross"]
    prof = _table([["Property", "Value"],
                   ["Gross area A_g", f"{g['A']:.2f} mm²"],
                   ["Net area A_net", f"{r['A_net']:.2f} mm²"],
                   ["Centre of gravity y_CG", f"{r['x_cg']:.3f} mm"],
                   ["Flat widths (web/flange/lip)",
                    f"{r['widths']['web']:g} / {r['widths']['flange']:g} / "
                    f"{r['widths']['lip']:g} mm"]],
                  [50 * mm, content_w - 78 * mm - 50 * mm])
    side = Table([[img, prof]], colWidths=[78 * mm, content_w - 78 * mm])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(side)

    # ---- inputs
    story.append(Paragraph("Input parameters", h2))
    all_rows = input_rows(inp, r, grade, cg_mode, ecc, column)
    left_groups = ("Specimen", "Centre of Gravity", "Perforations")
    halves = []
    for part in ([x for x in all_rows if x[0] in left_groups],
                 [x for x in all_rows if x[0] not in left_groups]):
        rows, last = [["Group", "Parameter", "Value"]], None
        for grp, par, val in part:
            rows.append([grp if grp != last else "", Paragraph(par, ParagraphStyle(
                "c", fontName="RPT", fontSize=8, leading=9.6)), Paragraph(val, ParagraphStyle(
                    "v", fontName="RPT", fontSize=8, leading=9.6))])
            last = grp
        halves.append(_table(rows, [27 * mm, 31 * mm, content_w / 2 - 61 * mm], size=7.6))
    two = Table([halves], colWidths=[content_w / 2, content_w / 2])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 6)]))
    story.append(two)

    # ---- results
    res_rows = [["Result", "Value"],
                ["Failure load R_k", f"{r['R_k'] / 1000:.2f} kN"],
                ["Design capacity N_b,Rd = R_k / γ_M0",
                 f"{r['R_k'] / 1000:.2f} / {inp.gamma_M0:g} = {r['N_b_Rd'] / 1000:.2f} kN"]]
    if ecc is not None:
        res_rows.append([f"Eccentric failure load (e = {ecc['e']:g} mm)",
                         f"{ecc['N_ue'] / 1000:.2f} kN"])
    rt = _table(res_rows, [95 * mm, content_w - 95 * mm], zebra=False)
    rt.setStyle(TableStyle([("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e8f5ee")),
                            ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor(GREEN)),
                            ("FONT", (0, 2), (-1, 2), "RPT-B", 10),
                            ("BOX", (0, 2), (-1, 2), 1.4, colors.HexColor(GREEN)),
                            ("FONT", (1, 1), (1, 1), "RPT-B", 10)]))
    story.append(KeepTogether([Paragraph("Results", h2), rt]))

    # ---- graph
    if with_graph:
        story.append(KeepTogether([
            Paragraph("Axial load vs axial displacement", h2),
            _scaled(_png(axial_figure(r, figsize=(7.2, 4.2))), content_w),
            Paragraph(f"Shortening δ = N·{'L1' if column else 'c'} / (E·A_eff(σ)) with "
                      f"{'L1' if column else 'c'} = {inp.c:g} mm and "
                      f"E = {E:,.0f} N/mm²; the curve ends at the failure load.", small)]))

    story += [Spacer(1, 10),
              Paragraph("Virtual test — results are calculated from the entered geometry and "
                        "material (effective width method / Direct Strength Method) and do not "
                        "replace a physical test.", small)]

    def footer(c, d):
        c.saveState()
        c.setStrokeColor(colors.HexColor(LINE))
        c.line(margin, 11 * mm, W_page - margin, 11 * mm)
        c.setFont("RPT", 7.5)
        c.setFillColor(colors.HexColor("#7b8a99"))
        c.drawString(margin, 7 * mm, f"Virtual SPM · {name}")
        c.drawRightString(W_page - margin, 7 * mm, f"Page {d.page}")
        c.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin,
                      topMargin=14 * mm, bottomMargin=16 * mm,
                      title=name, author="Virtual SPM").build(
        story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
