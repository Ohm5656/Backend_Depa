#!/usr/bin/env python3
"""
Script สำหรับรัน backend_middle แบบ local development
"""

import os
import sys
from pathlib import Path

def main():
    print("🚀 Starting Backend Middle - Local Development")
    print("=" * 50)
    
    # ตรวจสอบว่าโมเดลมีอยู่หรือไม่
    model_dir = Path("Model")
    required_models = ["size.pt", "shrimp.pt", "din.pt", "water_class.pt"]
    
    missing_models = []
    for model in required_models:
        model_path = model_dir / model
        if not model_path.exists():
            missing_models.append(model)
    
    if missing_models:
        print("⚠️  Warning: Missing model files:")
        for model in missing_models:
            print(f"   - {model}")
        print("\n💡 You can still run the server, but AI processing will fail.")
        print("   Make sure to place the model files in the Model/ directory.")
        print()
    
    # ตั้งค่า environment
    from local_config import setup_local_env, create_local_directories, setup_sample_data
    
    print("📋 Setting up local environment...")
    setup_local_env()
    create_local_directories()
    setup_sample_data()
    
    print("\n🌐 Starting FastAPI server...")
    print("📡 API Endpoints:")
    print("   - POST /process          - Upload and process files")
    print("   - POST /data             - Receive sensor data")
    print("   - POST /data_ponds       - Receive pond information")
    print("   - GET  /ponds/{id}/status - Get pond status")
    print("   - GET  /ponds/{id}/shrimp_size - Get shrimp size data")
    print("   - GET  /list             - List files")
    print("   - GET  /view             - View file content")
    print()
    
    # รัน server
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    
    try:
        uvicorn.run(
            "main_local:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
