"""Grok (xAI) document classifier — OpenAI-compatible API."""

from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO

import openpyxl
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionUserMessageParam,
)

from models import ClassificationResult

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Eres un clasificador de documentos contables para un estudio en Argentina.
Analiza el documento adjunto y devuelve ÚNICAMENTE un JSON con esta estructura exacta:

{
  "cliente": "nombre del cliente o empresa",
  "tipo_documento": "Factura | Recibo | Comprobante | Extracto | Otro",
  "periodo": "MM-YYYY",
  "proveedor": "nombre del emisor si es visible",
  "monto": 0.00,
  "confianza": 0.0
}

Reglas:
- "confianza" debe ser un número entre 0.0 y 1.0 que refleje qué tan seguro estás de la clasificación.
- Si no podés determinar un campo, usá cadena vacía "" para textos y 0.00 para montos.
- El período se calcula a partir de la fecha visible en el documento. Si no hay fecha, usá "".
- No agregues texto fuera del JSON."""

IMAGE_MIME_TYPES = frozenset(["image/jpeg", "image/png"])
EXCEL_MIME_TYPES = frozenset(
    [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]
)
PDF_MIME_TYPE = "application/pdf"


class ClassificationError(Exception):
    """Base exception for classification failures."""


class ClassificationTimeoutError(ClassificationError):
    """Grok API timed out."""


class ClassificationAuthError(ClassificationError):
    """Grok API authentication failed (401)."""


class ClassificationParseError(ClassificationError):
    """Grok response was not valid JSON."""


def _encode_image(file_bytes: bytes, content_type: str) -> str:
    """Encode image bytes as a base64 data URL."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


def _extract_excel_text(file_bytes: bytes) -> str:
    """Extract text content from an Excel file using openpyxl."""
    workbook = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    from openpyxl.worksheet.worksheet import Worksheet

    parts: list[str] = []
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        if not isinstance(sheet, Worksheet):
            continue
        parts.append(f"--- Hoja: {sheet_name} ---")
        for row in sheet.iter_rows(values_only=True):
            row_text = " | ".join(
                str(cell) for cell in row if cell is not None
            )
            if row_text.strip():
                parts.append(row_text)
    workbook.close()
    return "\n".join(parts)


def _parse_classification_response(raw_text: str) -> ClassificationResult:
    """Parse Grok's response text into a ClassificationResult.

    Handles responses wrapped in markdown code fences.
    """
    # Try to extract JSON from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1)
    else:
        # Fall back: find first JSON object
        brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(0)
        else:
            raise ClassificationParseError(
                f"No JSON object found in response: {raw_text[:200]}"
            )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ClassificationParseError(
            f"Invalid JSON in Grok response: {json_str[:200]}"
        ) from exc

    return ClassificationResult(
        cliente=data.get("cliente", ""),
        tipo_documento=data.get("tipo_documento", ""),
        periodo=data.get("periodo", ""),
        proveedor=data.get("proveedor", ""),
        monto=float(data.get("monto", 0.0)),
        confianza=float(data.get("confianza", 0.0)),
    )


async def classify_document(
    file_bytes: bytes,
    content_type: str,
    filename: str,
    api_key: str,
    base_url: str = "https://api.x.ai/v1",
    model: str = "grok-2-vision-1212",
    timeout_s: int = 15,
) -> ClassificationResult:
    """Classify a document using Grok (xAI) vision API.

    Args:
        file_bytes: Raw file contents.
        content_type: MIME type of the file.
        filename: Original filename (for logging).
        api_key: xAI API key.
        base_url: xAI API base URL.
        timeout_s: Request timeout in seconds.

    Returns:
        ClassificationResult with structured metadata.

    Raises:
        ClassificationTimeoutError: API call timed out.
        ClassificationAuthError: Authentication failed.
        ClassificationParseError: Response couldn't be parsed.
    """
    import httpx

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=httpx.Timeout(timeout_s),
    )

    # Build message content based on file type
    content_parts: list = []

    if content_type in IMAGE_MIME_TYPES:
        content_parts.append(
            ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={"url": _encode_image(file_bytes, content_type)},
            )
        )

    elif content_type == PDF_MIME_TYPE:
        # Treat PDF as image (Grok vision handles it)
        content_parts.append(
            ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={
                    "url": _encode_image(file_bytes, "application/pdf")
                },
            )
        )

    elif content_type in EXCEL_MIME_TYPES:
        # Extract text from Excel
        try:
            excel_text = _extract_excel_text(file_bytes)
        except Exception as exc:
            logger.warning("Failed to extract Excel text from %s: %s", filename, exc)
            excel_text = f"[No se pudo leer el archivo Excel: {filename}]"

        content_parts.append(
            ChatCompletionContentPartTextParam(
                type="text",
                text=f"Documento Excel ({filename}):\n\n{excel_text[:4000]}",
            )
        )

    else:
        # Unknown type — try as text
        try:
            text_content = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            text_content = f"[Archivo no legible: {filename}]"

        content_parts.append(
            ChatCompletionContentPartTextParam(
                type="text",
                text=f"Contenido del archivo ({filename}):\n\n{text_content[:4000]}",
            )
        )

    # Add the classification instruction as a separate user message
    messages = [
        {
            "role": "system",
            "content": "Sos un clasificador de documentos contables. Respondé ÚNICAMENTE con JSON válido, sin texto adicional.",
        },
        ChatCompletionUserMessageParam(
            role="user",
            content=content_parts,
        ),
        {
            "role": "user",
            "content": CLASSIFICATION_PROMPT,
        },
    ]

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=0.0,
        )
    except httpx.TimeoutException as exc:
        raise ClassificationTimeoutError(
            f"Grok API timed out after {timeout_s}s"
        ) from exc
    except Exception as exc:
        error_str = str(exc).lower()
        if "401" in error_str or "unauthorized" in error_str or "auth" in error_str:
            raise ClassificationAuthError(
                "Grok API authentication failed — check XAI_API_KEY"
            ) from exc
        raise ClassificationError(f"Grok API error: {exc}") from exc

    raw_text = response.choices[0].message.content or ""
    logger.debug("Grok raw response (first 200 chars): %s", raw_text[:200])

    return _parse_classification_response(raw_text)
