import os
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.core.log_path import resolve_log_file_path

router = APIRouter()

@router.get("/stream")
async def stream_logs():
 
    log_file_path = resolve_log_file_path()

    if not os.path.exists(log_file_path):
        raise HTTPException(status_code=404, detail=f"Log file not found: {log_file_path}")

    async def log_generator():
        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)

            while True:
                line = f.readline()
                if line:
                    yield line
                else:
                    await asyncio.sleep(0.3)

    return StreamingResponse(log_generator(), media_type="text/plain")
