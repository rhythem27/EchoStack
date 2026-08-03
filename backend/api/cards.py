import json
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from backend.auth import get_current_user_context, current_user_id

logger = logging.getLogger("backend-api-cards")

router = APIRouter(prefix="/api/cards", tags=["UI Cards"])

# Schema definitions for supported dynamic UI cards
CARD_SCHEMAS = {
    "AnalyticsMetricsCard": {
        "description": "Visual user analytics summary with metrics, topic badges, and engagement levels.",
        "properties": {
            "total_interactions": "integer",
            "top_topics": "array of strings or dicts",
            "last_updated_at": "ISO timestamp string",
            "user_id": "string UUID"
        }
    },
    "DocumentSearchCard": {
        "description": "RAG Knowledge Base search results card with format tags and relevance scores.",
        "properties": {
            "query": "string",
            "total_results": "integer",
            "results": "array of result objects {id, section_title, file_format, rrf_score, snippet}"
        }
    },
    "PythonResultCard": {
        "description": "Python sandbox code execution result card with syntax view and output log.",
        "properties": {
            "code": "string",
            "output": "string",
            "status": "string ('success' or 'error')"
        }
    }
}

@router.get("/templates")
async def get_card_templates(user_context: Dict[str, Any] = Depends(get_current_user_context)):
    """
    Returns supported dynamic UI card component definitions and their expected data schemas.
    """
    return {
        "status": "success",
        "schemas": CARD_SCHEMAS
    }

@router.get("/schemas/{component_name}")
async def get_card_schema(component_name: str, user_context: Dict[str, Any] = Depends(get_current_user_context)):
    """
    Returns data schema for a specific dynamic UI card component.
    """
    if component_name not in CARD_SCHEMAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card component '{component_name}' not found."
        )
    return {
        "component": component_name,
        "schema": CARD_SCHEMAS[component_name]
    }
