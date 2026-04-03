import fitz, json

doc = fitz.open("/mnt/c/Users/aksha/Documents/GitHub/pdf-service/resources/pdf_templates/wa_storage_lease.pdf")
fields = []
for page_num, page in enumerate(doc):
    for w in page.widgets():
        fields.append({"page": page_num, "name": w.field_name, "rect": list(w.rect)})

print(json.dumps(fields, indent=2))
print(f"\nTotal widgets: {len(fields)}")
sig = [f for f in fields if f["name"] == "Signature.Here"]
print(f"Signature.Here widgets: {len(sig)}")
for s in sig:
    print(s)
