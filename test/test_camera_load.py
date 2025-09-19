#!/usr/bin/env python3
"""
Load test for camera upload endpoint to simulate 60 concurrent users
Monitors CPU usage during the test
"""
import asyncio
import aiohttp
import aiofiles
import time
import psutil
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import json

# Test configuration
BASE_URL = "http://localhost:5000"  # Adjust to your Flask app URL
CONCURRENT_USERS = 60
UPLOADS_PER_USER = 3
TEST_IMAGE_SIZE = 1024 * 500  # 500KB per image (typical camera capture)

class CPUMonitor:
    def __init__(self):
        self.monitoring = False
        self.cpu_readings = []
        
    def start(self):
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_cpu)
        self.monitor_thread.start()
        
    def stop(self):
        self.monitoring = False
        self.monitor_thread.join()
        
    def _monitor_cpu(self):
        while self.monitoring:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            self.cpu_readings.append({
                'time': time.time(),
                'cpu': cpu_percent,
                'memory': memory_percent
            })
            print(f"CPU: {cpu_percent:5.1f}% | Memory: {memory_percent:5.1f}%")
            
    def get_stats(self):
        if not self.cpu_readings:
            return {}
        
        cpu_values = [r['cpu'] for r in self.cpu_readings]
        memory_values = [r['memory'] for r in self.cpu_readings]
        
        return {
            'avg_cpu': sum(cpu_values) / len(cpu_values),
            'max_cpu': max(cpu_values),
            'avg_memory': sum(memory_values) / len(memory_values),
            'max_memory': max(memory_values),
            'readings_count': len(self.cpu_readings)
        }

async def create_test_image(size_bytes):
    """Create a test image file in memory"""
    import io
    from PIL import Image
    
    # Create a simple test image
    img = Image.new('RGB', (640, 480), color='red')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=85)
    img_buffer.seek(0)
    
    # Pad to desired size if needed
    data = img_buffer.getvalue()
    if len(data) < size_bytes:
        padding = b'0' * (size_bytes - len(data))
        data += padding
    
    return data[:size_bytes]

async def login_and_get_session(session):
    """Login and get a valid session_id"""
    # You'll need to adjust this based on your auth system
    login_data = {
        'username': 'test_user',  # Adjust to valid test user
        'password': 'test_pass'
    }
    
    try:
        async with session.post(f"{BASE_URL}/auth/login", data=login_data) as resp:
            if resp.status != 200:
                print(f"Login failed: {resp.status}")
                return None
                
        # Get or create a test session
        async with session.post(f"{BASE_URL}/assessment/start") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('session_id')
    except Exception as e:
        print(f"Login error: {e}")
        return None

async def upload_camera_capture(session, session_id, user_id, upload_id):
    """Simulate a single camera upload"""
    try:
        # Create test image
        image_data = await create_test_image(TEST_IMAGE_SIZE)
        
        # Prepare form data
        data = aiohttp.FormData()
        data.add_field('session_id', session_id)
        data.add_field('capture_0', image_data, 
                      filename=f'test_user_{user_id}_upload_{upload_id}.jpg',
                      content_type='image/jpeg')
        data.add_field('metadata_0', json.dumps({
            'trigger': 'INTERVAL',
            'timestamp': time.time(),
            'test_user': user_id
        }))
        
        start_time = time.time()
        async with session.post(f"{BASE_URL}/assessment/camera/upload", data=data) as resp:
            end_time = time.time()
            
            result = {
                'user_id': user_id,
                'upload_id': upload_id,
                'status': resp.status,
                'response_time': end_time - start_time,
                'success': resp.status == 200
            }
            
            if resp.status != 200:
                text = await resp.text()
                result['error'] = text[:200]  # First 200 chars of error
                
            return result
            
    except Exception as e:
        return {
            'user_id': user_id,
            'upload_id': upload_id,
            'status': 'error',
            'response_time': 0,
            'success': False,
            'error': str(e)
        }

async def simulate_user(user_id, session_id):
    """Simulate one user doing multiple uploads"""
    results = []
    
    async with aiohttp.ClientSession() as session:
        # Do multiple uploads per user
        tasks = []
        for upload_id in range(UPLOADS_PER_USER):
            task = upload_camera_capture(session, session_id, user_id, upload_id)
            tasks.append(task)
            
        # Execute all uploads for this user concurrently
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in user_results:
            if isinstance(result, Exception):
                results.append({
                    'user_id': user_id,
                    'status': 'exception',
                    'success': False,
                    'error': str(result)
                })
            else:
                results.append(result)
                
    return results

async def run_load_test():
    """Main load test function"""
    print(f"🚀 Starting load test:")
    print(f"   👥 {CONCURRENT_USERS} concurrent users")
    print(f"   📸 {UPLOADS_PER_USER} uploads per user")
    print(f"   💾 {TEST_IMAGE_SIZE} bytes per image")
    print(f"   📊 Total uploads: {CONCURRENT_USERS * UPLOADS_PER_USER}")
    print()
    
    # Start CPU monitoring
    cpu_monitor = CPUMonitor()
    cpu_monitor.start()
    
    # You'll need a valid session_id - adjust this
    # For testing, you might need to create test sessions beforehand
    test_session_id = "test_session_123"  # Replace with valid session
    
    try:
        start_time = time.time()
        
        # Create tasks for all users
        user_tasks = []
        for user_id in range(CONCURRENT_USERS):
            task = simulate_user(user_id, test_session_id)
            user_tasks.append(task)
        
        print(f"⏳ Executing {len(user_tasks)} concurrent user simulations...")
        
        # Execute all users concurrently
        all_results = await asyncio.gather(*user_tasks, return_exceptions=True)
        
        end_time = time.time()
        
        # Stop monitoring
        cpu_monitor.stop()
        
        # Process results
        total_uploads = 0
        successful_uploads = 0
        failed_uploads = 0
        total_response_time = 0
        errors = []
        
        for user_results in all_results:
            if isinstance(user_results, Exception):
                errors.append(str(user_results))
                continue
                
            for result in user_results:
                total_uploads += 1
                if result['success']:
                    successful_uploads += 1
                    total_response_time += result['response_time']
                else:
                    failed_uploads += 1
                    if 'error' in result:
                        errors.append(f"User {result['user_id']}: {result['error']}")
        
        # Calculate stats
        total_time = end_time - start_time
        avg_response_time = total_response_time / successful_uploads if successful_uploads > 0 else 0
        throughput = successful_uploads / total_time if total_time > 0 else 0
        
        cpu_stats = cpu_monitor.get_stats()
        
        # Print results
        print("\n" + "="*60)
        print("📊 LOAD TEST RESULTS")
        print("="*60)
        print(f"⏱️  Total test time: {total_time:.2f} seconds")
        print(f"📤 Total uploads attempted: {total_uploads}")
        print(f"✅ Successful uploads: {successful_uploads}")
        print(f"❌ Failed uploads: {failed_uploads}")
        print(f"📈 Success rate: {(successful_uploads/total_uploads*100):.1f}%")
        print(f"⚡ Average response time: {avg_response_time:.3f} seconds")
        print(f"🔥 Throughput: {throughput:.1f} uploads/second")
        print()
        print("💻 SYSTEM PERFORMANCE:")
        print(f"🔴 Average CPU usage: {cpu_stats.get('avg_cpu', 0):.1f}%")
        print(f"🔴 Peak CPU usage: {cpu_stats.get('max_cpu', 0):.1f}%")
        print(f"💾 Average memory usage: {cpu_stats.get('avg_memory', 0):.1f}%")
        print(f"💾 Peak memory usage: {cpu_stats.get('max_memory', 0):.1f}%")
        
        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for error in errors[:10]:  # Show first 10 errors
                print(f"   • {error}")
            if len(errors) > 10:
                print(f"   ... and {len(errors) - 10} more errors")
                
    except Exception as e:
        cpu_monitor.stop()
        print(f"💥 Test failed: {e}")

if __name__ == "__main__":
    # Install required packages first:
    # pip install aiohttp aiofiles psutil pillow
    
    print("🧪 Camera Upload Load Test")
    print("=" * 40)
    
    # Check if required packages are installed
    try:
        import aiohttp, aiofiles, psutil
        from PIL import Image
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Install with: pip install aiohttp aiofiles psutil pillow")
        exit(1)
    
    asyncio.run(run_load_test())