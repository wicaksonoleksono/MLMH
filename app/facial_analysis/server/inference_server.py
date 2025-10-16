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
from typing import Dict, List, Any

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

        root_path = Path(__file__).resolve().parents[2]
        self.weights_path = (root_path / 'weights_libreface').resolve()
        self.weights_path.mkdir(parents=True, exist_ok=True)
        self.weights_dir = str(self.weights_path)

        if LIBREFACE_AVAILABLE:
            print(f"LibreFace available on {device}")
        else:
            print("LibreFace NOT available")

    def HealthCheck(self, request, context):
        """Health check endpoint"""
        if not LIBREFACE_AVAILABLE:
            return inference_pb2.HealthResponse(
                healthy=False,
                message="LibreFace not installed"
            )

        return inference_pb2.HealthResponse(
            healthy=True,
            message=f"LibreFace inference service running on {self.device}"
        )

    def _normalize_libreface_result(self, raw_result: Any) -> Dict[str, Any]:
        """Normalize LibreFace output to consistent structure."""
        if raw_result is None:
            raw_result = {}

        # Convert DataFrame/list output to dict
        if hasattr(raw_result, 'to_dict'):
            records = raw_result.to_dict('records')
            raw = records[0] if records else {}
        elif isinstance(raw_result, list):
            raw = raw_result[0] if raw_result else {}
        else:
            raw = raw_result

        if not isinstance(raw, dict):
            raw = {}

        facial_expression = raw.get('facial_expression') or raw.get('expression') or 'Unknown'

        def _parse_float(value, default=0.0):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        head_pose = {
            'pitch': _parse_float(raw.get('head_pose_pitch') or raw.get('pitch') or raw.get('head_pitch')),
            'yaw': _parse_float(raw.get('head_pose_yaw') or raw.get('yaw') or raw.get('head_yaw')),
            'roll': _parse_float(raw.get('head_pose_roll') or raw.get('roll') or raw.get('head_roll')),
        }

        expected_binary_aus = ['au_1', 'au_2', 'au_4', 'au_5', 'au_6', 'au_9', 'au_12', 'au_15', 'au_17', 'au_20', 'au_25', 'au_26']
        expected_intensity_aus = expected_binary_aus

        detected_aus_source = raw.get('detected_aus')
        if not isinstance(detected_aus_source, dict):
            detected_aus_source = {}
            for key, value in raw.items():
                lower = str(key).lower()
                if lower.startswith('au_') and not lower.endswith('_intensity'):
                    detected_aus_source[lower] = value

        action_units = {}
        for au in expected_binary_aus:
            value = detected_aus_source.get(au)
            if value is None:
                value = detected_aus_source.get(au.upper())
            try:
                action_units[au] = int(round(float(value)))
            except (TypeError, ValueError):
                action_units[au] = 0

        intensities_source = raw.get('au_intensities')
        if not isinstance(intensities_source, dict):
            intensities_source = {}
            for key, value in raw.items():
                lower = str(key).lower()
                if lower.startswith('au_') and lower.endswith('_intensity'):
                    intensities_source[lower] = value

        au_intensities = {}
        for au in expected_intensity_aus:
            key_candidates = [
                f'{au}_intensity',
                f'{au.upper()}_intensity'
            ]
            matched_value = None
            for candidate in key_candidates:
                if candidate in intensities_source:
                    matched_value = intensities_source[candidate]
                    break
            try:
                au_intensities[au] = float(matched_value)
            except (TypeError, ValueError):
                au_intensities[au] = 0.0

        # Extract landmarks - LibreFace returns flattened format lm_mp_{index}_{x|y|z}
        landmarks = []

        # Try to find landmarks in flattened format (lm_mp_0_x, lm_mp_0_y, lm_mp_0_z, ...)
        landmark_indices = set()
        for key in raw.keys():
            if key.startswith('lm_mp_'):
                # Extract index from key like 'lm_mp_123_x'
                parts = key.split('_')
                if len(parts) >= 4:
                    try:
                        index = int(parts[2])
                        landmark_indices.add(index)
                    except ValueError:
                        continue

        # Reconstruct landmarks from flattened keys
        for idx in sorted(landmark_indices):
            x_key = f'lm_mp_{idx}_x'
            y_key = f'lm_mp_{idx}_y'
            z_key = f'lm_mp_{idx}_z'

            if x_key in raw and y_key in raw and z_key in raw:
                try:
                    landmarks.append({
                        'index': int(idx),
                        'x': float(raw[x_key]),
                        'y': float(raw[y_key]),
                        'z': float(raw[z_key])
                    })
                except (TypeError, ValueError):
                    continue

        return {
            'facial_expression': facial_expression,
            'head_pose': head_pose,
            'action_units': action_units,
            'au_intensities': au_intensities,
            'landmarks': landmarks
        }

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
            normalized = self._normalize_libreface_result(result)

            facial_expression = normalized['facial_expression']

            head_pose = inference_pb2.HeadPose(
                pitch=normalized['head_pose']['pitch'],
                yaw=normalized['head_pose']['yaw'],
                roll=normalized['head_pose']['roll']
            )

            aus = normalized['action_units']
            action_units = inference_pb2.ActionUnits(
                au_1=int(aus.get('au_1', 0)),
                au_2=int(aus.get('au_2', 0)),
                au_4=int(aus.get('au_4', 0)),
                au_5=int(aus.get('au_5', 0)),
                au_6=int(aus.get('au_6', 0)),
                au_9=int(aus.get('au_9', 0)),
                au_12=int(aus.get('au_12', 0)),
                au_15=int(aus.get('au_15', 0)),
                au_17=int(aus.get('au_17', 0)),
                au_20=int(aus.get('au_20', 0)),
                au_25=int(aus.get('au_25', 0)),
                au_26=int(aus.get('au_26', 0))
            )

            intensities = normalized['au_intensities']
            au_intensities = inference_pb2.ActionUnitIntensities(
                au_1=float(intensities.get('au_1', 0.0)),
                au_2=float(intensities.get('au_2', 0.0)),
                au_4=float(intensities.get('au_4', 0.0)),
                au_5=float(intensities.get('au_5', 0.0)),
                au_6=float(intensities.get('au_6', 0.0)),
                au_9=float(intensities.get('au_9', 0.0)),
                au_12=float(intensities.get('au_12', 0.0)),
                au_15=float(intensities.get('au_15', 0.0)),
                au_17=float(intensities.get('au_17', 0.0)),
                au_20=float(intensities.get('au_20', 0.0)),
                au_25=float(intensities.get('au_25', 0.0)),
                au_26=float(intensities.get('au_26', 0.0))
            )

            # Extract key landmarks (25 important points)
            key_landmarks = []
            landmarks_data = normalized['landmarks']
            if landmarks_data:
                landmarks_by_index = {lm['index']: lm for lm in landmarks_data if 'index' in lm}
                for name, idx in KEY_LANDMARKS.items():
                    landmark = landmarks_by_index.get(idx)
                    if landmark:
                        key_landmarks.append(inference_pb2.Landmark(
                            index=int(idx),
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
