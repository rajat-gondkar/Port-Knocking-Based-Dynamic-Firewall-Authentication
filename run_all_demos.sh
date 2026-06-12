#!/bin/bash
echo "Starting Original Port Knocking Server (Dashboard: http://localhost:8084) ..."
python3 main.py &
PID1=$!

echo "Starting IPS Demo Server (Dashboard: http://localhost:8081) ..."
cd demo_ips && python3 main.py &
PID2=$!
cd ..

echo "Starting TOTP Demo Server (Dashboard: http://localhost:8082) ..."
cd demo_totp && python3 main.py &
PID3=$!
cd ..

echo "Starting GeoIP Demo Server (Dashboard: http://localhost:8083) ..."
cd demo_geoip && python3 main.py &
PID4=$!
cd ..

echo ""
echo "==========================================="
echo "All 4 backend engines are now running!"
echo "Open the Unified Dashboard here:"
echo "👉 http://localhost:8084"
echo "==========================================="
echo "Press Ctrl+C to gracefully stop all servers."

trap "echo 'Shutting down servers...'; kill $PID1 $PID2 $PID3 $PID4; exit" SIGINT SIGTERM
wait
