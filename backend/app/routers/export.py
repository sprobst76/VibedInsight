"""
Export Router - Export user content as Markdown ZIP.

Generates an Obsidian-compatible ZIP archive containing one Markdown file
per saved article that has been summarized.
"""

import io
import re
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_dev_or_current_user
from app.models.content import ContentItem, ProcessingStatus
from app.models.user import User, UserItem

router = APIRouter()


def _safe_filename(title: str) -> str:
    """Convert title to a safe filename."""
    safe = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    safe = re.sub(r"[\s_]+", "-", safe.strip())
    return safe[:80] or "untitled"


def _item_to_markdown(user_item: UserItem) -> str:
    """Convert a UserItem to Markdown content."""
    content = user_item.content
    lines = []

    title = content.title or "Untitled"
    lines.append(f"# {title}\n")

    # Metadata block
    if content.source:
        lines.append(f"**Quelle:** {content.source}")
    lines.append(f"**Datum:** {user_item.created_at.strftime('%d.%m.%Y')}")
    if content.topics:
        topic_names = ", ".join(t.name for t in content.topics)
        lines.append(f"**Topics:** {topic_names}")
    if user_item.rating > 0:
        lines.append(f"**Bewertung:** {user_item.rating}/5")
    if content.url:
        lines.append(f"**URL:** {content.url}")

    lines.append("")
    lines.append("## Zusammenfassung")
    lines.append("")
    lines.append(content.summary or "")

    return "\n".join(lines)


@router.get("/markdown")
async def export_markdown(
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all summarized items as an Obsidian-compatible Markdown ZIP."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.user_id == user.id)
        .join(UserItem.content)
        .where(
            ContentItem.status == ProcessingStatus.COMPLETED,
            ContentItem.summary.is_not(None),
        )
        .order_by(UserItem.created_at.desc())
    )
    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        seen_names: dict[str, int] = {}
        for ui in user_items:
            date_str = ui.created_at.strftime("%Y-%m-%d")
            base_name = _safe_filename(ui.content.title or "untitled")
            filename = f"{date_str}-{base_name}.md"

            # Handle duplicate filenames
            if filename in seen_names:
                seen_names[filename] += 1
                filename = f"{date_str}-{base_name}-{seen_names[filename]}.md"
            else:
                seen_names[filename] = 0

            zf.writestr(filename, _item_to_markdown(ui))

    zip_buffer.seek(0)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    zip_filename = f"vibedinsight-export-{today}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
