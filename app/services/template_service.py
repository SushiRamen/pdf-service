"""
TemplateService — loads PDF templates, merges parameters, and generates filled PDFs.

Template directory layout:
  resources/pdf_templates/
    {template_name}.pdf               ← the template PDF (store manually)
    {template_name}.defaults.json     ← defaults + field limits

Placeholder convention in the PDF:
  Namespace.Key  e.g.  Facility.Name,  Tenant.Email,  Space.Rent,  Document.Date

Incoming template_parameters structure:
  {
    "facility": { "Name": "...", "Phone": "..." },
    "tenant":   { "Name": "...", "Email": "..." },
    "space":    { "ID": "A12",  "Rent": "$150" }
  }
"""

import json
import os
import datetime
import asyncio
from pathlib import Path
from typing import Any

from services.pdf_service import PDFService, SIGNATURE_FIELD_NAME
from core.config import settings

# Root of template resources — two levels up from app/services/
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "resources" / "pdf_templates"


class TemplateNotFoundError(Exception):
    pass


class TemplateService:

    @staticmethod
    def list_templates() -> list[str]:
        """Return names of all available templates (stem of each .pdf file)."""
        return [p.stem for p in _TEMPLATES_DIR.glob("*.pdf")]

    @staticmethod
    def _load_defaults(template_name: str) -> dict:
        path = _TEMPLATES_DIR / f"{template_name}.defaults.json"
        if not path.exists():
            return {"defaults": {}, "field_limits": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base. Override values win."""
        result = dict(base)
        for key, val in override.items():
            if isinstance(val, dict) and isinstance(result.get(key), dict):
                result[key] = TemplateService._deep_merge(result[key], val)
            elif val not in (None, ""):
                # Only override if the incoming value is actually provided
                result[key] = val
        return result

    @staticmethod
    def _flatten_params(nested: dict[str, dict]) -> dict[str, str]:
        """
        Convert  {"facility": {"Name": "X"}}
        →        {"Facility.Name": "X"}
        Namespace capitalised, key kept as-is.
        """
        flat: dict[str, str] = {}
        for namespace, fields in nested.items():
            if not isinstance(fields, dict):
                continue
            ns_cap = namespace.capitalize()
            for key, value in fields.items():
                flat[f"{ns_cap}.{key}"] = str(value) if value is not None else ""
        return flat

    @staticmethod
    def _apply_field_limits(flat: dict[str, str], limits: dict[str, int]) -> dict[str, str]:
        """Truncate values that exceed their defined character limits."""
        result = {}
        for placeholder, value in flat.items():
            limit = limits.get(placeholder)
            if limit and len(value) > limit:
                value = value[:limit]
            result[placeholder] = value
        return result

    @staticmethod
    def _add_compound_placeholders(flat: dict[str, str]) -> dict[str, str]:
        """
        The PDF has several concatenated placeholder pairs with no separator.
        Build the combined replacement value so pdf_service can find and
        replace the exact string that appears in the PDF.

        Compound strings (must be replaced BEFORE their components):
          Tenant.Address1Tenant.Address2
          Tenant.AltAddress1Tenant.AltAddress2
          Tenant.AltStateTenant.AltPostalCode
        """
        compounds: dict[str, str] = {}

        addr1 = flat.get("Tenant.Address1", "")
        addr2 = flat.get("Tenant.Address2", "")
        compounds["Tenant.Address1Tenant.Address2"] = (
            addr1 + (", " + addr2 if addr2 else "")
        )

        alt_addr1 = flat.get("Tenant.AltAddress1", "")
        alt_addr2 = flat.get("Tenant.AltAddress2", "")
        compounds["Tenant.AltAddress1Tenant.AltAddress2"] = (
            alt_addr1 + (", " + alt_addr2 if alt_addr2 else "")
        )

        alt_state = flat.get("Tenant.AltState", "")
        alt_postal = flat.get("Tenant.AltPostalCode", "")
        compounds["Tenant.AltStateTenant.AltPostalCode"] = (
            alt_state + (" " + alt_postal if alt_postal else "")
        )

        # Prepend compounds so they're processed first (longest match wins)
        return {**compounds, **flat}

    @staticmethod
    def _auto_document_fields(flat: dict[str, str]) -> dict[str, str]:
        """Populate Document.* fields that are always auto-generated."""
        if not flat.get("Document.Date"):
            flat["Document.Date"] = datetime.date.today().strftime("%B %d, %Y")
        return flat

    @staticmethod
    async def generate_pdf(
        template_name: str,
        template_parameters: dict[str, Any],
        output_dir: str,
        output_filename: str,
    ) -> str:
        """
        Full pipeline:
          1. Validate template exists
          2. Load defaults + field limits
          3. Merge incoming params over defaults
          4. Flatten to {"Facility.Name": "value"} dict
          5. Apply field length limits
          6. Inject compound placeholders
          7. Auto-populate Document.Date
          8. Fill placeholders in PDF (runs in thread — PyMuPDF is blocking)
          9. Return path to generated PDF
        """
        template_pdf = _TEMPLATES_DIR / f"{template_name}.pdf"
        if not template_pdf.exists():
            raise TemplateNotFoundError(
                f"Template '{template_name}' not found. "
                f"Available: {TemplateService.list_templates()}"
            )

        config = TemplateService._load_defaults(template_name)
        defaults: dict = config.get("defaults", {})
        field_limits: dict = config.get("field_limits", {})

        # Merge: defaults ← overridden by incoming params
        merged = TemplateService._deep_merge(defaults, template_parameters)

        # Flatten namespaces to dot notation
        flat = TemplateService._flatten_params(merged)

        # Apply character limits
        flat = TemplateService._apply_field_limits(flat, field_limits)

        # Add compound placeholders (before their components)
        flat = TemplateService._add_compound_placeholders(flat)

        # Auto-populate Document fields
        flat = TemplateService._auto_document_fields(flat)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        # Detect all Signature.Here widget positions from the TEMPLATE before filling.
        # Store them in the DB so the frontend and finaliser know where to act.
        signature_fields = await asyncio.to_thread(
            PDFService.detect_signature_fields,
            str(template_pdf),
        )

        # PyMuPDF is blocking — run in thread.
        # Signature.Here widgets are intentionally left empty by fill_form_fields.
        await asyncio.to_thread(
            PDFService.fill_form_fields,
            str(template_pdf),
            output_path,
            flat,
        )

        return output_path, signature_fields
