"""
Chat router — "Frag dein Archiv" (RAG over the user's saved content).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import ChatRequest, ChatResponse, ChatSource
from app.services.rag import answer_question

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a question grounded in the user's archived content."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Frage darf nicht leer sein")

    try:
        result = await answer_question(question, db, top_k=request.top_k)
    except Exception as e:  # noqa: BLE001 — surface a clean 502 instead of a 500 traceback
        logger.error(f"RAG chat failed: {e}")
        raise HTTPException(
            status_code=502, detail="Der Chat-Dienst ist gerade nicht erreichbar."
        ) from e

    return ChatResponse(
        answer=result.answer,
        sources=[ChatSource(**vars(s)) for s in result.sources],
        used_context=result.used_context,
    )
