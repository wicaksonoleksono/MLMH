"""
gRPC Client for Facial Analysis

This client is used by Flask application to communicate with
the separate gRPC inference server.
"""

import grpc
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import generated proto files
# Support both direct execution and module execution
try:
    # Try relative import first (when run as module)
    from ..generated import inference_pb2
    from ..generated import inference_pb2_grpc
except ImportError:
    # Fallback for direct execution
    generated_path = Path(__file__).parent.parent / 'generated'
    sys.path.insert(0, str(generated_path))
    import inference_pb2
    import inference_pb2_grpc

class FacialInferenceClient:
    """Client for facial analysis gRPC service"""

    def __init__(self, host: str, port: int, timeout: Optional[int] = None):
        """
        Initialize gRPC client

        Args:
            host: gRPC server host (required)
            port: gRPC server port (required)
            timeout: Request timeout in seconds (None = infinite, for long image processing)
        """
        if not host or not port:
            raise ValueError("host and port are required - NO DEFAULTS")

        self.address = f'{host}:{port}'
        # For image processing: use infinite timeout (None)
        # Images can take minutes to process, especially with many images
        self.timeout = timeout  # None = no timeout
        self.channel = None
        self.stub = None

    def connect(self):
        """Establish connection to gRPC server"""
        try:
            self.channel = grpc.insecure_channel(self.address)
            self.stub = inference_pb2_grpc.FacialInferenceStub(self.channel)
            return True
        except Exception as e:
            print(f"Failed to connect to gRPC server at {self.address}: {e}")
            return False

    def disconnect(self):
        """Close connection to gRPC server"""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None

    def health_check(self) -> Dict[str, Any]:
        """
        Check if gRPC server is healthy

        Returns:
            {
                'healthy': bool,
                'message': str
            }
        """
        if not self.stub:
            if not self.connect():
                return {'healthy': False, 'message': 'Cannot connect to server'}

        try:
            request = inference_pb2.HealthRequest()
            response = self.stub.HealthCheck(request, timeout=self.timeout)

            return {
                'healthy': response.healthy,
                'message': response.message
            }
        except grpc.RpcError as e:
            return {
                'healthy': False,
                'message': f'gRPC error: {e.details()}'
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error: {str(e)}'
            }

    def analyze_image(self, image_path: str, device: str = 'cpu', retry_count: int = 0) -> Dict[str, Any]:
        """
        Analyze facial expression in image with retry logic

        Args:
            image_path: Absolute path to image file
            device: 'cpu' or 'cuda:0'
            retry_count: Internal retry counter (don't set manually)

        Returns:
            {
                'success': bool,
                'error_message': str,
                'facial_expression': str,
                'head_pose': {'pitch': float, 'yaw': float, 'roll': float},
                'action_units': {'au_1': int, 'au_2': int, ...},
                'au_intensities': {'au_1': float, 'au_2': float, ...},
                'key_landmarks': [{'index': int, 'x': float, 'y': float, 'z': float}, ...],
                'processing_time_ms': int
            }
        """
        max_retries = 3

        if not self.stub:
            if not self.connect():
                return {
                    'success': False,
                    'error_message': 'Cannot connect to gRPC server'
                }

        try:
            # Create request
            request = inference_pb2.ImageRequest(
                image_path=image_path,
                device=device
            )

            # Call gRPC service with NO timeout for long image processing
            response = self.stub.AnalyzeImage(request, timeout=self.timeout)

            # Convert protobuf to dict
            result = {
                'success': response.success,
                'error_message': response.error_message,
                'facial_expression': response.facial_expression,
                'head_pose': {
                    'pitch': response.head_pose.pitch,
                    'yaw': response.head_pose.yaw,
                    'roll': response.head_pose.roll
                },
                'action_units': {
                    'au_1': response.action_units.au_1,
                    'au_2': response.action_units.au_2,
                    'au_4': response.action_units.au_4,
                    'au_5': response.action_units.au_5,
                    'au_6': response.action_units.au_6,
                    'au_9': response.action_units.au_9,
                    'au_12': response.action_units.au_12,
                    'au_15': response.action_units.au_15,
                    'au_17': response.action_units.au_17,
                    'au_20': response.action_units.au_20,
                    'au_25': response.action_units.au_25,
                    'au_26': response.action_units.au_26
                },
                'au_intensities': {
                    'au_1': response.au_intensities.au_1,
                    'au_2': response.au_intensities.au_2,
                    'au_4': response.au_intensities.au_4,
                    'au_5': response.au_intensities.au_5,
                    'au_6': response.au_intensities.au_6,
                    'au_9': response.au_intensities.au_9,
                    'au_12': response.au_intensities.au_12,
                    'au_15': response.au_intensities.au_15,
                    'au_17': response.au_intensities.au_17,
                    'au_20': response.au_intensities.au_20,
                    'au_25': response.au_intensities.au_25,
                    'au_26': response.au_intensities.au_26
                },
                'key_landmarks': [
                    {
                        'index': landmark.index,
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z
                    }
                    for landmark in response.key_landmarks
                ],
                'processing_time_ms': response.processing_time_ms
            }

            return result

        except grpc.RpcError as e:
            error_msg = f'gRPC error: {e.details()}'
            print(f"[gRPC ERROR] {error_msg} (attempt {retry_count + 1}/{max_retries})")

            # Retry on transient errors
            if retry_count < max_retries and e.code() in [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED]:
                print(f"[RETRY] Retrying image: {image_path}")
                import time
                time.sleep(1)  # Wait before retry
                return self.analyze_image(image_path, device, retry_count + 1)

            return {
                'success': False,
                'error_message': error_msg
            }
        except Exception as e:
            error_msg = f'Error: {str(e)}'
            print(f"[EXCEPTION] {error_msg} (attempt {retry_count + 1}/{max_retries})")

            # Retry on transient errors
            if retry_count < max_retries:
                print(f"[RETRY] Retrying image: {image_path}")
                import time
                time.sleep(1)
                return self.analyze_image(image_path, device, retry_count + 1)

            return {
                'success': False,
                'error_message': error_msg
            }

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Convenience function for one-off analysis
def analyze_image(image_path: str, device: str = 'cpu',
                  host: str = 'localhost', port: int = 50051) -> Dict[str, Any]:
    """
    Analyze image using gRPC service (convenience function)

    Args:
        image_path: Absolute path to image
        device: 'cpu' or 'cuda:0'
        host: gRPC server host
        port: gRPC server port

    Returns:
        Analysis result dict
    """
    with FacialInferenceClient(host=host, port=port) as client:
        return client.analyze_image(image_path, device=device)


if __name__ == '__main__':
    # Test the client
    import sys

    if len(sys.argv) < 2:
        print("Usage: python inference_client.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"Analyzing: {image_path}")

    # Health check
    with FacialInferenceClient() as client:
        health = client.health_check()
        print(f"Health: {health}")

        if health['healthy']:
            # Analyze image
            result = client.analyze_image(image_path)
            print(f"\nResult: {result}")
