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
    mkdir -p "$WEIGHTS_DIR"

    echo "Downloading LibreFace weights to $WEIGHTS_DIR ..."
    if python -m libreface.cli download-weights --output "$WEIGHTS_DIR" 2>/dev/null; then
        echo "✓ Weights downloaded successfully via LibreFace CLI"
        return 0
    fi

    echo "LibreFace CLI unavailable; falling back to manual download from GitHub releases..."

    ZIP_URL=${LIBREFACE_WEIGHTS_URL:-https://github.com/ihp-lab/LibreFace/releases/download/v0.1.1/libreface_weights.zip}
    TMP_DIR=$(mktemp -d)
    ZIP_FILE="$TMP_DIR/libreface_weights.zip"

    if command -v curl >/dev/null 2>&1; then
        if ! curl -L -o "$ZIP_FILE" "$ZIP_URL"; then
            echo "ERROR: Failed to download weights archive with curl"
            rm -rf "$TMP_DIR"
            exit 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -O "$ZIP_FILE" "$ZIP_URL"; then
            echo "ERROR: Failed to download weights archive with wget"
            rm -rf "$TMP_DIR"
            exit 1
        fi
    else
        echo "ERROR: Neither curl nor wget is available to download weights"
        rm -rf "$TMP_DIR"
        exit 1
    fi

    EXTRACT_DIR="$TMP_DIR/extracted"
    mkdir -p "$EXTRACT_DIR"
    if ! unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR"; then
        echo "ERROR: Failed to unzip downloaded weights archive"
        rm -rf "$TMP_DIR"
        exit 1
    fi

    declare -A REQUIRED_FILES=(
        [detector]="detector.onnx face_detector.onnx"
        [expression]="expression.onnx expression_model.onnx"
        [action_units]="action_units.onnx au_model.onnx action_units_model.onnx"
        [landmarks]="landmarks_2d.tflite face_landmarks.tflite landmarks.tflite landmarks.onnx"
    )

    for category in "${!REQUIRED_FILES[@]}"; do
        candidates=${REQUIRED_FILES[$category]}
        primary=$(echo "$candidates" | awk '{print $1}')
        found_file=""
        for candidate in $candidates; do
            candidate_path=$(find "$EXTRACT_DIR" -name "$candidate" -print -quit)
            if [ -n "$candidate_path" ]; then
                found_file="$candidate_path"
                break
            fi
        done
        if [ -n "$found_file" ]; then
            cp "$found_file" "$WEIGHTS_DIR/$primary"
            echo "  ✓ ${category} weights -> $(basename "$primary")"
        else
            echo "  ⚠ WARNING: Could not find weights for ${category} in archive"
        fi
    done

    # Copy any remaining files for reference (optional)
    find "$EXTRACT_DIR" -maxdepth 1 -type f -name "*.pt" -exec cp {} "$WEIGHTS_DIR/" \;

    rm -rf "$TMP_DIR"
    echo "✓ Manual weight download complete"
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
    WORKERS=1

    echo "Starting gRPC Facial Analysis Server..."
    echo "  Port: $PORT"
    echo "  Device: $DEVICE"
    echo "  Workers: $WORKERS"
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
