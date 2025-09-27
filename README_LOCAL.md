# Backend Middle - Local Development Guide

## 🚀 Quick Start

### 1. ติดตั้ง Dependencies
```bash
cd backend_middle
pip install -r requirements.txt
```

### 2. เตรียมโมเดล AI
วางไฟล์โมเดลในโฟลเดอร์ `Model/`:
- `size.pt` - โมเดลวัดขนาดกุ้ง
- `shrimp.pt` - โมเดลตรวจจับกุ้งลอย
- `din.pt` - โมเดลตรวจการเคลื่อนไหว
- `water_class.pt` - โมเดลวิเคราะห์สีน้ำ

### 3. รัน Server
```bash
python run_local.py
```

หรือ
```bash
python main_local.py
```

## 📁 Directory Structure

```
backend_middle/
├── Model/                 # AI Models
├── local_storage/         # Local file storage
│   ├── size/             # Size analysis results
│   ├── shrimp/           # Shrimp detection results
│   ├── din/              # Movement analysis results
│   ├── water/            # Water analysis results
│   └── sensor/           # Sensor data
├── data_ponds/           # Pond information
├── output/               # Processed outputs
├── input_raspi1/         # Input from Raspberry Pi 1
├── input_raspi2/         # Input from Raspberry Pi 2
├── input_video/          # Video inputs
└── main_local.py         # Local development entry point
```

## 🔧 Configuration

### Environment Variables (Auto-configured)
- `STORAGE_DIR`: `./local_storage`
- `FILE_BASE_URL`: `http://localhost:8001`
- `PORT`: `8001`
- `MODEL_*`: Paths to AI models

### Manual Configuration
แก้ไขไฟล์ `local_config.py` เพื่อเปลี่ยนค่า default

## 📡 API Endpoints

### File Processing
```bash
# Upload files for AI processing
curl -X POST "http://localhost:8001/process" \
  -F "files=@shrimp_pond1_20250101_120000.jpg"
```

### Sensor Data
```bash
# Send sensor data
curl -X POST "http://localhost:8001/data" \
  -H "Content-Type: application/json" \
  -d '{
    "pond_id": 1,
    "ph": 7.2,
    "temperature": 28.5,
    "do": 6.8,
    "timestamp": "2025-01-01 12:00:00"
  }'
```

### Pond Information
```bash
# Send pond information
curl -X POST "http://localhost:8001/data_ponds" \
  -H "Content-Type: application/json" \
  -d '{
    "pond_id": 1,
    "pond_size_rai": 1.5,
    "initial_stock": 30000,
    "date": "2025-01-01 12:00:00"
  }'
```

### Get Data
```bash
# Get pond status
curl "http://localhost:8001/ponds/1/status"

# Get shrimp size data
curl "http://localhost:8001/ponds/1/shrimp_size"

# List files
curl "http://localhost:8001/list?path=sensor"
```

## 🧪 Testing

### 1. Test File Upload
```bash
# สร้างไฟล์ทดสอบ
echo "test" > test_image.jpg

# อัปโหลด
curl -X POST "http://localhost:8001/process" \
  -F "files=@test_image.jpg"
```

### 2. Test Sensor Data
```bash
# ส่งข้อมูลเซ็นเซอร์
curl -X POST "http://localhost:8001/data" \
  -H "Content-Type: application/json" \
  -d '{
    "pond_id": 1,
    "ph": 6.5,
    "temperature": 32.0,
    "do": 4.2,
    "timestamp": "2025-01-01 12:00:00"
  }'
```

## 🔍 Debugging

### 1. ตรวจสอบ Logs
```bash
# รันด้วย verbose logging
python run_local.py
```

### 2. ตรวจสอบไฟล์
```bash
# ดูไฟล์ที่สร้างขึ้น
ls -la local_storage/
ls -la data_ponds/
```

### 3. ตรวจสอบ API
```bash
# Health check
curl "http://localhost:8001/"

# List all files
curl "http://localhost:8001/list"
```

## ⚠️ Troubleshooting

### 1. Model Files Missing
```
⚠️ Warning: Missing model files
```
**แก้ไข**: วางไฟล์โมเดลในโฟลเดอร์ `Model/`

### 2. Port Already in Use
```
Error: Port 8001 already in use
```
**แก้ไข**: เปลี่ยน port ใน `local_config.py` หรือ kill process ที่ใช้ port นั้น

### 3. Permission Denied
```
PermissionError: [Errno 13] Permission denied
```
**แก้ไข**: ตรวจสอบสิทธิ์การเขียนไฟล์ในโฟลเดอร์

## 🚀 Production vs Local

| Feature | Local | Production |
|---------|-------|------------|
| Storage | `./local_storage` | `/data/local_storage` |
| Port | `8001` | `8000` |
| Models | `./Model/` | `/data/Model/` |
| URLs | `localhost` | Railway domain |
| Reload | ✅ Yes | ❌ No |

## 📝 Notes

- ไฟล์ `main_local.py` เป็น wrapper ของ `main.py` ที่ตั้งค่า environment สำหรับ local
- ไฟล์ `local_config.py` จัดการ environment variables ทั้งหมด
- ไฟล์ `run_local.py` เป็น script สำหรับรันง่ายๆ พร้อม error handling
- โฟลเดอร์และไฟล์ตัวอย่างจะถูกสร้างอัตโนมัติเมื่อรันครั้งแรก
