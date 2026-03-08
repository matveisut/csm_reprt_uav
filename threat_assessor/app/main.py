from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import os
import asyncpg
import json

app = FastAPI(title="Threat Assessor Service", version="1.0.0")

class SegmentData(BaseModel):
    id: int
    geometry_geojson: str

class AssessmentRequest(BaseModel):
    segments: list[SegmentData]

class SegmentAssessment(BaseModel):
    segment_id: int
    p_att: float

class AssessmentResponse(BaseModel):
    results: list[SegmentAssessment]

DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")

# Replace prefix for asyncpg if it's there
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

async def get_db_pool():
    # Simple unpooled connection for demo, in production use asyncpg.create_pool
    # Reverting back to standard postgresql:// for asyncpg connect
    conn_url = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")
    return await asyncpg.connect(conn_url)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "threat_assessor"}

@app.post("/assess", response_model=AssessmentResponse)
async def assess_threats(payload: AssessmentRequest):
    """
    Evaluates P_att for each provided segment.
    P_att(e_ij) = 1 - \prod_k (1 - p_k * w_k)
    For a segment, we first identify which threats geometrically intersect or are within radius.
    For simplicity, we query threats in the DB whose location overlaps the segment geometry buffered by radius.
    """
    conn = await get_db_pool()
    results = []
    
    try:
        # P_att calculation logic
        for segment in payload.segments:
            # First, fetch all active threats that intersect with the segment buffer
            # We use PostGIS ST_DWithin to check distance
            query = """
                SELECT probability, criticality 
                FROM threats 
                WHERE is_active = TRUE
                AND ST_DWithin(
                    location::geography, 
                    ST_GeomFromGeoJSON($1)::geography, 
                    radius_m
                )
            """
            threats = await conn.fetch(query, segment.geometry_geojson)
            
            p_att = 0.0
            if threats:
                product_term = 1.0
                for t in threats:
                    pk = t['probability']
                    wk = t['criticality']
                    product_term *= (1.0 - (pk * wk))
                p_att = 1.0 - product_term
            
            results.append(SegmentAssessment(segment_id=segment.id, p_att=p_att))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()
        
    return AssessmentResponse(results=results)
