"""FastAPI router for Evidence PDF Download and Cryptographic Verification.

Endpoints:
- GET /cases/{id}/evidence: Streams generated PDF evidence dossier
- POST /evidence/verify: Validates uploaded PDF file against hash-chained ledger and HMAC seal
"""

from pathlib import Path
from typing import Any
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evidence import verify_evidence_pdf
from app.config import Settings, get_settings
from app.db import get_db_session
from app.models.case import Case

router = APIRouter(tags=["Evidence"])


# ==============================================================================
# 1. Evidence PDF Download
# ==============================================================================


@router.get("/cases/{id}/evidence")
async def download_case_evidence(
    id: str,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Returns downloadable PDF evidence dossier for a completed case."""
    try:
        case_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    res = await db.execute(select(Case).where(Case.id == case_uuid))
    case_obj = res.scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    pdf_path = Path(settings.STORAGE_DIR) / "evidence" / f"{case_uuid}.pdf"
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence PDF not yet generated for case '{id}'.",
        )

    pdf_bytes = pdf_path.read_bytes()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="case_{case_uuid}_evidence.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ==============================================================================
# 2. Cryptographic Ledger & Signature Verification
# ==============================================================================


@router.post("/evidence/verify")
async def verify_evidence(
    file: UploadFile = File(..., description="Evidence PDF document to verify"),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Verifies authenticity and cryptographic integrity of an evidence PDF file."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        # Note: Still compute hash if content present, or reject non-PDF
        pass

    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    verification = await verify_evidence_pdf(
        pdf_bytes=pdf_bytes,
        db=db,
        settings=settings,
    )

    return verification
