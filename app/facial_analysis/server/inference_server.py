"""
gRPC Server for Facial Analysis using LibreFace

This server runs SEPARATELY from Flask application.
Port: 50051
Purpose: Stateless image inference only
"""

import grpc
from concurrent import futures
import time
import sys
import os
from pathlib import Path

# Import generated proto files
# Support both direct execution and module execution
try:
    # Try relative import first (when run as module)
    from ..generated import inference_pb2
    from ..generated import inference_pb2_grpc
except ImportError:
    # Fallback for direct execution (python server/inference_server.py)
    import sys
    from pathlib import Path
    generated_path = Path(__file__).parent.parent / 'generated'
    sys.path.insert(0, str(generated_path))
    import inference_pb2
    import inference_pb2_grpc
# Import LibreFace
try:
    import libreface
    LIBREFACE_AVAILABLE = True
except ImportError:
    print("WARNING: LibreFace not installed. Install from: https://github.com/ihp-lab/LibreFace")
    LIBREFACE_AVAILABLE = False
    libreface = None


# Key landmarks indices (from important.md)
KEY_LANDMARKS = {
    # Left Eye
    'left_eye_outer': 33,
    'left_eye_inner': 133,
    'left_eye_upper_lid': 159,
    'left_eye_lower_lid': 145,

    # Right Eye
    'right_eye_outer': 263,
    'right_eye_inner': 362,
    'right_eye_upper_lid': 386,
    'right_eye_lower_lid': 374,

    # Left Brow
    'left_brow_outer': 46,
    'left_brow_mid': 105,
    'left_brow_inner': 70,

    # Right Brow
    'right_brow_outer': 276,
    'right_brow_mid': 334,
    'right_brow_inner': 300,

    # Mouth
    'mouth_left': 61,
    'mouth_right': 291,
    'mouth_upper': 13,
    'mouth_lower': 14,

    # Nose
    'nose_bridge': 1,
    'nose_tip': 0,

    # Chin
    'chin': 152,

    # Cheeks
    'left_cheek': 234,
    'right_cheek': 454,

    # Forehead
    'forehead': 10
}


class FacialInferenceServicer(inference_pb2_grpc.FacialInferenceServicer):
    """gRPC service implementation for facial analysis"""

    def __init__(self, device='cpu'):
        """
        Initialize LibreFace

        Args:
            device: 'cpu' or 'cuda:0'
        """
        self.device = device
        self.weights_dir = './weights_libreface'

        if LIBREFACE_AVAILABLE:
            print(f"LibreFace available on {device}")
        else:
            print("LibreFace NOT available")

    def HealthCheck(self, request, context):
        """Health check endpoint"""
        if LIBREFACE_AVAILABLE:
            return inference_pb2.HealthResponse(
                healthy=True,
                message=f"LibreFace inference service running on {self.device}"
            )
        else:
            return inference_pb2.HealthResponse(
                healthy=False,
                message="LibreFace not installed"
            )

    def AnalyzeImage(self, request, context):
        """Analyze facial expression in image"""
        start_time = time.time()

        # Validate LibreFace is available
        if not LIBREFACE_AVAILABLE:
            return inference_pb2.ImageResponse(
                success=False,
                error_message="LibreFace not installed"
            )

        # Validate image exists
        if not os.path.exists(request.image_path):
            return inference_pb2.ImageResponse(
                success=False,
                error_message=f"Image not found: {request.image_path}"
            )

        try:
            # Get facial attributes using LibreFace
            result = libreface.get_facial_attributes_image(
                request.image_path,
                device=self.device,
                weights_download_dir=self.weights_dir
            )

            # Handle both DataFrame and dict return types
            if hasattr(result, 'to_dict'):
                result = result.to_dict('records')[0]

            # Extract facial expression
            facial_expression = result.get('facial_expression', 'Unknown')

            # Extract head pose
            head_pose = inference_pb2.HeadPose(
                pitch=float(result.get('head_pose_pitch', 0.0)),
                yaw=float(result.get('head_pose_yaw', 0.0)),
                roll=float(result.get('head_pose_roll', 0.0))
            )

            # Extract Action Units (binary)
            action_units = inference_pb2.ActionUnits(
                au_1=int(result.get('AU_1', 0)),
                au_2=int(result.get('AU_2', 0)),
                au_4=int(result.get('AU_4', 0)),
                au_5=int(result.get('AU_5', 0)),
                au_6=int(result.get('AU_6', 0)),
                au_9=int(result.get('AU_9', 0)),
                au_12=int(result.get('AU_12', 0)),
                au_15=int(result.get('AU_15', 0)),
                au_17=int(result.get('AU_17', 0)),
                au_20=int(result.get('AU_20', 0)),
                au_25=int(result.get('AU_25', 0)),
                au_26=int(result.get('AU_26', 0))
            )

            # Extract Action Unit intensities
            au_intensities = inference_pb2.ActionUnitIntensities(
                au_1=float(result.get('AU_1_intensity', 0.0)),
                au_2=float(result.get('AU_2_intensity', 0.0)),
                au_4=float(result.get('AU_4_intensity', 0.0)),
                au_5=float(result.get('AU_5_intensity', 0.0)),
                au_6=float(result.get('AU_6_intensity', 0.0)),
                au_9=float(result.get('AU_9_intensity', 0.0)),
                au_12=float(result.get('AU_12_intensity', 0.0)),
                au_15=float(result.get('AU_15_intensity', 0.0)),
                au_17=float(result.get('AU_17_intensity', 0.0)),
                au_20=float(result.get('AU_20_intensity', 0.0)),
                au_25=float(result.get('AU_25_intensity', 0.0)),
                au_26=float(result.get('AU_26_intensity', 0.0))
            )

            # Extract key landmarks (25 important points)
            key_landmarks = []
            landmarks_data = result.get('landmarks', [])

            if landmarks_data:
                for name, idx in KEY_LANDMARKS.items():
                    if idx < len(landmarks_data):
                        landmark = landmarks_data[idx]
                        key_landmarks.append(inference_pb2.Landmark(
                            index=idx,
                            x=float(landmark.get('x', 0.0)),
                            y=float(landmark.get('y', 0.0)),
                            z=float(landmark.get('z', 0.0))
                        ))

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Return successful response
            return inference_pb2.ImageResponse(
                success=True,
                error_message="",
                facial_expression=facial_expression,
                head_pose=head_pose,
                action_units=action_units,
                au_intensities=au_intensities,
                key_landmarks=key_landmarks,
                processing_time_ms=processing_time_ms
            )

        except Exception as e:
            return inference_pb2.ImageResponse(
                success=False,
                error_message=f"Analysis failed: {str(e)}"
            )


def serve(port=50051, device='cpu', max_workers=1):
    """
    Start gRPC server

    Args:
        port: Port to listen on (default 50051)
        device: 'cpu' or 'cuda:0'
        max_workers: Number of worker threads (default 1 for sequential processing)
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    # Add servicer
    inference_pb2_grpc.add_FacialInferenceServicer_to_server(
        FacialInferenceServicer(device=device),
        server
    )

    # Start server
    server.add_insecure_port(f'[::]:{port}')
    server.start()

    print(f"=" * 60)
    print(f"Facial Analysis gRPC Server started")
    print(f"Port: {port}")
    print(f"Device: {device}")
    print(f"Workers: {max_workers}")
    print(f"LibreFace: {'Loaded' if LIBREFACE_AVAILABLE else 'NOT AVAILABLE'}")
    print(f"=" * 60)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nShutting down gRPC server...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Get config from environment - NO FALLBACKS
    default_port = os.getenv('GRPC_FACIAL_ANALYSIS_PORT')
    default_device = os.getenv('GRPC_FACIAL_ANALYSIS_DEVICE')

    if not default_port or not default_device:
        print("ERROR: Missing required environment variables in .env:")
        print("  - GRPC_FACIAL_ANALYSIS_PORT")
        print("  - GRPC_FACIAL_ANALYSIS_DEVICE")
        sys.exit(1)

    default_port = int(default_port)

    parser = argparse.ArgumentParser(description='Facial Analysis gRPC Server')
    parser.add_argument('--port', type=int, default=default_port, help=f'Port to listen on (default: {default_port} from .env)')
    parser.add_argument('--device', type=str, default=default_device, help=f'Device: cpu or cuda:0 (default: {default_device} from .env)')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker threads')

    args = parser.parse_args()

    serve(port=args.port, device=args.device, max_workers=args.workers)
