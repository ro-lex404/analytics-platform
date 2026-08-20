import os
import re

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import the Celery worker task and compiled LangGraph workflow
from app.worker import process_document_task
from app.agent.router import app as agent_app

app = FastAPI(title="Hybrid AI Analytics API")


def _resolve_allowed_origins() -> list[str]:
    default_origins = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    }
    configured = os.getenv("ALLOWED_ORIGINS", "")
    configured_origins = {origin.strip() for origin in configured.split(",") if origin.strip()}
    return sorted(default_origins | configured_origins)

# Enable CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str


def _collapse_exact_repetition(text: str) -> str:
    """Collapses exact contiguous repetition such as A+A or A+A+A."""
    normalized = (text or "").strip()
    if not normalized:
        return ""

    for repeats in (3, 2):
        if len(normalized) % repeats != 0:
            continue
        chunk_size = len(normalized) // repeats
        chunk = normalized[:chunk_size]
        if chunk * repeats == normalized:
            return chunk.strip()

    lines = normalized.splitlines()
    if len(lines) % 2 == 0:
        half = len(lines) // 2
        if lines[:half] == lines[half:]:
            return "\n".join(lines[:half]).strip()

    return normalized


def _collapse_adjacent_word_repeats(text: str) -> str:
    """Collapses duplicated adjacent words such as 'hello hello'."""
    return re.sub(r"\b(\w+)\b(?:\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)


def normalize_final_answer(answer: str) -> str:
    deduped = _collapse_exact_repetition(answer)
    deduped = _collapse_adjacent_word_repeats(deduped)
    return deduped.strip()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Saves uploaded PDFs/CSVs and triggers the Celery background task."""
    
    # 1. Guarantee the directory exists so it never fails
    upload_dir = "./uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_location = f"{upload_dir}/{file.filename}"
    
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
        
    # Dispatch heavy processing job to Redis/Celery worker
    process_document_task.delay(file_location, file.filename)
    
    return {"info": f"File '{file.filename}' saved."}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    inputs = {"question": request.query}
    final_state = await agent_app.ainvoke(inputs)
    final_answer = final_state.get("final_answer", "")
    normalized_answer = normalize_final_answer(final_answer)
    return JSONResponse({"answer": normalized_answer})