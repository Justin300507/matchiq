import openai
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.main import get_artifact_dir, get_db
from app.ml.analyst import answer_question
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def post_chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    artifact_dir=Depends(get_artifact_dir),
):
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="AI analyst is not configured — set OPENAI_API_KEY")

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        answer = answer_question(
            db, artifact_dir, body.sport, body.league, body.question, settings.openai_api_key
        )
    except openai.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"AI analyst request failed: {e.message}")
    except openai.APIConnectionError:
        raise HTTPException(status_code=502, detail="AI analyst request failed: connection error")

    return ChatResponse(answer=answer)
