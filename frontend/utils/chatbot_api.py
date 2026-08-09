"""
Chatbot API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/chatbot/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by utils/quiz_api.py.

Unlike the other api utils, these read the JSON body even on non-2xx
responses, so the assistant's specific error message (e.g. "Ollama is not
running") reaches the UI instead of a generic status code.
"""

import httpx
from config import backend_endpoint

# Generous timeout: local LLM inference on the first token can be slow.
_CHAT_TIMEOUT = 180
_HEALTH_TIMEOUT = 10


def send_chat_message(messages: list) -> dict:
    """
    Send the full conversation and get the assistant's next reply.

    Args:
        messages: [{"role": "user"|"assistant", "content": str}, ...]

    Returns:
        {"success": True, "reply": str, "provider": str} or
        {"success": False, "error": str}
    """
    try:
        url = f"{backend_endpoint}api/chatbot/chat"
        response = httpx.post(url, json={"messages": messages}, timeout=_CHAT_TIMEOUT)
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"The assistant service returned an unexpected response (status {response.status_code})."}
    except httpx.ConnectError:
        return {"success": False, "error": "Could not reach the backend service. Make sure it is running."}
    except Exception as e:
        return {"success": False, "error": f"Could not reach the assistant: {e}"}


def check_chatbot_health() -> dict:
    """
    Check whether the underlying LLM provider (Ollama) is reachable.

    Returns:
        {"success": True, "available": bool} or {"success": False, ...}
    """
    try:
        url = f"{backend_endpoint}api/chatbot/health"
        response = httpx.get(url, timeout=_HEALTH_TIMEOUT)
        try:
            return response.json()
        except Exception:
            return {"success": False, "available": False}
    except Exception as e:
        return {"success": False, "available": False, "error": str(e)}
