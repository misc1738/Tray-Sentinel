"""
FastAPI application for SmartGrid Sentinel (MVP)
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import asyncio

from config.settings import settings
from services.orchestrator import SmartGridOrchestrator
from database.connection import init_db, get_db
from database.models import Incident
from ai.retrainer import retrain_from_feedback


# mount static files and templates
templates = Jinja2Templates(directory="ui/templates")

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")

orchestrator = SmartGridOrchestrator()


class SensorReadingInput(BaseModel):
    sensor_id: str
    sensor_type: str
    value: float
    timestamp: Optional[datetime] = None


@app.get("/")
async def root():
    return {"service": settings.app_name, "version": settings.app_version, "status": "operational"}


@app.post("/sensors/process")
async def process_sensors(readings: List[SensorReadingInput], background_tasks: BackgroundTasks):
    sensor_data = [r.dict() for r in readings]
    result = await orchestrator.process_sensor_data_stream(sensor_data)
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('error'))
    return result


@app.on_event("startup")
async def startup_event():
    # initialize DB tables
    init_db()


@app.get('/incidents')
async def list_incidents():
    db = get_db()
    try:
        rows = db.query(Incident).order_by(Incident.created_at.desc()).limit(100).all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "sensor_ids": r.sensor_ids,
                "risk_label": r.risk_label,
                "risk_score": r.risk_score,
                "explanation": r.explanation,
                "recommendations": r.recommendations,
                "feedback": r.feedback,
            })
        return {"count": len(out), "incidents": out}
    finally:
        db.close()


class FeedbackInput(BaseModel):
    incident_id: str
    feedback: str  # true_positive | false_positive
    feedback_by: Optional[str] = None
    correct_label: Optional[str] = None


@app.post('/feedback')
async def submit_feedback(payload: FeedbackInput):
    db = get_db()
    try:
        inc = db.query(Incident).filter(Incident.id == payload.incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")
        inc.feedback = payload.feedback
        inc.feedback_by = payload.feedback_by
        if payload.correct_label:
            inc.correct_label = payload.correct_label
        inc.feedback_at = datetime.utcnow()
        db.add(inc)
        db.commit()
        return {"success": True}
    finally:
        db.close()


@app.get('/ui')
async def ui_dashboard(request: Request):
    db = get_db()
    try:
        rows = db.query(Incident).order_by(Incident.created_at.desc()).limit(100).all()
        incidents = []
        for r in rows:
            incidents.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "sensor_ids": r.sensor_ids,
                "risk_label": r.risk_label,
                "risk_score": r.risk_score,
                "explanation": r.explanation,
                "recommendations": r.recommendations,
                "feedback": r.feedback,
            })
        return templates.TemplateResponse('dashboard.html', {"request": request, "incidents": incidents})
    finally:
        db.close()


@app.post('/feedback', response_class=RedirectResponse)
async def ui_submit_feedback(incident_id: str = Form(...), feedback: str = Form(...), feedback_by: Optional[str] = Form(None)):
    db = get_db()
    try:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")
        inc.feedback = feedback
        inc.feedback_by = feedback_by
        # allow optional corrected label via a hidden form field named 'correct_label'
        # (dashboard can be extended to include a select box for corrected label)
        # if present in form data, it'll be added here
        # note: Request.Form doesn't include fields not in signature; dashboard currently doesn't send correct_label
        # this is a placeholder for future enhancement
        inc.feedback_at = datetime.utcnow()
        db.add(inc)
        db.commit()
        return RedirectResponse(url='/ui', status_code=303)
    finally:
        db.close()


@app.post('/admin/retrain-risk')
async def admin_retrain_risk(background_tasks: BackgroundTasks, min_samples: int = 10):
    """Trigger retraining from operator-corrected incidents (runs in background)."""
    # run retraining in background to avoid blocking API
    def run():
        res = retrain_from_feedback(min_samples=min_samples)
        # best-effort: log result
        import logging
        logging.getLogger(__name__).info("Retrain result: %s", res)

    background_tasks.add_task(run)
    return {"status": "retrain_queued"}


@app.get('/health')
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
