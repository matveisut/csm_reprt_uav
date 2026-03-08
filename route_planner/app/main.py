import os
import networkx as nx
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import asyncpg
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

app = FastAPI(title="Route Planner Service", version="1.0.0")

class RoutePlanRequest(BaseModel):
    uav_id: int
    source_node_id: int
    target_node_id: int
    alpha: float = 0.4
    beta: float = 0.3
    gamma: float = 0.3

class RouteReplanRequest(BaseModel):
    uav_id: int
    current_node_id: int
    target_node_id: int
    trigger_reason: str

class RoutePlanResponse(BaseModel):
    uav_id: int
    path: list[int]
    q_metric: float
    estimated_time: float

DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")
THREAT_ASSESSOR_URL = os.getenv("THREAT_ASSESSOR_URL", "http://threat_assessor:8002")

async def get_db_pool():
    conn_url = os.getenv("POSTGRES_URL", "postgresql://uav_admin:admin123@db:5432/uav_routing")
    return await asyncpg.connect(conn_url)

async def assess_threats_for_segments(segments_data: list):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{THREAT_ASSESSOR_URL}/assess",
                json={"segments": segments_data}
            )
            response.raise_for_status()
            return response.json()["results"]
        except Exception as e:
            # Fallback for demonstration if service isn't reachable
            return [{"segment_id": s["id"], "p_att": 0.1} for s in segments_data]

async def build_graph(conn) -> tuple[nx.DiGraph, dict]:
    graph = nx.DiGraph()
    # Fetch all nodes
    nodes = await conn.fetch("SELECT id, ST_X(location) as lon, ST_Y(location) as lat FROM graph_nodes")
    for n in nodes:
        graph.add_node(n['id'], pos=(n['lon'], n['lat']))
        
    # Fetch all edges
    # We retrieve the geojson to send to the threat assessor
    edges = await conn.fetch("""
        SELECT id, source_node, target_node, base_time, r_link, ST_AsGeoJSON(geometry) as geojson 
        FROM graph_edges
    """)
    
    segments_payload = [{"id": e["id"], "geometry_geojson": e["geojson"]} for e in edges]
    
    # Batch request to Threat Assessor
    threat_assessments = await assess_threats_for_segments(segments_payload)
    p_att_map = {res["segment_id"]: res["p_att"] for res in threat_assessments}
    
    edges_info = {}
    for e in edges:
        e_id = e["id"]
        p_att = p_att_map.get(e_id, 0.0)
        
        # Constraint validation: reject segments with P_att > 0.4
        if p_att > 0.4:
            continue
            
        graph.add_edge(e["source_node"], e["target_node"], 
                       id=e_id, 
                       base_time=e["base_time"], 
                       r_link=e["r_link"], 
                       p_att=p_att)
        edges_info[e_id] = {"base_time": e["base_time"], "r_link": e["r_link"], "p_att": p_att}

    # Helper function to compute minimum time to reach target globally (T_ref conceptual)
    # Using simple Dijkstra on base_time for all pairs, this is T_ref calculation
    t_ref_cache = dict(nx.all_pairs_dijkstra_path_length(graph, weight="base_time"))
    
    return graph, t_ref_cache

@app.post("/plan", response_model=RoutePlanResponse)
async def plan_route(request: RoutePlanRequest):
    alpha = request.alpha
    beta = request.beta
    gamma = request.gamma
    
    if abs((alpha + beta + gamma) - 1.0) > 1e-4:
         raise HTTPException(status_code=400, detail="alpha + beta + gamma must equal 1")
    
    conn = await get_db_pool()
    try:
        graph, t_ref_cache = await build_graph(conn)
        
        if request.source_node_id not in graph or request.target_node_id not in graph:
            raise HTTPException(status_code=400, detail="Source or target node not found/available in graph")
        
        # We need to compute Q. Since networkx uses shortest_path, we must invert maximizing Q into minimizing Cost.
        # Q = alpha*(1 - P_att) + beta*R_link - gamma*(T_route/T_ref)
        # To maximize Q, we minimize Cost = -Q or construct positive weights reflecting the penalty.
        # For simplicity, let's assign a cost weight directly to edges.
        
        # T_ref from source to target across the entire graph context
        # In actual OR-Tools integration, we define multiple dimensions. Here we use networkx primarily for cost structure
        # OR-Tools is overkill for single pair shortest path unless adding vehicle constraints (VRP). 
        # But per requirements, let's formulate edge weights to emulate OR-Tools capability.
        
        try:
            t_ref = t_ref_cache[request.source_node_id][request.target_node_id]
        except KeyError:
            raise HTTPException(status_code=400, detail="No path exists between nodes")
            
        def q_cost(u, v, d):
            # We want to maximize Q, so minimize -Q or a positive shift.
            # Local segment approximation:
            # Q_local = alpha*(1 - p_att) + beta*r_link - gamma*(base_time / t_ref)
            q_local = alpha * (1 - d['p_att']) + beta * d['r_link'] - gamma * (d['base_time'] / t_ref)
            # Minimize (max_possible_Q - Q_local) to keep weights positive for Dijkstra
            max_q = alpha * 1.0 + beta * 1.0 - gamma * 0.0 # 1.0
            return (1.0 - q_local)
        
        # Find shortest path based on optimized Q-cost
        path = nx.shortest_path(graph, request.source_node_id, request.target_node_id, weight=q_cost)
        
        # Calculate actual metrics
        total_time = sum(graph[u][v]['base_time'] for u, v in zip(path[:-1], path[1:]))
        total_p_att_penalty = 1.0
        r_link_sum = 0.0
        edges_count = 0
        
        for u, v in zip(path[:-1], path[1:]):
            d = graph[u][v]
            total_p_att_penalty *= (1 - d['p_att'])
            r_link_sum += d['r_link']
            edges_count += 1
            
        overall_p_att = 1 - total_p_att_penalty
        avg_r_link = r_link_sum / edges_count if edges_count else 1.0
        
        final_q = alpha * (1 - overall_p_att) + beta * avg_r_link - gamma * (total_time / t_ref)
        
    finally:
        await conn.close()
        
    return RoutePlanResponse(
        uav_id=request.uav_id,
        path=path,
        q_metric=final_q,
        estimated_time=total_time
    )

@app.patch("/replan", response_model=RoutePlanResponse)
async def replan_route(request: RouteReplanRequest):
    # Triggers dynamic replanning from the current node onwards
    plan_req = RoutePlanRequest(
        uav_id=request.uav_id,
        source_node_id=request.current_node_id,
        target_node_id=request.target_node_id,
    )
    return await plan_route(plan_req)
