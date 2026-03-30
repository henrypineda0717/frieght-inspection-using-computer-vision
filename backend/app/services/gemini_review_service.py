"""Gemini LLM review helper"""
from __future__ import annotations

import base64
import json
import time
from typing import Optional, Dict, Any

import requests
from requests import Response
from requests.exceptions import RequestException

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiReviewService:
    """Wraps Gemini generative language review calls for inspection imagery."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash-lite")
        self.temperature = getattr(settings, "GEMINI_REVIEW_TEMPERATURE", 0.25)
        self._cache: Dict[str, str] = {}
        self.enabled = bool(self.api_key)
        self.endpoint = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent"
        self.max_retries = 3
        self.base_delay = 2.0

    def review_image(self, image_bytes: bytes, prompt_context: str, cache_key: Optional[str] = None) -> Optional[str]:
        """Call Gemini to describe a defect using the supplied image with retry logic."""
        if not self.enabled or not image_bytes:
            return None

        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        encoded_image = self._encode_image(image_bytes)
        
        # New Gemini 1.5/2.0 content format
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_context},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "topP": 0.95,
                "topK": 64,
                "maxOutputTokens": 1024,
            }
        }

        text = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.endpoint,
                    params={"key": self.api_key},
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(f"Gemini rate limit hit (429). Retrying in {delay}s... (Attempt {attempt+1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Gemini rate limit hit. Max retries exhausted.")
                        response.raise_for_status()
                
                response.raise_for_status()
                text = self._extract_text(response.json())
                break # Success
                
            except RequestException as exc:
                if attempt == self.max_retries:
                    self._log_request_failure(payload, exc.response)
                elif exc.response is not None and exc.response.status_code != 429:
                    # Non-429 error, don't retry unless it's a transient server error
                    if exc.response.status_code >= 500:
                        delay = self.base_delay
                        time.sleep(delay)
                        continue
                    self._log_request_failure(payload, exc.response)
                    break
            except (ValueError, KeyError, IndexError) as exc:
                logger.warning("Gemini review response parsing failed", exc_info=exc)
                break

        final_text = text or "Descriptive analysis unavailable at this time"
        if cache_key:
            self._cache[cache_key] = final_text
        return final_text

    def _log_request_failure(self, payload: Dict[str, Any], response: Optional[Response]) -> None:
        """Log request payload and response body when the Gemini call fails."""
        try:
            logged_payload = json.loads(json.dumps(payload))
            if "contents" in logged_payload:
                for content in logged_payload["contents"]:
                    for part in content.get("parts", []):
                        if "inline_data" in part:
                            part["inline_data"]["data"] = "<image data omitted>"
            request_info = json.dumps(logged_payload, indent=2)
        except Exception:
            request_info = "<unable to serialize payload>"

        response_body = None
        if response is not None:
            try:
                response_body = response.text
            except Exception:
                response_body = "<unable to read response text>"

        logger.warning(
            "Gemini review request failed",
            extra={
                "request_payload": request_info,
                "response_status": response.status_code if response else None,
                "response_text": (response_body or "")[:1000]
            }
        )

    def _encode_image(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def _extract_text(self, payload: Dict) -> Optional[str]:
        # Handle Gemini 1.5/2.0 response structure
        candidates = payload.get("candidates") or []
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"].strip()
        
        output = payload.get("output") or payload.get("text")
        if isinstance(output, str) and output.strip():
            return output.strip()
        return None
