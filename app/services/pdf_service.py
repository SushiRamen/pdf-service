import fitz  # PyMuPDF
import base64
import os

class PDFService:
    @staticmethod
    def overlay_signature(input_pdf_path: str, output_pdf_path: str, base64_image_data: str) -> str:
        """
        Overlays a base64 signature image onto the bottom-right corner of the last page of the PDF.
        """
        # Strip header if it's a data URL (e.g. data:image/png;base64,...)
        if "," in base64_image_data:
            base64_image_data = base64_image_data.split(",")[1]
            
        image_bytes = base64.b64decode(base64_image_data)
        
        doc = fitz.open(input_pdf_path)
        last_page = doc[-1]  # Get the last page
        
        page_width = last_page.rect.width
        page_height = last_page.rect.height
        
        # Dimensions for a 4:1 ratio signature box (e.g., 200x50)
        sig_width = 200
        sig_height = 50
        
        # Padding from edges
        margin_x = 50
        margin_y = 50
        
        # Calculate position for bottom right
        x0 = page_width - sig_width - margin_x
        y0 = page_height - sig_height - margin_y
        x1 = x0 + sig_width
        y1 = y0 + sig_height
        
        rect = fitz.Rect(x0, y0, x1, y1)
        
        last_page.insert_image(rect, stream=image_bytes)
        
        doc.save(output_pdf_path)
        doc.close()
        
        return output_pdf_path
