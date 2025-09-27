"""
Local Development Configuration
ใช้สำหรับการพัฒนาแบบ localhost
"""

import os
from pathlib import Path

# =========================
# Local Development Settings
# =========================

def setup_local_env():
    """ตั้งค่า environment variables สำหรับ local development"""
    
    # Base directory ของโปรเจค
    BASE_DIR = Path(__file__).parent
    
    # Storage Configuration
    os.environ.setdefault("STORAGE_DIR", str(BASE_DIR / "local_storage"))
    os.environ.setdefault("LOCAL_STORAGE_BASE", str(BASE_DIR / "local_storage"))
    os.environ.setdefault("LOCAL_STORAGE_ROOT", str(BASE_DIR / "local_storage"))
    os.environ.setdefault("DATA_PONDS_DIR", str(BASE_DIR / "data_ponds"))
    
    # File Server Configuration
    os.environ.setdefault("FILE_BASE_URL", "http://localhost:8001")
    os.environ.setdefault("OUTPUT_DIR", str(BASE_DIR / "local_storage"))
    
    # Model Paths
    os.environ.setdefault("MODEL_SIZE", str(BASE_DIR / "Model" / "size.pt"))
    os.environ.setdefault("MODEL_SHRIMP", str(BASE_DIR / "Model" / "shrimp.pt"))
    os.environ.setdefault("MODEL_DIN", str(BASE_DIR / "Model" / "din.pt"))
    os.environ.setdefault("MODEL_WATER", str(BASE_DIR / "Model" / "water_class.pt"))
    
    # Output Directories
    os.environ.setdefault("OUTPUT_SIZE", str(BASE_DIR / "local_storage" / "size"))
    os.environ.setdefault("OUTPUT_SHRIMP", str(BASE_DIR / "local_storage" / "shrimp"))
    os.environ.setdefault("OUTPUT_DIN", str(BASE_DIR / "local_storage" / "din"))
    os.environ.setdefault("OUTPUT_WATER", str(BASE_DIR / "local_storage" / "water"))
    
    # Sensor Configuration
    os.environ.setdefault("SENSOR_DIR", str(BASE_DIR / "local_storage" / "sensor"))
    os.environ.setdefault("SENSOR_BASE", str(BASE_DIR / "local_storage" / "sensor"))
    os.environ.setdefault("POND_INFO_BASE", str(BASE_DIR / "data_ponds"))
    os.environ.setdefault("TXT_WATER_DIR", str(BASE_DIR / "output" / "water_output"))
    os.environ.setdefault("SAN_BASE", str(BASE_DIR / "local_storage" / "san"))
    
    # Backend URLs (ปล่อยว่างสำหรับ local development)
    os.environ.setdefault("APP_STATUS_URL", "")
    os.environ.setdefault("APP_SIZE_URL", "")
    
    # MQTT Configuration
    os.environ.setdefault("MQTT_BROKER", "broker.emqx.io")
    os.environ.setdefault("MQTT_PORT", "1883")
    
    # Port Configuration
    os.environ.setdefault("PORT", "8001")
    
    print("✅ Local development environment configured!")
    print(f"📁 Storage: {os.environ['STORAGE_DIR']}")
    print(f"🌐 Base URL: {os.environ['FILE_BASE_URL']}")
    print(f"🔌 Port: {os.environ['PORT']}")

# =========================
# Development Helper Functions
# =========================

def create_local_directories():
    """สร้างโฟลเดอร์ที่จำเป็นสำหรับ local development"""
    base_dir = Path(__file__).parent
    
    directories = [
        "local_storage/size",
        "local_storage/shrimp", 
        "local_storage/din",
        "local_storage/water",
        "local_storage/sensor",
        "local_storage/san",
        "local_storage/temp",
        "local_storage/processed_images",
        "data_ponds",
        "output/size_output",
        "output/shrimp_output", 
        "output/din_output",
        "output/water_output",
        "input_raspi1",
        "input_raspi2",
        "input_video"
    ]
    
    for dir_path in directories:
        full_path = base_dir / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created: {full_path}")

def setup_sample_data():
    """สร้างข้อมูลตัวอย่างสำหรับทดสอบ"""
    import json
    from datetime import datetime
    
    base_dir = Path(__file__).parent
    
    # Sample pond data
    pond_data = {
        "pond_id": 1,
        "pond_size_rai": 1.5,
        "initial_stock": 30000,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    pond_file = base_dir / "data_ponds" / "pond_1_sample.json"
    with open(pond_file, "w", encoding="utf-8") as f:
        json.dump(pond_data, f, ensure_ascii=False, indent=2)
    
    # Sample sensor data
    sensor_data = {
        "pond_id": 1,
        "ph": 7.2,
        "temperature": 28.5,
        "do": 6.8,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    sensor_file = base_dir / "local_storage" / "sensor" / "sensor_sample.json"
    with open(sensor_file, "w", encoding="utf-8") as f:
        json.dump(sensor_data, f, ensure_ascii=False, indent=2)
    
    print("✅ Sample data created!")

if __name__ == "__main__":
    print("🚀 Setting up local development environment...")
    setup_local_env()
    create_local_directories()
    setup_sample_data()
    print("✅ Local setup complete!")
