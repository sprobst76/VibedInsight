"""
Chat router — "Frag dein Archiv" (RAG over the user's saved content).

Two endpoints share the same retrieval:
- POST /chat        buffered JSON answer.
- POST /chat/stream NDJSON event stream (sources first, then answer deltas),
                    so the app can show sources instantly and stream tokens.
"""

import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import ChatRequest, ChatResponse, ChatSource
from app.services import rag

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_question(request: ChatRequest) -> str:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Frage darf nicht leer sein")
    return question


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a question grounded in the user's archived content."""
    question = _clean_question(request)
    try:
        result = await rag.answer_question(question, db, user, top_k=request.top_k)
    except Exception as e:  # noqa: BLE001 — clean 502 instead of a 500 traceback
        logger.error(f"RAG chat failed: {e}")
        raise HTTPException(
            status_code=502, detail="Der Chat-Dienst ist gerade nicht erreichbar."
        ) from e

    return ChatResponse(
        answer=result.answer,
        sources=[ChatSource(**vars(s)) for s in result.sources],
        used_context=result.used_context,
    )


def _ndjson(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream the answer as NDJSON events: sources -> delta* -> done.

    Retrieval (DB-bound) runs here, before streaming starts; the generator then
    only touches Ollama, so the DB session is never used mid-stream.
    """
    question = _clean_question(request)
    prep = await rag.prepare(question, db, user, top_k=request.top_k)

    async def events():
        if not prep.used_context:
            yield _ndjson(
                {
                    "type": "answer",
                    "answer": prep.fallback_answer or rag.NO_CONTEXT_ANSWER,
                    "sources": [],
                    "used_context": False,
                }
            )
            return

        yield _ndjson(
            {
                "type": "sources",
                "sources": [asdict(s) for s in prep.sources],
                "used_context": True,
            }
        )
        try:
            async for delta in rag.stream_answer(question, prep.context):
                yield _ndjson({"type": "delta", "text": delta})
            yield _ndjson({"type": "done"})
        except Exception as e:  # noqa: BLE001 — surface as a stream error event
            logger.error(f"RAG stream failed: {e}")
            yield _ndjson(
                {
                    "type": "error",
                    "message": "Der Chat-Dienst ist gerade nicht erreichbar.",
                }
            )

    return StreamingResponse(events(), media_type="application/x-ndjson")
