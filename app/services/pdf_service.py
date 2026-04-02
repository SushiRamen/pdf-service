import fitz  # PyMuPDF
import base64

SIGNATURE_FIELD_NAME = "Signature.Here"


class PDFService:

    # ── Signature field detection ─────────────────────────────────────────────

    @staticmethod
    def detect_signature_fields(pdf_path: str) -> list[dict]:
        """
        Finds all AcroForm widgets named 'Signature.Here' across all pages.
        Returns [{page, x0, y0, x1, y1}, ...] (page is 0-indexed).
        """
        doc = fitz.open(pdf_path)
        fields = []
        for page_num, page in enumerate(doc):
            for widget in page.widgets():
                if widget.field_name == SIGNATURE_FIELD_NAME:
                    r = widget.rect
                    fields.append({
                        "page": page_num,
                        "x0": round(r.x0, 2),
                        "y0": round(r.y0, 2),
                        "x1": round(r.x1, 2),
                        "y1": round(r.y1, 2),
                    })
        doc.close()
        return fields

    # ── Form field filling ────────────────────────────────────────────────────

    @staticmethod
    def fill_form_fields(template_path: str, output_path: str, data: dict[str, str]) -> str:
        """
        Iterates every widget in the AcroForm template and, if its field_name
        is in `data`, sets the value and calls widget.update() to regenerate
        the appearance stream.

        After filling:
        - All non-signature fields are marked read-only.
        - The Signature.Here widget is left empty (its position is used later
          for the signature image overlay).

        Runs synchronously — call via asyncio.to_thread.
        """
        doc = fitz.open(template_path)

        for page in doc:
            for widget in page.widgets():
                name = widget.field_name
                if name == SIGNATURE_FIELD_NAME:
                    # Leave blank; mark read-only so it doesn't appear as an
                    # interactive field in the browser viewer.
                    widget.field_flags = fitz.PDF_FIELD_IS_READ_ONLY
                    widget.text_align  = fitz.TEXT_ALIGN_CENTER
                    widget.update()
                    continue

                if name in data:
                    widget.field_value = data[name]
                    widget.field_flags = fitz.PDF_FIELD_IS_READ_ONLY
                    widget.text_align  = fitz.TEXT_ALIGN_CENTER
                    widget.update()

        doc.save(output_path)
        doc.close()
        return output_path

    # ── Signature image overlay ───────────────────────────────────────────────

    @staticmethod
    def overlay_signature(
        input_pdf_path: str,
        output_pdf_path: str,
        base64_image_data: str,
        signature_fields: list[dict] | None = None,
    ) -> str:
        """
        Overlays the drawn signature image at each stored signature field
        position.  Falls back to bottom-right of last page if no fields given.
        """
        if "," in base64_image_data:
            base64_image_data = base64_image_data.split(",")[1]
        image_bytes = base64.b64decode(base64_image_data)

        doc = fitz.open(input_pdf_path)

        if signature_fields:
            for field in signature_fields:
                page = doc[field["page"]]
                rect = fitz.Rect(field["x0"], field["y0"], field["x1"], field["y1"])
                page.insert_image(rect, stream=image_bytes)
        else:
            last = doc[-1]
            pw, ph = last.rect.width, last.rect.height
            rect = fitz.Rect(pw - 250, ph - 70, pw - 50, ph - 20)
            last.insert_image(rect, stream=image_bytes)

        doc.save(output_pdf_path)
        doc.close()
        return output_pdf_path
