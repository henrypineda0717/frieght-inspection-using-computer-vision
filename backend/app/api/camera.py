"""
Camera-related helpers such as streaming proxies.
"""
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Camera"])


@router.get("/camera-proxy")
async def proxy_camera_stream(url: str = Query(..., description="Full URL to the camera stream")):
    """
    Proxy the remote camera stream through the backend so that the frontend can load it from the same origin.
    """
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Camera URL must start with http:// or https://")

    client = httpx.AsyncClient(timeout=None)
    stream_context = client.stream("GET", url, timeout=None, headers={"User-Agent": "ContainerInspectionProxy"})
    response = await stream_context.__aenter__()

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        await stream_context.__aexit__(None, None, None)
        await client.aclose()
        raise HTTPException(status_code=exc.response.status_code, detail=f"Camera returned {exc.response.status_code}")

    media_type = response.headers.get("content-type", "application/octet-stream")

    async def stream_content() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in response.aiter_bytes(chunk_size=16_384):
                if chunk:
                    yield chunk
        except httpx.StreamClosed:
            return
        finally:
            await stream_context.__aexit__(None, None, None)
            await client.aclose()

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": media_type
    }

    return StreamingResponse(
        stream_content(),
        status_code=response.status_code,
        headers=headers
    )
