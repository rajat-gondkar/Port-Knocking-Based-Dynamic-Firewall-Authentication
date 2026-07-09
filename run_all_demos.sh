#!/bin/bash
# Run all Port Knocking demo servers in the background

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Original Port Knocking Server (Dashboard: http://localhost:8084) ..."
(cd "$SCRIPT_DIR" && python3 main.py) &
PID1=$!

echo "Starting IPS Demo Server (Dashboard: http://localhost:8081) ..."
(cd "$SCRIPT_DIR/demo_ips" && python3 main.py) &
PID2=$!

echo "Starting TOTP Demo Server (Dashboard: http://localhost:8082) ..."
(cd "$SCRIPT_DIR/demo_totp" && python3 main.py) &
PID3=$!

echo "Starting GeoIP Demo Server (Dashboard: http://localhost:8083) ..."
(cd "$SCRIPT_DIR/demo_geoip" && python3 main.py) &
PID4=$!

echo ""
echo "==========================================="
echo "All 4 backend engines are now running!"
echo ""
echo "  🏠 Hub (Home):     http://localhost:8084"
echo "  🔐 Original:       http://localhost:8084/dashboard"
echo "  🛡️  IPS Mode:       http://localhost:8081"
echo "  ⏱️  TOTP Mode:      http://localhost:8082"
echo "  🌍 GeoIP Mode:     http://localhost:8083"
echo "==========================================="
echo "Press Ctrl+C to gracefully stop all servers."

trap "echo 'Shutting down servers...'; kill $PID1 $PID2 $PID3 $PID4 2>/dev/null; exit" SIGINT SIGTERM
wait
