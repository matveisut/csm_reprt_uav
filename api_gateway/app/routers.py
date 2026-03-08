from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import os
from app.auth import get_current_user

router = APIRouter()

ROUTE_PLANNER_URL = os.environ.get("ROUTE_PLANNER_URL", "http://route_planner:8001")
THREAT_ASSESSOR_URL = os.environ.get("THREAT_ASSESSOR_URL", "http://threat_assessor:8002")
TELEMETRY_PROCESSOR_URL = os.environ.get("TELEMETRY_PROCESSOR_URL", "http://telemetry_processor:8003")

async def forward_request(method: str, url: str, request: Request):
    headers = dict(request.headers)
    
    # Optional: cleanup headers to prevent host mismatches in internal routing
    headers.pop('host', None)
    
    body = await request.body()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method, 
                url, 
                headers=headers, 
                content=body,
                params=request.query_params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Internal service error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@router.post("/routes/plan")
async def plan_route(request: Request, current_user: dict = Depends(get_current_user)):
    url = f"{ROUTE_PLANNER_URL}/plan"
    return await forward_request("POST", url, request)

@router.patch("/routes/replan")
async def replan_route(request: Request, current_user: dict = Depends(get_current_user)):
    url = f"{ROUTE_PLANNER_URL}/replan"
    return await forward_request("PATCH", url, request)

@router.get("/threats/assess")
async def assess_threats(request: Request, current_user: dict = Depends(get_current_user)):
    url = f"{THREAT_ASSESSOR_URL}/assess"
    return await forward_request("GET", url, request)
