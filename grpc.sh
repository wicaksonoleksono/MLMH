#!/bin/bash
# gRPC Facial Analysis Server Management Script
# Usage: ./grpc.sh {start|stop|restart|status|install-weights}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Log and PID files
LOG_FILE="grpc_server.log"
PID_FILE="grpc_server.pid"

# Load environment variables
load_env() {
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
}

# Download LibreFace weights into project root
download_weights() {
    activate_venv

    WEIGHTS_DIR="$SCRIPT_DIR/weights_libreface"

    echo "Downloading LibreFace weights to $WEIGHTS_DIR ..."
    echo "This will use LibreFace's automatic download feature..."

    # Create a temporary Python script to trigger weight download
    TMP_SCRIPT=$(mktemp --suffix=.py)
    cat > "$TMP_SCRIPT" << 'PYTHON_EOF'
import os
import sys
from pathlib import Path

try:
    import libreface

    # Get the weights directory argument
    weights_dir = sys.argv[1] if len(sys.argv) > 1 else "./weights_libreface"
    weights_path = Path(weights_dir).resolve()
    weights_path.mkdir(parents=True, exist_ok=True)

    print(f"Triggering LibreFace weight download to: {weights_path}")

    # LibreFace automatically downloads weights when initialized
    # We'll use a dummy image path to trigger the download
    # The actual processing doesn't matter, we just need to trigger weight download

    # Create a minimal test to trigger weight download
    import numpy as np
    from PIL import Image

    # Create a dummy image (required to trigger initialization)
    dummy_img = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8))
    dummy_path = weights_path / "dummy_test.jpg"
    dummy_img.save(dummy_path)

    # This will trigger automatic weight download
    try:
        # Set the weights directory via environment variable if supported
        os.environ['LIBREFACE_WEIGHTS_DIR'] = str(weights_path)

        result = libreface.get_facial_attributes(
            str(dummy_path),
            weights_download_dir=str(weights_path)
        )
        print("✓ Weights downloaded successfully!")

        # Clean up dummy file
        dummy_path.unlink()

    except Exception as e:
        print(f"Note: Weight download triggered but processing failed (expected): {e}")
        print("Checking if weights were downloaded...")

        # Check if any weight files exist
        weight_files = list(weights_path.glob("*.onnx")) + list(weights_path.glob("*.tflite")) + list(weights_path.glob("*.pt"))
        if weight_files:
            print(f"✓ Found {len(weight_files)} weight files:")
            for wf in weight_files:
                print(f"  - {wf.name}")
        else:
            print("⚠ WARNING: No weight files found. LibreFace may download weights on first actual use.")
            sys.exit(1)

        # Clean up dummy file if it exists
        if dummy_path.exists():
            dummy_path.unlink()

except ImportError as e:
    print(f"ERROR: LibreFace not installed properly: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Failed to download weights: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

    # Run the Python script with the weights directory
    if python "$TMP_SCRIPT" "$WEIGHTS_DIR"; then
        rm "$TMP_SCRIPT"
        echo "✓ LibreFace weights installation complete at $WEIGHTS_DIR"
        echo ""
        echo "Weight files downloaded:"
        ls -lh "$WEIGHTS_DIR"
        return 0
    else
        rm "$TMP_SCRIPT"
        echo "ERROR: Failed to download LibreFace weights"
        echo ""
        echo "Alternative: Weights will be auto-downloaded on first inference run."
        echo "The server will download weights automatically when processing the first image."
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    if [ -f venv.libre/bin/activate ]; then
        source venv.libre/bin/activate
    else
        echo "ERROR: venv.libre/bin/activate not found"
        exit 1
    fi
}

# Check if server is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Start server
start_server() {
    if is_running; then
        echo "ERROR: gRPC server is already running (PID: $(cat $PID_FILE))"
        exit 1
    fi

    # Clean up stale PID file
    [ -f "$PID_FILE" ] && rm "$PID_FILE"

    load_env
    activate_venv

    # Configuration from .env (no fallbacks)
    if [ -z "$GRPC_FACIAL_ANALYSIS_PORT" ] || [ -z "$GRPC_FACIAL_ANALYSIS_DEVICE" ]; then
        echo "ERROR: Missing required .env variables:"
        echo "  - GRPC_FACIAL_ANALYSIS_PORT"
        echo "  - GRPC_FACIAL_ANALYSIS_DEVICE"
        exit 1
    fi

    PORT=$GRPC_FACIAL_ANALYSIS_PORT
    DEVICE=$GRPC_FACIAL_ANALYSIS_DEVICE
    WORKERS=4              # Parallel inference threads for faster processing

    echo "Starting gRPC Facial Analysis Server..."
    echo "  Port: $PORT"
    echo "  Device: $DEVICE"
    echo "  Workers: $WORKERS (parallel inference threads)"
    echo "  Log: $LOG_FILE"

    nohup python app/facial_analysis/server/inference_server.py \
        --port "$PORT" \
        --device "$DEVICE" \
        --workers "$WORKERS" \
        > "$LOG_FILE" 2>&1 &

    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"

    sleep 1

    if is_running; then
        echo "✓ gRPC server started (PID: $SERVER_PID)"
        echo "  View logs: tail -f $LOG_FILE"
    else
        echo "ERROR: Failed to start server"
        exit 1
    fi
}

# Stop server
stop_server() {
    if ! is_running; then
        echo "gRPC server is not running"
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
        exit 0
    fi

    PID=$(cat "$PID_FILE")
    echo "Stopping gRPC server (PID: $PID)..."
    kill "$PID"

    # Wait for process to stop (up to 5 seconds)
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "✓ Server stopped successfully"
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo "Force killing server..."
    kill -9 "$PID"
    sleep 1

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "ERROR: Could not stop server"
        exit 1
    else
        echo "✓ Server stopped"
        rm "$PID_FILE"
    fi
}

# Restart server
restart_server() {
    echo "Restarting gRPC server..."
    stop_server
    sleep 1
    start_server
}

# Show status
show_status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        load_env
        echo "gRPC Facial Analysis Server"
        echo "  Status: Running"
        echo "  PID: $PID"
        echo "  Port: ${GRPC_FACIAL_ANALYSIS_PORT:-unknown}"
        echo "  Device: ${GRPC_FACIAL_ANALYSIS_DEVICE:-unknown}"
        echo "  Log: $LOG_FILE"
    else
        echo "gRPC Facial Analysis Server"
        echo "  Status: Stopped"
    fi
}

# Main
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    install-weights)
        download_weights
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|install-weights}"
        exit 1
        ;;
esac
