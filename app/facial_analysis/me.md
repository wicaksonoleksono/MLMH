# Facial Analysis gRPC Service

## Setup

1. Install gRPC tools:

```bash
pip install grpcio grpcio-tools

```

2. Install LibreFace (in separate conda env):

```bash
conda create -n libreface python=3.9
conda activate libreface
pip install --upgrade libreface
# Follow LibreFace installation: https://github.com/ihp-lab/LibreFace
```

## Generate Python code from proto

```bash
cd /home/wicaksonolxn/Documents/KJ/MH/facial_analysis
python -m grpc_tools.protoc -I. \
  --python_out=generated \
  --grpc_python_out=generated \
  inference.proto
```

## Run the gRPC server

Server reads configuration from `/home/wicaksonolxn/Documents/KJ/MH/.env`:

- `GRPC_FACIAL_ANALYSIS_PORT`
- `GRPC_FACIAL_ANALYSIS_DEVICE`

**Foreground:**

```bash
cd /home/wicaksonolxn/Documents/KJ/MH/facial_analysis.service
conda activate libreface
python server/inference_server.py
```

**Background:**

```bash
cd /home/wicaksonolxn/Documents/KJ/MH/facial_analysis.service
conda activate libreface
nohup python server/inference_server.py > grpc_server.log 2>&1 &
```

**Check logs:**

```bash
tail -f grpc_server.log
```

**Stop background server:**

```bash
pkill -f inference_server.py
```

## Architecture

- **Port**: From `.env` (GRPC_FACIAL_ANALYSIS_PORT)
- **Device**: From `.env` (GRPC_FACIAL_ANALYSIS_DEVICE)
- **Separate from Flask**: Runs independently
- **Purpose**: LibreFace inference only
- **No database access**: Stateless image processing
