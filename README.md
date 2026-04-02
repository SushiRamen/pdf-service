# PDF Signing Service

A lightweight, self-hosted e-signature service built with **FastAPI + PyMuPDF + SQLite**. Designed to integrate as a node in an **n8n** workflow (e.g. lease signing).

---

## How It Works

1. **n8n** POSTs a `template_name` + `template_parameters` to `POST /api/v1/documents/create` (API Key protected).
2. The service fills the PDF template with the provided parameters, falling back to per-template defaults.
3. `Signature.Here` placeholders in the PDF are detected and their page coordinates stored in the DB.
4. The service returns a `signing_url` for the client.
5. The client opens the signing URL in their browser:
   - The PDF is rendered via **pdf.js** (all pages).
   - The client draws their signature on a canvas.
   - **"SIGN HERE"** boxes are overlaid at the exact position of every `Signature.Here` placeholder in the template (can be multiple).
   - The client clicks each "SIGN HERE" field to apply their drawn signature as a preview.
   - The **Complete** button is only enabled when the signature is drawn **and** all fields have been clicked.
6. On completion, **PyMuPDF** overlays the signature image at each stored field position and saves the signed PDF.
7. The client is redirected to a success page with a download link.

---

## Project Structure

```
pdf-service/
├── app/
│   ├── main.py                          # FastAPI app entry point, lifespan, routers
│   ├── api/
│   │   └── endpoints/
│   │       ├── n8n.py                   # POST /api/v1/documents/create  (API-key protected)
│   │       ├── documents.py             # GET  /api/v1/document/{token}  (public)
│   │       └── signing.py              # GET+POST /sign/{token}          (public)
│   ├── core/
│   │   ├── config.py                   # Pydantic settings (reads from .env)
│   │   ├── security.py                 # X-API-Key dependency
│   │   └── limiter.py                  # Centralised slowapi rate limiter
│   ├── db/
│   │   ├── database.py                 # Async SQLAlchemy engine + session
│   │   ├── models.py                   # Document SQLAlchemy model
│   │   └── schemas.py                  # Pydantic request/response schemas
│   ├── services/
│   │   ├── template_service.py         # Template loading, param merging, PDF generation
│   │   ├── document_service.py         # DB CRUD + signing orchestration
│   │   └── pdf_service.py              # PyMuPDF: placeholder fill + signature overlay
│   └── templates/
│       ├── sign.html                   # Signing page (pdf.js + signature canvas + field overlays)
│       ├── success.html                # Post-signing success + download page
│       └── expired.html               # Expired link page
├── resources/
│   └── pdf_templates/
│       ├── wa_storage_lease.pdf        # Template PDF (add Signature.Here placeholders)
│       └── wa_storage_lease.defaults.json  # Default params + field character limits
├── requirements.txt
├── .env.example
└── README.md
```

---

## PDF Template Setup

Templates live in `resources/pdf_templates/`. Each template requires two files:

| File | Purpose |
|------|---------|
| `{name}.pdf` | The template PDF with placeholder text |
| `{name}.defaults.json` | Default parameter values + field character limits |

### Placeholder Convention

Placeholders in the PDF use `Namespace.Key` format (both parts capitalised):

```
Facility.Name    Facility.Address1    Facility.City    Facility.State
Facility.PostalCode    Facility.Phone    Facility.SalesTax    Facility.AdminFee

Tenant.Name    Tenant.Address1    Tenant.Address2    Tenant.City
Tenant.State    Tenant.PostalCode    Tenant.HomePhone    Tenant.CellPhone
Tenant.Email    Tenant.SSN    Tenant.DLNumber    Tenant.DLState
Tenant.RentDueDate    Tenant.AltName    Tenant.AltAddress1    Tenant.AltAddress2
Tenant.AltCity    Tenant.AltState    Tenant.AltPostalCode    Tenant.AltEmail
Tenant.ActiveMilitary    Tenant.LienHolderDetails

Space.ID    Space.Rent

Document.Date       ← auto-populated with today's date (e.g. "April 02, 2026")
Signature.Here      ← marks all signing fields; replaced with ____ in the output PDF
```

**Compound placeholders** (written directly adjacent in the PDF, no space):
- `Tenant.Address1Tenant.Address2`
- `Tenant.AltAddress1Tenant.AltAddress2`
- `Tenant.AltStateTenant.AltPostalCode`

These are handled automatically — do not include them in `template_parameters`.

### `Signature.Here` — How It Works

1. Add the text `Signature.Here` in the PDF at every location where a signature is required.
2. The service detects each occurrence (page number + bounding box) **before** filling the template.
3. In the output PDF the text is replaced with `____________________________` (a visual blank line).
4. The stored coordinates are sent to the signing page so clickable "SIGN HERE" overlays appear at the exact right position on every pdf.js page.
5. On finalisation the drawn signature image is overlaid at each stored rect.

### `defaults.json` Format

```json
{
  "defaults": {
    "facility": { "Name": "Larroc Storage", "State": "WA", "AdminFee": "$25.00" },
    "tenant":   { "Address2": "", "RentDueDate": "1st", "ActiveMilitary": "No" },
    "space":    {},
    "document": {}
  },
  "field_limits": {
    "Tenant.Name": 40,
    "Tenant.Email": 50,
    "Space.Rent": 15
  }
}
```

- Keys present in `template_parameters` **override** defaults.
- Keys absent from `template_parameters` fall back to the default value.
- Values exceeding `field_limits` are silently truncated.

---

## API Reference

> **Base URL:** `http://localhost:8000` (or your deployed URL)
> **Interactive docs:** `GET /docs` (Swagger UI)

---

### Protected Endpoints (require `X-API-Key` header)

---

#### `POST /api/v1/documents/create`

Creates a signing session by filling a stored PDF template.

**Auth:** `X-API-Key: <your_api_key>`  
**Content-Type:** `application/json`

**Request body:**
```json
{
  "template_name": "wa_storage_lease",
  "template_parameters": {
    "facility": {
      "Name": "Larroc Storage",
      "Phone": "(555) 123-4567"
    },
    "tenant": {
      "Name": "John Smith",
      "Email": "john@example.com",
      "CellPhone": "(555) 987-6543",
      "Address1": "456 Oak Ave",
      "City": "Bellevue",
      "State": "WA",
      "PostalCode": "98004"
    },
    "space": {
      "ID": "B7",
      "Rent": "$175.00"
    }
  },
  "signer_email": "john@example.com",
  "completion_emails": ["owner@larrocstorage.com", "manager@larrocstorage.com"]
}
```

> All top-level keys in `template_parameters` are optional. Missing keys fall back to template defaults.

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "signing_url": "http://localhost:8000/sign/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-04-09T17:30:00.000000",
  "status": "pending"
}
```

**Error responses:**
| Code | Reason |
|------|--------|
| `401` | Missing or invalid `X-API-Key` |
| `404` | `template_name` not found in `resources/pdf_templates/` |
| `429` | Rate limit exceeded (10 req/min) |
| `500` | PDF generation failed |

---

#### `GET /api/v1/templates`

Lists all available PDF templates.

**Auth:** `X-API-Key: <your_api_key>`

**Response `200`:**
```json
{ "templates": ["wa_storage_lease"] }
```

---

### Public Endpoints (no auth required — token is the access control)

---

#### `GET /sign/{token}`

Serves the signing page. Renders the PDF via pdf.js and overlays SIGN HERE buttons at all `Signature.Here` field positions.

**Response:** `text/html` — the interactive signing page  
**Behaviour:**
- `pending` → serves the signing UI
- `signed` → redirects to success page
- `expired` → shows expired page

---

#### `POST /sign/{token}/submit`

Submits the drawn signature and finalises the document.

**Content-Type:** `application/json`

**Request body:**
```json
{
  "signature_data": "data:image/png;base64,iVBORw0KGgo..."
}
```

> `signature_data` is a base64 PNG data URL (produced automatically by the signing page canvas).

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "signed",
  "signed_pdf_url": "/sign/download/550e8400-e29b-41d4-a716-446655440000"
}
```

**Error responses:**
| Code | Reason |
|------|--------|
| `400` | Document already signed or expired |
| `404` | Token not found |
| `429` | Rate limit exceeded (5 req/min) |

---

#### `GET /sign/download/{token}`

Downloads the finalised signed PDF.

**Response:** `application/pdf` (file download)

**Error responses:**
| Code | Reason |
|------|--------|
| `404` | Token not found or document not yet signed |
| `429` | Rate limit exceeded (10 req/min) |

---

#### `GET /api/v1/document/{token}`

Returns document metadata. Called by the signing page on load to get the PDF URL and signature field positions.

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "template_name": "wa_storage_lease",
  "signer_email": "john@example.com",
  "expires_at": "2026-04-09T17:30:00.000000",
  "created_at": "2026-04-02T17:30:00.000000",
  "pdf_url": "http://localhost:8000/api/v1/document/550e8400.../pdf",
  "signature_fields": [
    { "page": 3, "x0": 72.0, "y0": 660.0, "x1": 340.0, "y1": 690.0 }
  ]
}
```

> `signature_fields` is an array of `{page, x0, y0, x1, y1}` objects in PDF points (72 pts = 1 inch). `page` is 0-indexed.

---

#### `GET /api/v1/document/{token}/pdf`

Streams the filled (unsigned) PDF inline. Used as the pdf.js source URL.

**Response:** `application/pdf` (inline, not attachment)

**Error responses:**
| Code | Reason |
|------|--------|
| `404` | Token not found or PDF missing |
| `410` | Document has expired |

---

#### `GET /`

Health check.

**Response `200`:**
```json
{ "status": "ok", "service": "pdf-signing-service" }
```

---

## Configuration

Copy `.env.example` to `.env`:

```env
# Required
API_KEY=your_secure_random_key_here
BASE_URL=http://localhost:8000

# Database (SQLite by default)
DATABASE_URL=sqlite+aiosqlite:///./data.db

# File storage
UPLOAD_DIR=./uploads
SIGNED_DIR=./signed
```

---

## Running Locally

Make sure the template PDF is in place first:

```
resources/pdf_templates/wa_storage_lease.pdf   ← copy your template here
```

Then start the server from the repo root:

```bash
# Option A — using the __main__ entrypoint
.venv/bin/python3 app/main.py

# Option B — uvicorn directly
.venv/bin/python3 -m uvicorn main:app --reload --port 8000 --app-dir app
```

Visit:
- `http://localhost:8000/docs` — Swagger UI (all endpoints, interactive)
- `http://localhost:8000/` — health check

---

## Testing with Postman

1. **Create document**
   - `POST http://localhost:8000/api/v1/documents/create`
   - Header: `X-API-Key: default_unsafe_key_for_dev_only`
   - Body: JSON (see request body in API Reference above)
   - Copy `signing_url` from response

2. **Open signing URL** in a browser — sign the document using the UI.

3. **Download signed PDF** via the URL on the success page, or:
   - `GET http://localhost:8000/sign/download/{id}`

---

## Deploying to Render.com

1. Create a **Web Service**, connect your GitHub repo.
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `cd app && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add a **Persistent Disk** mounted at `/data` and set env vars:
   ```
   UPLOAD_DIR=/data/uploads
   SIGNED_DIR=/data/signed
   DATABASE_URL=sqlite+aiosqlite:////data/data.db
   BASE_URL=https://your-app.onrender.com
   ```
5. Set `API_KEY` to a strong random value.

---

## TODO / Future Enhancements

### Email on Completion
- [ ] Implement `email_service.py` using `aiosmtplib` (or Brevo/Mailgun via `httpx`)
- [ ] Add SMTP env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL`
- [ ] After signing, send the signed PDF to all `completion_emails`
- [ ] Optionally send the signer a copy

### n8n Completion Webhook
- [ ] Add `N8N_WEBHOOK_URL: str = ""` to `core/config.py`
- [ ] After signing, POST `{"document_id": ..., "status": "signed", "signed_pdf_url": ...}` to the webhook URL via `httpx.AsyncClient`

### Deployment
- [ ] Add `Procfile` for Render/Heroku: `web: cd app && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Add `Dockerfile` for container-based deploy

### Security Hardening
- [ ] Replace `allow_origins=["*"]` with an explicit origin list in production CORS config
- [ ] Add expiry check to `GET /api/v1/document/{token}/pdf`

### UX Polish
- [ ] Mobile-responsive layout for the signing page
- [ ] Typed signature option alongside the drawn canvas
- [ ] Page progress indicator showing document scroll status