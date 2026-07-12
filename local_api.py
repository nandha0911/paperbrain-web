import time
from pathlib import Path
from pydantic import BaseModel
from services.pdf_service import pdf_service
from services.vector_store import vector_store
from services.rag_service import RAGService
from services.llm_service import llm_service
from services.cache_service import query_cache
from models.document import DocumentInfo, ProcessingStatus
from models.chat import ChatRequest, ChatResponse
from utils.file_utils import sanitize_filename
from utils.hash_utils import compute_file_hash

# Initialize RAGService once
rag_service = RAGService()

def api_health() -> dict:
    try:
        llm_ok, llm_msg = llm_service.is_available()
        docs = vector_store.get_all_documents()
        return {
            "status": "healthy" if llm_ok else "degraded",
            "llm": {
                "provider": llm_service.provider_name,
                "model": llm_service.model_name,
                "available": llm_ok,
                "message": llm_msg,
            },
            "vector_store": {
                "documents": len(docs),
                "total_chunks": vector_store.total_chunks(),
            },
            "cache": query_cache.stats,
        }
    except Exception:
        return {}

def api_list_documents() -> list[dict]:
    try:
        docs = vector_store.get_all_documents()
        return [doc.model_dump() for doc in docs]
    except Exception:
        return []

def api_upload(file_bytes: bytes, filename: str) -> dict:
    try:
        file_hash = compute_file_hash(file_bytes)
        existing_filename = vector_store.document_exists(file_hash)
        
        if existing_filename:
            existing_info = vector_store.get_document(existing_filename)
            return {
                "filename": existing_filename,
                "page_count": existing_info.page_count if existing_info else 0,
                "chunk_count": existing_info.chunk_count if existing_info else 0,
                "already_exists": True
            }

        safe_name = sanitize_filename(filename)
        chunks, page_count, _ = pdf_service.process_pdf(file_bytes, safe_name)
        
        if not chunks:
            return {"error": "No extractable text found."}

        doc_info = DocumentInfo(
            filename=safe_name,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            page_count=page_count,
            chunk_count=len(chunks),
            status=ProcessingStatus.PROCESSING,
        )
        
        stored_count = vector_store.add_chunks(chunks, doc_info)
        doc_info.status = ProcessingStatus.COMPLETED
        doc_info.chunk_count = stored_count
        
        return {
            "filename": safe_name,
            "page_count": page_count,
            "chunk_count": stored_count,
            "already_exists": False
        }
    except Exception as e:
        return {"error": str(e)}

def api_chat(question: str, session_id: str, top_k: int) -> dict:
    try:
        req = ChatRequest(question=question, session_id=session_id, top_k=top_k)
        response = rag_service.chat(req)
        return response.model_dump()
    except Exception as e:
        return {"error": str(e)}

def api_delete_document(filename: str) -> bool:
    try:
        success = vector_store.remove_document(filename)
        return success
    except Exception:
        return False

def api_delete_all() -> bool:
    try:
        vector_store.clear_all()
        return True
    except Exception:
        return False

def api_clear_history(session_id: str) -> bool:
    try:
        rag_service.memory.clear(session_id)
        return True
    except Exception:
        return False
