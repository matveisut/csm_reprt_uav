CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. БПЛА (UAVs)
CREATE TABLE IF NOT EXISTS uavs (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'IDLE', -- IDLE, IN_FLIGHT, REPLANNING, ALERT
    current_location GEOMETRY(Point, 4326),
    last_telemetry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Зоны риска
CREATE TABLE IF NOT EXISTS risk_zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    area GEOMETRY(Polygon, 4326),
    base_threat_level FLOAT CHECK (base_threat_level >= 0 AND base_threat_level <= 1)
);

-- 3. Угрозы (Информационная безопасность)
CREATE TABLE IF NOT EXISTS threats (
    id SERIAL PRIMARY KEY,
    vector_type VARCHAR(50) NOT NULL, -- GPS_SPOOFING, MAVLINK_INTERCEPT, DOS
    probability FLOAT NOT NULL CHECK (probability >= 0 AND probability <= 1), -- p_k
    criticality FLOAT NOT NULL CHECK (criticality >= 0 AND criticality <= 1), -- w_k
    location GEOMETRY(Point, 4326),
    radius_m FLOAT DEFAULT 1000.0, -- Радиус действия угрозы в метрах
    is_active BOOLEAN DEFAULT TRUE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Граф маршрутизации: Узлы
CREATE TABLE IF NOT EXISTS graph_nodes (
    id SERIAL PRIMARY KEY,
    location GEOMETRY(Point, 4326) NOT NULL
);

-- 5. Граф маршрутизации: Ребра (Сегменты)
CREATE TABLE IF NOT EXISTS graph_edges (
    id SERIAL PRIMARY KEY,
    source_node INTEGER REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_node INTEGER REFERENCES graph_nodes(id) ON DELETE CASCADE,
    base_time FLOAT NOT NULL, -- T_ref для сегмента (в секундах)
    r_link FLOAT NOT NULL CHECK (r_link >= 0 AND r_link <= 1), -- Надежность связи (R_link)
    geometry GEOMETRY(LineString, 4326)
);

-- 6. Маршруты
CREATE TABLE IF NOT EXISTS routes (
    id SERIAL PRIMARY KEY,
    uav_id INTEGER REFERENCES uavs(id) ON DELETE CASCADE,
    planned_path GEOMETRY(LineString, 4326),
    q_metric FLOAT, -- Метрика Q (Интегральная доверенная эффективность)
    estimated_time FLOAT, -- T_route (Расчетное время)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для оптимизации гео-запросов
CREATE INDEX idx_uavs_location ON uavs USING GIST (current_location);
CREATE INDEX idx_risk_zones_area ON risk_zones USING GIST (area);
CREATE INDEX idx_threats_location ON threats USING GIST (location);
CREATE INDEX idx_graph_nodes_location ON graph_nodes USING GIST (location);
CREATE INDEX idx_graph_edges_geometry ON graph_edges USING GIST (geometry);
CREATE INDEX idx_routes_planned_path ON routes USING GIST (planned_path);
