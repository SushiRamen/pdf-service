import argparse
import fitz  # PyMuPDF
import re
import sys

def parse_rect(rect_str):
    """Parses a string like 'Rect(335.7, 615.9, 516.2, 648.2)' into a fitz.Rect."""
    match = re.search(r"Rect\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)", rect_str)
    if not match:
        raise ValueError(f"Invalid rect format: '{rect_str}'. Expected 'Rect(x0, y0, x1, y1)'")
    
    x0, y0, x1, y1 = map(float, match.groups())
    return fitz.Rect(x0, y0, x1, y1)

def find_text_in_page(pdf_path, page_num, text_to_find):
    """
    Finds specific text in a PDF page and prints its exact bounding box (Rect) with no padding.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF '{pdf_path}': {e}")
        sys.exit(1)

    try:
        page = doc.load_page(page_num)
    except Exception as e:
        print(f"Error loading page {page_num}: {e}")
        sys.exit(1)
        
    rects = page.search_for(text_to_find)
    if not rects:
        print(f"Text '{text_to_find}' not found on page {page_num}.")
    else:
        for r in rects:
            # PyMuPDF search_for returns a fitz.Rect with the exact bounding box.
            print(f"Rect({r.x0}, {r.y0}, {r.x1}, {r.y1})")
            
    doc.close()

def extract_rect_image(pdf_path, page_num, rect_str, output_path="output.png", zoom=2.0):
    """
    Extracts a region of a PDF page defined by a Rect string and saves it as a PNG.
    """
    print(f"Opening PDF: {pdf_path}")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF '{pdf_path}': {e}")
        sys.exit(1)

    print(f"Loading page: {page_num} (0-indexed)")
    try:
        page = doc.load_page(page_num)
    except Exception as e:
        print(f"Error loading page {page_num}: {e}")
        sys.exit(1)

    try:
        rect = parse_rect(rect_str)
        print(f"Parsed Rect: {rect}")
    except ValueError as e:
        print(e)
        sys.exit(1)

    # Use a matrix to render at a higher resolution (e.g. 2x)
    mat = fitz.Matrix(zoom, zoom)
    
    try:
        print(f"Rendering rect {rect} to {output_path}...")
        # Get pixmap using the parsed rect as the clip boundary
        pix = page.get_pixmap(matrix=mat, clip=rect)
        pix.save(output_path)
        print(f"Successfully saved extracted image to {output_path}")
    except Exception as e:
        print(f"Error extracting image: {e}")
        sys.exit(1)
    finally:
        doc.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Debugger: Extract images from rects or find text rects on a page.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("page_num", type=int, help="Page number (0-indexed, where 0 is the first page)")
    parser.add_argument("target", help="Rect string like 'Rect(x0,y0,x1,y1)' or text to find (if --find-text is used)")
    
    parser.add_argument("--find-text", action="store_true", help="If provided, 'target' is treated as text to find and the script returns its Rect")
    parser.add_argument("-o", "--output", default="output.png", help="Output PNG file path (default: output.png) if extracting image")
    parser.add_argument("-z", "--zoom", type=float, default=2.0, help="Zoom factor for higher resolution rendering (default: 2.0) if extracting image")

    args = parser.parse_args()

    if args.find_text:
        find_text_in_page(args.pdf_path, args.page_num, args.target)
    else:
        extract_rect_image(args.pdf_path, args.page_num, args.target, args.output, args.zoom)
