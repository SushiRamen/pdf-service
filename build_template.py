"""
build_template.py — Run ONCE (or after any change to the source PDF).

Pipeline (single in-memory pass, one save):
  1. Open the ORIGINAL source PDF (never modified)
  2. Repair & clean xref table
  3. Inject Signature.Here text at the occupant signature line
  4. Add AcroForm widgets (centered, white-background) over every placeholder
  5. Save to resources/pdf_templates/wa_storage_lease.pdf

Usage (from repo root):
    python3 build_template.py
"""

import os
import sys
import fitz  # PyMuPDF

SOURCE_PDF = "/mnt/c/Users/aksha/Downloads/wa_storage_lease.pdf"        # original — never modified
OUTPUT_PDF = "resources/pdf_templates/wa_storage_lease.pdf"

SIGNATURE_FIELD = "Signature.Here"

# ── Padding: (left, top, right, bottom) in PDF points ───────────────────────
# ~5pt per average char at 9pt Helvetica  →  10 chars ≈ 50pt, 20 chars ≈ 100pt
FIELD_PADDING = {
    SIGNATURE_FIELD:                   (0,  10, 120, 10),
    # Facility.Name is position-based — see POSITION_BASED_PADDING below
    "Facility.Address1":               (0,  2,  30,  2),
    "Facility.City":                   (0,  2,  30,  2),
    "Facility.Phone":                  (0,  2,  10,  2),
    # Tenant: 20-char right pad
    "Tenant.Name":                     (0,   2, 100,  2),
    "Tenant.Address1Tenant.Address2":  (0,   2, 100,  2),
    "Tenant.Address1":                 (0,   2, 100,  2),
    "Tenant.City":                     (0,   2, 100,  2),
    "Tenant.Email":                    (0,   2, 100,  2),
    # Tenant / Space: 10-char right pad
    "Tenant.DLNumber":                 (0,   2,  50,  2),
    "Space.ID":                        (0,   2,  50,  2),
    "Space.Rent":                      (0,   2,  50,  2),
    # Multi-line fields — extra vertical room
    "Tenant.ActiveMilitary":           (0,   2,  50, 10),
    "Tenant.LienHolderDetails":        (0,   2,  50, 10),
}
DEFAULT_PADDING = (1, 1, 1, 1)

# Position-based padding: rules are checked top-to-bottom by rect.y0;
# first match wins. Falls back to "default" if none match.
POSITION_BASED_PADDING = {
    "Facility.Name": {
        "rules": [
            # Heading at top of page (company name block)
            {"y_max": 150, "padding": (0, 2, 50, 2)},
        ],
        # Inline body text e.g. "Facility.Name d/b/a ..." — minimal padding
        "default": DEFAULT_PADDING,
    },
}

# ── Max character lengths per field ─────────────────────────────────────────
MAX_LEN = {
    "Facility.Name": 50, "Facility.Address1": 50, "Facility.City": 30,
    "Facility.State": 2, "Facility.PostalCode": 10, "Facility.Phone": 20,
    "Facility.SalesTax": 10, "Facility.AdminFee": 15,
    "Tenant.Name": 40,
    "Tenant.Address1Tenant.Address2": 70,
    "Tenant.Address1": 35, "Tenant.Address2": 35,
    "Tenant.City": 30, "Tenant.State": 2, "Tenant.PostalCode": 10,
    "Tenant.HomePhone": 20, "Tenant.CellPhone": 20,
    "Tenant.Email": 50, "Tenant.SSN": 15, "Tenant.DLNumber": 20,
    "Tenant.DLState": 2, "Tenant.RentDueDate": 5,
    "Tenant.AltName": 40,
    "Tenant.AltAddress1Tenant.AltAddress2": 70,
    "Tenant.AltAddress1": 35, "Tenant.AltAddress2": 35,
    "Tenant.AltCity": 30,
    "Tenant.AltStateTenant.AltPostalCode": 15,
    "Tenant.AltState": 2, "Tenant.AltPostalCode": 10, "Tenant.AltEmail": 50,
    "Tenant.ActiveMilitary": 120, "Tenant.LienHolderDetails": 200,
    "Space.ID": 10, "Space.Rent": 15,
    "Document.Date": 30, SIGNATURE_FIELD: 30,
}
DEFAULT_MAX = 20

# Compounds must come before their component strings so the longer match
# is placed first and the overlap-check skips the shorter sub-matches.
PLACEHOLDERS = [
    "Tenant.AltAddress1Tenant.AltAddress2",
    "Tenant.AltStateTenant.AltPostalCode",
    "Tenant.Address1Tenant.Address2",
    "Facility.Name", "Facility.Address1", "Facility.City", "Facility.State",
    "Facility.PostalCode", "Facility.Phone", "Facility.SalesTax", "Facility.AdminFee",
    "Tenant.Name", "Tenant.Address1", "Tenant.Address2",
    "Tenant.City", "Tenant.State", "Tenant.PostalCode",
    "Tenant.HomePhone", "Tenant.CellPhone", "Tenant.Email",
    "Tenant.SSN", "Tenant.DLNumber", "Tenant.DLState", "Tenant.RentDueDate",
    "Tenant.AltName", "Tenant.AltAddress1", "Tenant.AltAddress2",
    "Tenant.AltCity", "Tenant.AltState", "Tenant.AltPostalCode", "Tenant.AltEmail",
    "Tenant.ActiveMilitary", "Tenant.LienHolderDetails",
    "Space.ID", "Space.Rent",
    "Document.Date",
    SIGNATURE_FIELD,
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_font_size(page, rect, fallback=9.0):
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if fitz.Rect(span["bbox"]).intersects(rect):
                    return span["size"]
    return fallback


def overlaps(rect, covered):
    for c in covered:
        inter = rect & c
        if not inter.is_empty and inter.get_area() > 0.5 * rect.get_area():
            return True
    return False


def padded(rect, placeholder):
    """Expand rect by the appropriate padding for this placeholder.
    POSITION_BASED_PADDING takes priority over FIELD_PADDING."""
    if placeholder in POSITION_BASED_PADDING:
        spec = POSITION_BASED_PADDING[placeholder]
        chosen = spec["default"]
        for rule in spec["rules"]:
            if rect.y0 < rule["y_max"]:
                chosen = rule["padding"]
                break
        pl, pt, pr, pb = chosen
    else:
        pl, pt, pr, pb = FIELD_PADDING.get(placeholder, DEFAULT_PADDING)
    return fitz.Rect(rect.x0 - pl, rect.y0 - pt, rect.x1 + pr, rect.y1 + pb)


# ── Step 1: Open & repair ────────────────────────────────────────────────────
if not os.path.exists(SOURCE_PDF):
    print(f"ERROR: source PDF not found: {SOURCE_PDF}")
    sys.exit(1)

print(f"Opening {SOURCE_PDF} …")
doc = fitz.open(SOURCE_PDF)

# Rebuild xref in-memory to eliminate any existing corruption
raw = doc.tobytes(garbage=4, deflate=True, clean=True)
doc.close()
doc = fitz.open("pdf", raw)
print(f"  {len(doc)} pages, xref cleaned.")


# ── Step 2: Inject Signature.Here ───────────────────────────────────────────
last_page = doc[-1]
existing = last_page.search_for(SIGNATURE_FIELD)

if existing:
    print(f"  '{SIGNATURE_FIELD}' already present — skipping inject.")
    sig_injected = True
else:
    sig_injected = False
    target_rect = None

    for block in last_page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if "Occupant Signature" in span["text"]:
                    b = span["bbox"]
                    target_rect = fitz.Rect(b[0], b[1] - 20, b[0] + 200, b[1] - 4)
                    break

    if target_rect is None:
        hits = last_page.search_for("_______")
        if hits:
            r = hits[0]
            target_rect = fitz.Rect(r.x0, r.y0, r.x0 + 200, r.y1)

    if target_rect is None:
        print("WARNING: could not locate signature area — Signature.Here NOT injected.")
    else:
        shape = last_page.new_shape()
        shape.draw_rect(target_rect)
        shape.finish(fill=(1, 1, 1), color=(1, 1, 1), width=0)
        shape.commit()
        last_page.insert_text(
            fitz.Point(target_rect.x0, target_rect.y1 - 2),
            SIGNATURE_FIELD,
            fontname="helv",
            fontsize=9.0,
            color=(1, 1, 1),  # white — invisible to reader, detectable by search_for
        )
        sig_injected = True
        print(f"  Injected '{SIGNATURE_FIELD}' at {target_rect}")


# ── Step 3: Add AcroForm widgets ─────────────────────────────────────────────
os.makedirs(os.path.dirname(OUTPUT_PDF), exist_ok=True)
total_widgets = 0

for page_num, page in enumerate(doc):
    covered = []

    for placeholder in PLACEHOLDERS:
        rects = page.search_for(placeholder, quads=False)
        for raw_rect in rects:
            r = padded(fitz.Rect(raw_rect), placeholder)

            if overlaps(r, covered):
                continue

            fs = get_font_size(page, fitz.Rect(raw_rect))

            w = fitz.Widget()
            w.field_type    = fitz.PDF_WIDGET_TYPE_TEXT
            w.field_name    = placeholder
            w.field_value   = ""
            w.rect          = r
            w.text_font     = "Helv"
            if placeholder == "Facility.Phone":
                w.text_fontsize = fs - 2
            else:
                w.text_fontsize = fs
            
            # --- FIXED ALIGNMENT ---
            # w.text_align  = fitz.TEXT_ALIGN_CENTER  <-- REMOVED
            if placeholder in ["Signature.Here", "Document.Date", "Space.Rent"]:
                w.text_quadding = 0  # Left align
            else:
                w.text_quadding = 1  # Center align (Fixed comment)
            
            w.fill_color    = (1, 1, 1)
            w.border_color  = None
            w.text_color    = (0, 0, 0)
            
            # --- FIXED FLAGS & MULTILINE ---
            w.field_flags   = 0
            if placeholder in ["Tenant.ActiveMilitary", "Tenant.LienHolderDetails"]:
                # 4096 is the PDF spec bit-flag for multiline text fields
                w.field_flags |= 4096
                
            w.text_maxlen   = MAX_LEN.get(placeholder, DEFAULT_MAX)

            page.add_widget(w)
            covered.append(r)
            total_widgets += 1
            print(f"  p{page_num+1}  {placeholder:45s}  {r}")


# ── Step 4: Single clean save ────────────────────────────────────────────────
tmp = OUTPUT_PDF + ".tmp"
doc.save(tmp, garbage=4, deflate=True, clean=True)
doc.close()
os.replace(tmp, OUTPUT_PDF)

print(f"\n✓ {total_widgets} widgets added → {OUTPUT_PDF}")
if not sig_injected:
    print("  WARNING: Signature.Here was NOT injected.")
