@echo off
set VENV_PYTHON=..\venv\Scripts\python.exe

echo Running API Gateway Tests
cd api_gateway
%VENV_PYTHON% -m pytest tests
cd ..

echo.
echo Running Telemetry Processor Tests
cd telemetry_processor
%VENV_PYTHON% -m pytest tests
cd ..

echo.
echo Running Threat Assessor Tests
cd threat_assessor
%VENV_PYTHON% -m pytest tests
cd ..

echo.
echo Running Route Planner Tests
cd route_planner
%VENV_PYTHON% -m pytest tests
cd ..

echo All tests completed.
