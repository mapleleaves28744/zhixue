from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.llm import ChatMessage, get_llm_provider
from app.models.user import User
from app.rag.retriever import VectorRetriever
from app.services.prompt_service import PromptService


router = APIRouter()


@router.get("/ping")
async def ping(request: Request) -> dict[str, object]:
    return success_response({"module": "tutor", "status": "ok"}, request=request)


class TutorAskRequest(BaseModel):
    course_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/ask")
async def ask_tutor(
    body: TutorAskRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    retriever = VectorRetriever(db)
    results = []
    try:
        results = await retriever.search(
            course_id=body.course_id,
            query=body.question,
            top_k=body.top_k,
        )
        context_parts = [r.content for r in results]
        retrieved_context = "\n\n".join(context_parts) if context_parts else "未检索到相关资料"
    except Exception:
        retrieved_context = "未检索到相关资料"

    prompts = PromptService(db)
    rendered = await prompts.render_prompt(
        agent_name="TutorAgent",
        scene="tutor.qa",
        params={
            "question": body.question,
            "retrieved_context": retrieved_context[:3000],
        },
    )

    llm = get_llm_provider(db=db, user_id=current_user.id, course_id=body.course_id)
    response = await llm.chat(
        [ChatMessage(role="user", content=rendered.content)],
        temperature=0.7,
        max_tokens=2048,
    )

    return success_response(
        {
            "answer": response.content,
            "model": response.model,
            "sources": [
                {
                    "chunk_id": str(r.chunk_id),
                    "source_title": r.source_title,
                    "score": round(r.score, 4),
                }
                for r in results
            ],
        },
        request=request,
    )
