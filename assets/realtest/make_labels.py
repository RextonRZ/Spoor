"""Three A6 shipping labels on one A4 page for the real-footage test (fictional CONTOH Express; fake numbers).
    uv run --with reportlab python assets/realtest/make_labels.py  ->  assets/realtest/labels.pdf"""
from pathlib import Path

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).with_name("labels.pdf")
LABELS = [("CTX900000000101", "A", "Box A (look-alike pair)"), ("CTX900000000102", "B", "Box B (look-alike pair)"),
          ("CTX900000000103", "C", "Box C (different)")]
W, H = 105 * mm, 148 * mm  # A6 portrait
SLOTS = [(0, A4[1] - H), (W, A4[1] - H), (0, A4[1] - 2 * H)]  # three A6 on A4, cut on the grey lines

c = canvas.Canvas(str(OUT), pagesize=A4)
c.setTitle("Spoor real-footage test labels")
for (num, box, note), (x, y) in zip(LABELS, SLOTS, strict=True):
    c.setStrokeGray(0.75); c.setLineWidth(0.4); c.rect(x, y, W, H)
    p = 7 * mm
    c.setFillGray(0); c.setFont("Helvetica-Bold", 20); c.drawString(x + p, y + H - p - 16, "CONTOH Express")
    c.setFont("Helvetica", 8); c.drawString(x + p, y + H - p - 27, "Fictional courier for a product test. Not a real shipment.")
    c.setLineWidth(1.2); c.setStrokeGray(0); c.line(x + p, y + H - p - 33, x + W - p, y + H - p - 33)
    c.setFont("Helvetica", 9)
    for i, line in enumerate(["FROM  Spoor test bench, Kuala Lumpur", "TO    Klang Valley hub (test)", "SERVICE  Standard parcel"]):
        c.drawString(x + p, y + H - p - 47 - i * 12, line)
    bc = code128.Code128(num, barHeight=26 * mm, barWidth=0.42 * mm, humanReadable=False)
    bc.drawOn(c, x + (W - bc.width) / 2, y + 46 * mm)
    c.setFont("Helvetica-Bold", 19); c.drawCentredString(x + W / 2, y + 36 * mm, num)
    c.setFont("Helvetica-Bold", 64); c.drawString(x + p, y + 8 * mm, box)
    c.setFont("Helvetica", 9); c.drawString(x + p + 52, y + 16 * mm, note)
    c.drawString(x + p + 52, y + 10 * mm, "Label facing UP, toward the camera")
c.setFont("Helvetica", 8); c.setFillGray(0.4)
c.drawString(W + 7 * mm, A4[1] - 2 * H + 20 * mm, "Print at 100% (no 'fit to page'). Cut on the grey lines.")
c.drawString(W + 7 * mm, A4[1] - 2 * H + 14 * mm, "Tape one label on top of each box.")
c.showPage(); c.save()
print(OUT)
