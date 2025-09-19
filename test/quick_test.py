#!/usr/bin/env python3
"""
Quick CPU load test for camera uploads
"""
import requests
import threading
import time
import psutil
from concurrent.futures import ThreadPoolExecutor

def monitor_cpu():
    """Monitor CPU usage"""
    readings = []
    monitoring = True
    
    def collect():
        while monitoring:
            cpu = psutil.cpu_percent(interval=0.5)
            readings.append(cpu)
            print(f"CPU: {cpu:5.1f}%", end='\r')
            
    thread = threading.Thread(target=collect)
    thread.start()
    
    return readings, lambda: setattr(monitor_cpu, 'monitoring', False)

def test_upload(user_id):
    """Single upload test"""
    try:
        # Create fake image data
        image_data = b'FAKE_IMAGE_DATA' * 1000  # ~15KB
        
        files = {'capture_0': ('test.jpg', image_data, 'image/jpeg')}
        data = {'session_id': 'test_session_123'}
        
        start = time.time()
        resp = requests.post('http://localhost:5000/assessment/camera/upload', 
                           files=files, data=data, timeout=10)
        duration = time.time() - start
        
        return {
            'user': user_id,
            'time': duration, 
            'status': resp.status_code,
            'ok': resp.status_code == 200
        }
    except Exception as e:
        return {'user': user_id, 'time': 0, 'status': 'error', 'ok': False, 'error': str(e)}

def main():
    print("🔥 Quick CPU Load Test - 60 concurrent camera uploads")
    
    # Start monitoring
    readings, stop_monitor = monitor_cpu()
    
    start_time = time.time()
    
    # Run 60 concurrent uploads
    with ThreadPoolExecutor(max_workers=60) as executor:
        futures = [executor.submit(test_upload, i) for i in range(60)]
        results = [f.result() for f in futures]
    
    total_time = time.time() - start_time
    stop_monitor()
    
    # Stats
    successful = [r for r in results if r['ok']]
    avg_cpu = sum(readings) / len(readings) if readings else 0
    max_cpu = max(readings) if readings else 0
    
    print(f"\n📊 Results:")
    print(f"   Time: {total_time:.1f}s")
    print(f"   Success: {len(successful)}/60")
    print(f"   Avg CPU: {avg_cpu:.1f}%")
    print(f"   Max CPU: {max_cpu:.1f}%")
    
    if len(successful) < 60:
        errors = [r for r in results if not r['ok']]
        print(f"   Errors: {[r.get('error', r['status']) for r in errors[:3]]}")

if __name__ == "__main__":
    main()