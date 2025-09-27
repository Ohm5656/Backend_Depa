"""
Local Development Version ของ main.py
ใช้ local_config.py เพื่อตั้งค่า environment variables
"""

# ตั้งค่า environment variables ก่อน import อื่นๆ
from local_config import setup_local_env, create_local_directories
setup_local_env()
create_local_directories()

# Import main application
from main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 Starting local development server on port {port}")
    print(f"📁 Storage directory: {os.environ.get('STORAGE_DIR')}")
    print(f"🌐 File base URL: {os.environ.get('FILE_BASE_URL')}")
    uvicorn.run("main_local:app", host="0.0.0.0", port=port, reload=True)
