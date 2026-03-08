import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
from datetime import datetime

app = FastAPI(title="Telemetry Processor Service", version="1.0.0")

class TelemetryPayload(BaseModel):
    uav_id: int
    current_node_id: int
    target_node_id: int
    delay_ms: int
    deviation_m: float
    timestamp: datetime
    has_threat_notification: bool = False

class TriggerResponse(BaseModel):
    replan_triggered: bool
    reason: str | None

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api_gateway:8000")
DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")

async def get_db_pool():
    conn_url = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")
    return await asyncpg.connect(conn_url)

async def trigger_replan(payload: TelemetryPayload, reason: str):
    # Sends patch to Gateway /routes/replan
    async with httpx.AsyncClient() as client:
        try:
            # Token logic could be added here for internal gateway auth bypass or internal admin token
            response = await client.patch(
                f"{API_GATEWAY_URL}/routes/replan",
                json={
                    "uav_id": payload.uav_id,
                    "current_node_id": payload.current_node_id,
                    "target_node_id": payload.target_node_id,
                    "trigger_reason": reason
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to trigger replanning: {str(e)}")

@app.post("/ingest", response_model=TriggerResponse)
async def ingest_telemetry(payload: TelemetryPayload):
    trigger = False
    reason = None
    
    # 1. Поступление уведомления об угрозе от службы мониторинга.
    if payload.has_threat_notification:
        trigger = True
        reason = "System threat notification received."
        
    # 2. Превышение задержки телеметрии более 200 мс (признак DoS-атаки).
    elif payload.delay_ms > 200:
        trigger = True
        reason = f"Telemetry delay exceeded 200ms ({payload.delay_ms}ms)."
        
    # 3. Отклонение БПЛА от плановой траектории более чем на 15 метров.
    elif payload.deviation_m > 15:
        trigger = True
        reason = f"UAV deviation exceeded 15m ({payload.deviation_m}m)."
        
    if trigger:
        # Update UAV status in DB
        conn = await get_db_pool()
        try:
            await conn.execute("UPDATE uavs SET status = 'REPLANNING' WHERE id = $1", payload.uav_id)
        finally:
            await conn.close()
            
        await trigger_replan(payload, reason)
        return TriggerResponse(replan_triggered=True, reason=reason)
        
    return TriggerResponse(replan_triggered=False, reason="Nominal flight parameters")
