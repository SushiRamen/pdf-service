from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_api_key
from core.limiter import limiter
from core.config import settings
from db.database import get_db
from db.schemas import DocumentCreateRequest, DocumentCreateResponse
from services.document_service import DocumentService
from services.template_service import TemplateNotFoundError

router = APIRouter()


@router.post(
    "/documents/create",
    response_model=DocumentCreateResponse,
    dependencies=[Depends(get_api_key)],
    summary="Create a document signing session from a stored template",
)
@limiter.limit("10/minute")
async def create_document(
    request: Request,
    body: DocumentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    **Auth:** X-API-Key header required.

    **Body (JSON):**
    ```json
    {
      "template_name": "wa_storage_lease",
      "template_parameters": {
        "facility": { "Name": "Larroc Storage", "Phone": "(555) 123-4567" },
        "tenant":   { "Name": "John Smith", "Email": "john@example.com",
                      "CellPhone": "(555) 987-6543", "Address1": "456 Oak Ave",
                      "City": "Bellevue", "State": "WA", "PostalCode": "98004" },
        "space":    { "ID": "B7", "Rent": "$175.00" }
      },
      "signer_email": "john@example.com",
      "completion_emails": ["owner@larrocstorage.com"]
    }
    ```

    Keys not provided fall back to template defaults defined in `{template_name}.defaults.json`.
    Returns a `signing_url` the client opens in their browser.
    """
    try:
        doc = await DocumentService.create_from_template(
            db=db,
            template_name=body.template_name,
            template_parameters=body.template_parameters,
            signer_email=body.signer_email,
            completion_emails=body.completion_emails or [],
        )
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {exc}")

    signing_url = f"{settings.BASE_URL}/sign/{doc.id}"
    return DocumentCreateResponse(
        id=doc.id,
        signing_url=signing_url,
        expires_at=doc.expires_at,
        status=doc.status,
    )


@router.get(
    "/templates",
    summary="List available PDF templates",
    dependencies=[Depends(get_api_key)],
)
@limiter.limit("30/minute")
async def list_templates(request: Request):
    """Returns names of all templates available in resources/pdf_templates/."""
    from services.template_service import TemplateService
    return {"templates": TemplateService.list_templates()}
