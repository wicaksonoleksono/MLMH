#!/usr/bin/env python3
"""
Simple load test for camera uploads using requests
"""
import requests
import threading
import time
import psutil
import os
from concurrent.futures import ThreadPoolExecutor
import json

# Configuration
BASE_URL = "http://localhost:5000"
CONCURRENT_USERS = 60
TEST_IMAGE_SIZE = 1024 * 500  # 500KB

def monitor_system():
    """Monitor CPU and memory usage"""
    readings = []
    def collect():
        while getattr(collect, 'running', True):
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
            readings.append({'cpu': cpu, 'memory': memory})
            print(f"CPU: {cpu:5.1f}% | Memory: {memory:5.1f}%")
    
    thread = threading.Thread(target=collect)
    thread.start()
    return thread, readings

def create_test_image():
    """Create test image data"""
    # Simple fake image data
    header = b'\xff\xd8\xff\xe0'  # JPEG header
    data = header + (b'A' * (TEST_IMAGE_SIZE - len(header)))
    return data

def upload_test(user_id, session_id="test_session"):
    """Single upload test"""
    try:
        start_time = time.time()
        
        # Create test data
        image_data = create_test_image()
        
        files = {
            'capture_0': ('test.jpg', image_data, 'image/jpeg')
        }
        data = {
            'session_id': session_id,
            'metadata_0': json.dumps({
                'trigger': 'INTERVAL',
                'timestamp': time.time()
            })
        }
        
        # Make request
        response = requests.post(
            f"{BASE_URL}/assessment/camera/upload",
            files=files,
            data=data,
            timeout=30
        )
        
        end_time = time.time()
        
        return {
            'user_id': user_id,
            'status_code': response.status_code,
            'response_time': end_time - start_time,
            'success': response.status_code == 200,
            'response_size': len(response.content)
        }
        
    except Exception as e:
        return {
            'user_id': user_id,
            'status_code': 'error',
            'response_time': 0,
            'success': False,
            'error': str(e)
        }

def run_load_test():
    """Run the load test"""
    print(f"🚀 Starting camera upload load test")
    print(f"   Users: {CONCURRENT_USERS}")
    print(f"   Image size: {TEST_IMAGE_SIZE} bytes")
    print(f"   Target: {BASE_URL}/assessment/camera/upload")
    print()
    
    # Start monitoring
    monitor_thread, readings = monitor_system()
    
    try:
        start_time = time.time()
        
        # Run concurrent uploads
        with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
            futures = []
            for i in range(CONCURRENT_USERS):
                future = executor.submit(upload_test, i)
                futures.append(future)
            
            # Collect results
            results = []
            for future in futures:
                results.append(future.result())
        
        end_time = time.time()
        
        # Stop monitoring
        monitor_thread.running = False
        monitor_thread.join()
        
        # Calculate stats
        total_time = end_time - start_time
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        if successful:
            avg_response_time = sum(r['response_time'] for r in successful) / len(successful)
            max_response_time = max(r['response_time'] for r in successful)
            min_response_time = min(r['response_time'] for r in successful)
        else:
            avg_response_time = max_response_time = min_response_time = 0
        
        # CPU stats
        if readings:
            avg_cpu = sum(r['cpu'] for r in readings) / len(readings)
            max_cpu = max(r['cpu'] for r in readings)
            avg_memory = sum(r['memory'] for r in readings) / len(readings)
            max_memory = max(r['memory'] for r in readings)
        else:
            avg_cpu = max_cpu = avg_memory = max_memory = 0
        
        # Print results
        print("\n" + "="*50)
        print("📊 LOAD TEST RESULTS")
        print("="*50)
        print(f"⏱️  Total time: {total_time:.2f}s")
        print(f"👥 Concurrent users: {CONCURRENT_USERS}")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"📈 Success rate: {len(successful)/len(results)*100:.1f}%")
        print(f"⚡ Avg response time: {avg_response_time:.3f}s")
        print(f"⚡ Min response time: {min_response_time:.3f}s")
        print(f"⚡ Max response time: {max_response_time:.3f}s")
        print(f"🔥 Throughput: {len(successful)/total_time:.1f} req/s")
        print()
        print("💻 SYSTEM PERFORMANCE:")
        print(f"🔴 Avg CPU: {avg_cpu:.1f}%")
        print(f"🔴 Max CPU: {max_cpu:.1f}%")
        print(f"💾 Avg Memory: {avg_memory:.1f}%")
        print(f"💾 Max Memory: {max_memory:.1f}%")
        
        # Show errors
        if failed:
            print(f"\n❌ ERRORS ({len(failed)}):")
            for fail in failed[:5]:  # Show first 5 errors
                error = fail.get('error', f"HTTP {fail['status_code']}")
                print(f"   User {fail['user_id']}: {error}")
            if len(failed) > 5:
                print(f"   ... and {len(failed) - 5} more errors")
        
        print("\n" + "="*50)
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        monitor_thread.running = False
    except Exception as e:
        print(f"💥 Test failed: {e}")
        monitor_thread.running = False

if __name__ == "__main__":
    print("🧪 Simple Camera Upload Load Test")
    print("=" * 40)
    
    # Check if Flask app is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Flask app is running (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Cannot reach Flask app at {BASE_URL}")
        print(f"   Error: {e}")
        print("   Make sure your Flask app is running first!")
        exit(1)
    
    run_load_test()