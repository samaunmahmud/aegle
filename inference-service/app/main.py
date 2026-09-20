"""Aegle inference service.

Internal service: called by the Core API, never directly by browsers.
Uploads are processed in memory and are not written to disk or logged.
"""
from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from .base import ModelUnavailable
from .imaging import MAX_UPLOAD_BYTES, UnsupportedImage, decode_image
from .registry import Registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.registry = Registry()
    yield


app = FastAPI(title="Aegle Inference Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    reg: Registry = app.state.registry
    return {
        "status": "ok" if reg.loaded() else "degraded",
        "models_loaded": [m.info.id for m in reg.loaded()],
        "models_unavailable": reg.unavailable(),
    }


@app.get("/v1/models")
def list_models():
    reg: Registry = app.state.registry
    return {"models": [asdict(m.info) for m in reg.loaded()]}


@app.post("/v1/models/{model_id}/predict")
async def predict(
    model_id: str,
    file: UploadFile = File(...),
    heatmap: bool = Query(True, description="Include a Grad-CAM overlay"),
):
    reg: Registry = app.state.registry
    try:
        adapter = reg.get(model_id)
    except KeyError:
        raise HTTPException(404, f"Unknown model '{model_id}'")
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc))

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        image = decode_image(data)
    except UnsupportedImage as exc:
        raise HTTPException(422, str(exc))

    out = adapter.predict(image, explain=heatmap)
    return {
        "model": asdict(adapter.info),
        "top_label": out.predictions[0].label,
        "predictions": [asdict(p) for p in out.predictions],
        "heatmap": None if out.heatmap is None else {
            "method": out.heatmap.method,
            "target_label": out.heatmap.target_label,
            "format": "png",
            "image_base64": base64.b64encode(out.heatmap.png).decode("ascii"),
        },
    }
