#!/usr/bin/env python3
"""
Deployment checker for MLMH production setup
Run this on production server to verify paths and configuration
"""

import os
import sys

def check_production_setup():
    """Check if production paths are correctly configured"""
    
    print("🔍 MLMH Production Deployment Checker")
    print("=" * 50)
    
    # Check if we're in production environment
    prod_path = '/var/www/MLMH'
    is_production = os.path.exists(prod_path)
    
    print(f"📍 Environment: {'PRODUCTION' if is_production else 'DEVELOPMENT'}")
    print(f"📂 Root path: {prod_path if is_production else 'current directory'}")
    
    if not is_production:
        print("⚠️  Not in production environment - checks will be limited")
        return
    
    # Check critical paths
    paths_to_check = [
        f"{prod_path}/wsgi.py",
        f"{prod_path}/app/__init__.py", 
        f"{prod_path}/app/static",
        f"{prod_path}/app/static/js",
        f"{prod_path}/app/static/js/core/api.js",
        f"{prod_path}/app/static/css",
        f"{prod_path}/app/templates",
        f"{prod_path}/app/static/uploads",
        f"{prod_path}/.env"
    ]
    
    print("\n📋 Critical Path Checks:")
    all_good = True
    
    for path in paths_to_check:
        exists = os.path.exists(path)
        status = "✅" if exists else "❌"
        print(f"{status} {path}")
        if not exists:
            all_good = False
    
    # Check if static files are readable
    print("\n📄 Static File Accessibility:")
    js_files = [
        f"{prod_path}/app/static/js/core/api.js",
        f"{prod_path}/app/static/js/shared/refreshDetection.js", 
        f"{prod_path}/app/static/js/shared/cameraManager.js"
    ]
    
    for js_file in js_files:
        if os.path.exists(js_file):
            try:
                with open(js_file, 'r') as f:
                    content = f.read(100)  # Read first 100 chars
                print(f"✅ {js_file} (readable)")
            except Exception as e:
                print(f"❌ {js_file} (permission error: {e})")
                all_good = False
        else:
            print(f"❌ {js_file} (not found)")
            all_good = False
    
    # Check permissions
    print("\n🔐 Permission Checks:")
    for path in [f"{prod_path}/app/static", f"{prod_path}/app/static/uploads"]:
        if os.path.exists(path):
            readable = os.access(path, os.R_OK)
            writable = os.access(path, os.W_OK)
            print(f"{'✅' if readable else '❌'} {path} - Read: {readable}, Write: {writable}")
            if not readable:
                all_good = False
        else:
            print(f"❌ {path} (not found)")
            all_good = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_good:
        print("🎉 All checks passed! Production deployment looks good.")
    else:
        print("⚠️  Some issues found. Check the ❌ items above.")
        print("\nCommon fixes:")
        print("- Ensure all files are deployed to /var/www/MLMH")
        print("- Check file permissions (www-data should have read access)")
        print("- Verify static files are in correct locations")
        print("- Restart web server after fixes")
    
    return all_good

if __name__ == "__main__":
    check_production_setup()