# PDF Signing Service

A lightweight, self-hosted e-signature service built with **FastAPI + PyMuPDF + SQLite**. Designed to integrate as a node in an **n8n** lease-signing workflow.

## How It Works

1. **n8n** POSTs a PDF + metadata to `POST /api/v1/documents/create` (API Key protected).
2. The service saves the PDF, creates a DB record with a unique UUID token, and returns a `signing_url`.
3. n8n emails the signing link to the client.
4. The client opens the signing URL in their browser:
   - The PDF is rendered via **pdf.js**.
   - The client draws their signature on a canvas.
   - A **"SIGN HERE"** box is overlaid at the bottom-right of the last PDF page.
   - The client clicks the box to "place" their signature.
   - The **Complete** button is only enabled when both steps are done.
5. On completion, **PyMuPDF** overlays the signature image onto the PDF and saves it.
6. The client is redirected to a success page with a download link.

---

## API Reference

### `POST /api/v1/documents/create`
**Auth:** `X-API-Key` header required.  
**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | PDF binary | ✅ | The PDF to be signed |
| `signer_email` | string | ❌ | Email of the person signing |
| `completion_emails` | JSON string | ❌ | Array of emails to receive signed PDF e.g. `["a@b.com"]` |

**Postman example:**  
- Body → form-data  
- `file` → select PDF file  
- `signer_email` → `tenant@example.com`  
- `completion_emails` → `["landlord@example.com","agent@example.com"]`

**Response:**
```json
{
  "id": "uuid",
  "signing_url": "https://your-domain.com/sign/<uuid>",
  "expires_at": "2026-04-08T...",
  "status": "pending"
}
```

---

### `GET /sign/{token}`
Public. Serves the signing page (pdf.js + signature pad).

### `POST /sign/{token}/submit`
Public. Accepts `{ "signature_data": "data:image/png;base64,..." }`, overlays signature on PDF, marks document as signed.

### `GET /sign/download/{token}`
Public. Downloads the signed PDF.

### `GET /api/v1/document/{token}`
Public. Returns document metadata (status, expiry, pdf URL).

### `GET /api/v1/document/{token}/pdf`
Public. Streams the original PDF — used by pdf.js on the signing page.

---

## Configuration

Copy `.env.example` to `.env` and fill in:

```env
API_KEY=your_secure_random_key
BASE_URL=https://your-domain.com
DATABASE_URL=sqlite+aiosqlite:///./data.db
UPLOAD_DIR=./uploads
SIGNED_DIR=./signed
```

---

## Running Locally

```bash
# From repo root — app/ is the package, main.py is the entry point
cd app
uvicorn main:app --reload --port 8000
```

Or from the repo root if PYTHONPATH is set:
```bash
cd app && uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Deploying to Render.com

1. Create a new **Web Service**, connect your GitHub repo.
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `cd app && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add a **Persistent Disk** mounted at `/data` and set:
   - `UPLOAD_DIR=/data/uploads`
   - `SIGNED_DIR=/data/signed`
   - `DATABASE_URL=sqlite+aiosqlite:////data/data.db`
5. Set all env vars in the Render dashboard.

---

## Project Structure

```
pdf-service/
├── app/
│   ├── main.py                        # FastAPI app, lifespan, routers
│   ├── api/
│   │   └── endpoints/
│   │       ├── n8n.py                 # POST /api/v1/documents/create (API-key protected)
│   │       ├── documents.py           # GET /api/v1/document/{token} (public)
│   │       └── signing.py            # GET+POST /sign/{token} (public)
│   ├── core/
│   │   ├── config.py                  # Pydantic settings
│   │   ├── security.py               # X-API-Key dependency
│   │   └── limiter.py                # Centralised slowapi Limiter
│   ├── db/
│   │   ├── database.py               # Async SQLAlchemy engine + session
│   │   ├── models.py                 # Document SQLAlchemy model
│   │   └── schemas.py                # Pydantic request/response schemas
│   ├── services/
│   │   ├── document_service.py       # CRUD + sign orchestration
│   │   └── pdf_service.py            # PyMuPDF signature overlay
│   └── templates/
│       ├── sign.html                 # Signing page (pdf.js + signature canvas)
│       ├── success.html              # Post-signing success page
│       └── expired.html              # Expired link page
├── requirements.txt
├── .env.example
└── README.md
```

---

## TODO / Future Enhancements

### Email on Completion
- [ ] Add `email_service.py` using `aiosmtplib` (or Brevo/Mailgun via `httpx`)
- [ ] Add SMTP env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL`
- [ ] In `signing.py → submit_signature`: after `sign_document()`, call email service to send signed PDF to all `completion_emails`
- [ ] Optionally email the signer a copy too

### n8n Completion Webhook
- [ ] Add `N8N_WEBHOOK_URL: str = ""` to `core/config.py`
- [ ] After signing, POST `{"document_id": ..., "status": "signed", "signed_pdf_url": ...}` to `N8N_WEBHOOK_URL` using `httpx.AsyncClient`
- [ ] Handle failures gracefully (log, don't crash)

### Signature Fields (Multi-Box Signing)
- [ ] Add `signature_fields: JSON` column to `Document` model (list of `{x, y, w, h, page}` dicts)
- [ ] Accept `signature_fields` as a JSON Form param in `POST /documents/create`
- [ ] Expose fields via `GET /api/v1/document/{token}` response
- [ ] In `sign.html`, read fields from API and overlay clickable boxes on correct pdf.js pages
- [ ] Gate Complete button behind all fields being signed
- [ ] In `pdf_service.py`, overlay signature into each field rect instead of hardcoded corner

### Deployment
- [ ] Add `Procfile`: `web: cd app && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Add `render.yaml` for one-click Render deploy
- [ ] Add `Dockerfile` for container-based deploy

### Security Hardening
- [ ] Set explicit `allow_origins` in CORS middleware (not `["*"]`) for production
- [ ] Add token expiry check to `GET /api/v1/document/{token}/pdf`
- [ ] Serve PDFs with signed URL / short-lived token instead of raw token

### UX / Polish
- [ ] Progress indicator showing which pages have been reviewed
- [ ] Mobile-responsive layout improvements
- [ ] Typed signature option (in addition to drawn)


'''
GREAT. THIS WORKS AWESOMELY.

Now i need phase 2 plan. 

create a resources/pdf_templates that will contain raw_pdf templates. That way no one will be required to send the pdf. 

How the create-document endpoint changes : 
1. POST request will contain 
a) template_name
b) template_parameters(key_value)
There will be several required key-value pairs that will already be checked by the front-end. 
'''