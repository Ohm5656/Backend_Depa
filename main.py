from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

import shutil
import os
import uuid
import json
import time
import math
import re
import glob
import asyncio
import requests
import paho.mqtt.client as mqtt

from typing import List
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy

# ==========================
# Imports จาก process modules
# ==========================
from process.size import analyze_shrimp
from process.shrimp import analyze_kuny
from process.din import analyze_video
from process.water import analyze_water
from local_storage import LocalStorage
from auto_dose import process_auto_dose   # 🟢 เพิ่มบรรทัดนี้

# ==========================
# FastAPI และ CORS
# ==========================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Storage Config
# ==========================
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/data/local_storage"))
(STORAGE_DIR / "size").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "shrimp").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "din").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "water").mkdir(parents=True, exist_ok=True)

# Mount static directories
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")
app.mount("/size", StaticFiles(directory=str(STORAGE_DIR / "size")), name="size")
app.mount("/shrimp", StaticFiles(directory=str(STORAGE_DIR / "shrimp")), name="shrimp")
app.mount("/din", StaticFiles(directory=str(STORAGE_DIR / "din")), name="din")
app.mount("/water", StaticFiles(directory=str(STORAGE_DIR / "water")), name="water")

# ==========================
# Railway Config
# ==========================
FILE_BASE_URL = os.environ.get("FILE_BASE_URL", "http://localhost:8001").rstrip("/")
LOCAL_STORAGE_BASE = os.environ.get("LOCAL_STORAGE_BASE", "/data/local_storage")
DATA_PONDS_DIR = os.environ.get("DATA_PONDS_DIR", "/data/data_ponds")

os.makedirs(LOCAL_STORAGE_BASE, exist_ok=True)
os.makedirs(DATA_PONDS_DIR, exist_ok=True)

storage = LocalStorage(storage_path=LOCAL_STORAGE_BASE, base_url=FILE_BASE_URL)

# ==========================
# Timezone
# ==========================
BANGKOK_TZ = timezone(timedelta(hours=7))

def now_bangkok():
    return datetime.now(BANGKOK_TZ)

def format_timestamp(dt: datetime | None = None) -> str:
    return (dt or now_bangkok()).strftime("%Y-%m-%dT%H:%M:%S")

# ==========================
# Public URL Helpers
# ==========================
PUBLIC_FOLDER_ALIASES = {
    "size": "size",
    "size_output": "size",
    "shrimp": "shrimp",
    "shrimp_output": "shrimp",
    "din": "din",
    "din_output": "din",
    "water": "water",
    "water_output": "water",
}

def _relative_to_storage(file_path: str):
    abs_file = os.path.abspath(file_path)
    candidates = []
    for base in {LOCAL_STORAGE_BASE, os.environ.get("STORAGE_DIR")}:
        if base:
            candidates.append(os.path.abspath(base))

    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        try:
            rel = os.path.relpath(abs_file, base)
        except ValueError:
            continue
        rel = rel.replace("\\", "/")
        if rel.startswith(".."):
            continue
        rel = rel.lstrip("./")
        if rel:
            return rel
    return None

def _extract_public_subpath(parts):
    for idx, part in enumerate(parts):
        mapped = PUBLIC_FOLDER_ALIASES.get(str(part).lower())
        if mapped:
            remainder = list(parts[idx + 1:])
            segment = "/".join([mapped, *remainder]).strip("/")
            return segment
    return None

def make_public_url(file_path: str) -> str:
    abs_file = os.path.abspath(file_path)
    rel_path = _relative_to_storage(abs_file)
    segment = None
    if rel_path:
        segment = _extract_public_subpath(rel_path.split("/"))
    if not segment:
        segment = _extract_public_subpath(Path(abs_file).parts)
    if segment:
        return f"{FILE_BASE_URL}/{segment}"
    return f"{FILE_BASE_URL}/{os.path.basename(abs_file)}"

def build_public_url(file_path: str) -> str:
    abs_file = os.path.abspath(file_path)
    rel_path = _relative_to_storage(abs_file)
    if rel_path:
        segment = _extract_public_subpath(rel_path.split("/"))
        if segment:
            return f"{FILE_BASE_URL}/{segment}"
        return f"{FILE_BASE_URL}/{rel_path}"
    return make_public_url(abs_file)

# ==========================
# Helper: แปลงค่า Size จาก text_content
# ==========================
def _extract_size_from_text(text: str):
    matches = re.findall(r"Shrimp\s+\d+:\s*([\d.]+)\s*cm\s*/\s*([\d.]+)\s*g", text)
    if matches:
        lengths = [float(m[0]) for m in matches]
        weights = [float(m[1]) for m in matches]
        avg_length = sum(lengths) / len(lengths)
        avg_weight = sum(weights) / len(weights)
        return avg_length, avg_weight
    return None, None

def _has_status_payload(data: dict) -> bool:
    return any([
        data.get("DO") not in (None, ""),
        data.get("PH") not in (None, ""),
        data.get("Temp") not in (None, ""),
        bool(data.get("ColorWater") and data["ColorWater"] != "unknown"),
        bool(data.get("PicColorWater")),
        bool(data.get("PicKungOnWater")),
    ])

def _has_size_payload(data: dict) -> bool:
    return any([
        data.get("Size_CM") not in (None, ""),
        data.get("Size_gram") not in (None, ""),
        bool(data.get("SizePic")),
        bool(data.get("PicFood")),
        bool(data.get("PicKungDinn")),
    ])

# ==========================
# Save JSON Result
# ==========================
def save_json_result(
    result_type,
    original_name,
    output_image=None,
    output_text_path=None,
    pond_number=None,
    total_larvae=None,
    survival_rate=None,
    output_video=None,
    original_input_path=None
):
    text_content = None
    if output_text_path and os.path.exists(output_text_path):
        with open(output_text_path, "r", encoding="utf-8") as f:
            text_content = f.read()

    result_data = {
        "id": str(uuid.uuid4()),
        "type": result_type,
        "original_name": original_name,
        "timestamp": format_timestamp(),
        "pond_number": pond_number,
        "total_larvae": total_larvae,
        "survival_rate": survival_rate,
        "text_content": text_content
    }

    if result_data["pond_number"] is None and original_name:
        fallback_pond = extract_pond_id_from_filename(original_name.lower())
        if fallback_pond is not None:
            result_data["pond_number"] = fallback_pond

    if output_image:
        if isinstance(output_image, list):
            result_data["output_image"] = [make_public_url(p) for p in output_image]
        else:
            result_data["output_image"] = make_public_url(output_image)

    if output_video:
        result_data["output_video"] = make_public_url(output_video)

    if original_input_path and os.path.exists(original_input_path):
        raw_dir = os.path.join(LOCAL_STORAGE_BASE, result_type, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        raw_filename = os.path.basename(original_input_path)
        raw_dest = os.path.join(raw_dir, raw_filename)
        try:
            if not (os.path.exists(raw_dest) and os.path.samefile(original_input_path, raw_dest)):
                shutil.copy2(original_input_path, raw_dest)
        except FileNotFoundError:
            shutil.copy2(original_input_path, raw_dest)
        except Exception:
            pass
        if os.path.exists(raw_dest):
            result_data["raw_input_image"] = build_public_url(raw_dest)

    # ✅ เพิ่ม shrimp_size ถ้าเป็น result_type = "size"
    if result_type == "size":
        length_cm, weight_avg_g = _extract_size_from_text(text_content or "")
        result_data["shrimp_size"] = {
            "length_cm": length_cm,
            "weight_avg_g": weight_avg_g,
            "image_url": result_data.get("output_image")
        }

    # ✅ ส่งการแจ้งเตือนเมื่อพบกุ้งลอยผิวน้ำ
    if result_type == "shrimp" and text_content and "🆗 ไม่พบกุ้งลอยผิวน้ำในภาพนี้" not in text_content:
        pond_id = result_data.get("pond_number")
        if pond_id:
            image_url = result_data.get("output_image")
            raw_image_url = result_data.get("raw_input_image")
            send_shrimp_alert_notification(pond_id, raw_image_url, image_url)

    save_dir = os.path.join(LOCAL_STORAGE_BASE, result_type)
    os.makedirs(save_dir, exist_ok=True)

    json_filename = f"{os.path.splitext(original_name)[0]}_{now_bangkok().strftime('%Y%m%d_%H%M%S_%f')}.json"
    json_path = os.path.join(save_dir, json_filename)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    return json_path

# ==========================
# Extract pond_id จาก filename
# ==========================
def extract_pond_id_from_filename(filename):
    match = re.search(r"pond(\d+)", filename)
    if match:
        return int(match.group(1))
    return None
# ==========================
# Helper: Login และ Push Notification
# ==========================
def login_and_get_token():
    """Login เพื่อรับ access token"""
    login_url = "https://web-production-7909d.up.railway.app/api/v1/auth/login"
    login_data = "username=0812345678&password=admin123"
    try:
        response = requests.post(
            login_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=login_data,
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("access_token")
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None


def send_shrimp_alert_notification(pond_id, image_url, output_image_url):
    """ส่งการแจ้งเตือนเมื่อพบกุ้งลอยผิวน้ำ"""
    # 1. Login เพื่อรับ token
    access_token = login_and_get_token()
    if not access_token:
        print("❌ Cannot get access token for push notification")
        return False

    # 2. เตรียมข้อมูลแจ้งเตือน
    final_image_url = output_image_url or image_url
    alert_data = {
        "user_id": 1,
        "title": "พบกุ้งลอยบนผิวน้ำ!!!",
        "body": f"ตรวจพบกุ้งลอยบนผิวน้ำในบ่อที่ {pond_id} ควรตรวจสอบทันที",
        "image": final_image_url,
        "url": final_image_url,
        "tag": "shrimp-alert",
        "data": {
            "pond_id": str(pond_id),
            "timestamp": format_timestamp(),
            "alert_type": f"ShrimpOnWater-{pond_id}",
            "severity": "high"
        }
    }

    # 3. ส่งแจ้งเตือน
    push_url = "https://web-production-7909d.up.railway.app/api/v1/push/send"
    try:
        response = requests.post(
            push_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json=alert_data,
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Shrimp alert notification sent successfully for pond {pond_id}")
            return True
        else:
            print(f"❌ Push notification failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Push notification error: {e}")
        return False


def send_device_offline_notification(device_id, pond_id):
    """ส่งการแจ้งเตือนเมื่อ device offline"""
    # 1. Login
    access_token = login_and_get_token()
    if not access_token:
        print("❌ Cannot get access token for offline notification")
        return False

    # 2. ข้อมูลแจ้งเตือน
    alert_data = {
        "user_id": 1,
        "title": "ยอกุ้งดับเรียบร้อยแล้ว",
        "body": "ยอกุ้งดับเรียบร้อยแล้ว ตรวจสอบยอกุ้งด่วน!!!",
        "icon": "/icons/icon-192x192.png",
        "badge": "/icons/icon-72x72.png",
        "url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTIM0syGxE_4zEiuWSroBXGlfRIcdIXR97v2Q&s",
        "tag": "general-notification",
        "data": {
            "type": "info",
            "source": "system",
            "device_id": device_id,
            "pond_id": str(pond_id),
            "timestamp": format_timestamp(),
            "alert_type": f"DeviceOffline-{device_id}",
            "severity": "high"
        }
    }

    # 3. ส่งแจ้งเตือน
    push_url = "https://web-production-7909d.up.railway.app/api/v1/push/send"
    try:
        response = requests.post(
            push_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json=alert_data,
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Device offline notification sent successfully for {device_id}")
            return True
        else:
            print(f"❌ Push notification failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Push notification error: {e}")
        return False


def get_latest_pond_info_for_pond(data_ponds_dir, pond_id):
    pond_files = glob.glob(os.path.join(data_ponds_dir, f"pond_{pond_id}_*.json"))
    if not pond_files:
        return None, None
    pond_files.sort(reverse=True)
    latest_file = pond_files[0]
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pond_id"), data.get("initial_stock")

# ==========================
# API: /process
# ==========================
@app.post("/process")
async def process_files(files: List[UploadFile] = File(...)):
    os.makedirs("input_raspi1", exist_ok=True)
    os.makedirs("input_raspi2", exist_ok=True)
    os.makedirs("input_video", exist_ok=True)

    results = []
    now_str = now_bangkok().strftime("%Y%m%d_%H%M%S_%f")

    for file in files:
        filename = file.filename
        filename_lower = filename.lower()
        ext = os.path.splitext(filename_lower)[-1]
        print(f"📦 Received file: {filename}")

        try:
            if ext in [".jpg", ".jpeg", ".png"]:
                content = await file.read()
                pond_id = extract_pond_id_from_filename(filename_lower)
                if pond_id is None:
                    raise HTTPException(status_code=400, detail="ไม่พบ pond_id ในชื่อไฟล์!")

                pond_number, total_larvae = get_latest_pond_info_for_pond(DATA_PONDS_DIR, pond_id)

                # Shrimp Floating
                if "shrimp_float" in filename_lower:
                    input_path = os.path.join("input_raspi2", f"shrimp_float_pond{pond_id}_{now_str}{ext}")
                    with open(input_path, "wb") as f:
                        f.write(content)

                    output_img_path, output_txt_path = analyze_kuny(input_path)
                    json_path = save_json_result(
                        result_type="shrimp",
                        original_name=filename,
                        output_image=output_img_path,
                        output_text_path=output_txt_path,
                        pond_number=pond_number,
                        total_larvae=total_larvae
                    )
                    results.append({"type": "shrimp_floating", "filename": filename, "json": json_path})

                # Shrimp Size
                elif "shrimp" in filename_lower:
                    input_path = os.path.join("input_raspi1", f"shrimp_pond{pond_id}_{now_str}{ext}")
                    with open(input_path, "wb") as f:
                        f.write(content)

                    output_img_path, output_txt_path = analyze_shrimp(
                        input_path,
                        total_larvae=total_larvae,
                        pond_number=pond_number
                    )
                    json_path = save_json_result(
                        result_type="size",
                        original_name=filename,
                        output_image=output_img_path,
                        output_text_path=output_txt_path,
                        pond_number=pond_number,
                        total_larvae=total_larvae,
                        original_input_path=input_path
                    )
                    results.append({"type": "shrimp_size", "filename": filename, "json": json_path})

                # Water
                elif "water" in filename_lower:
                    input_path = os.path.join("input_raspi2", f"water_pond{pond_id}_{now_str}{ext}")
                    with open(input_path, "wb") as f:
                        f.write(content)

                    output_img_path, output_txt_path = analyze_water(input_path)

                    # 🟢 อ่านค่า sensor ล่าสุดมาใช้ร่วมกับ auto_dose
                    sensor_path, sensor_d = _latest_json_in_dir(FS_SENSOR_DIR, pond_id=pond_id)
                    if sensor_d:
                        ph = float(sensor_d.get("ph", 7))
                        temp = float(sensor_d.get("temperature", 28))
                        do = float(sensor_d.get("do", 5))
                    else:
                        ph, temp, do = 7, 28, 5

                    pond_size_rai = 1.0
                    process_auto_dose(pond_id, pond_size_rai, ph, temp, do, last_dose={})

                    json_path = save_json_result(
                        result_type="water",
                        original_name=filename,
                        output_image=output_img_path,
                        output_text_path=output_txt_path,
                        pond_number=pond_number,
                        total_larvae=total_larvae
                    )
                    results.append({"type": "water_image", "filename": filename, "json": json_path})

            # Video
            elif ext in [".mp4", ".avi", ".mov", ".mpeg4"]:
                pond_id = extract_pond_id_from_filename(filename_lower)
                if pond_id is None:
                    raise HTTPException(status_code=400, detail="ไม่พบ pond_id ในชื่อไฟล์!")

                pond_number, total_larvae = get_latest_pond_info_for_pond(DATA_PONDS_DIR, pond_id)
                input_path = os.path.join("input_video", f"video_pond{pond_id}_{now_str}{ext}")
                with open(input_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)

                output_video_path, output_txt_path = analyze_video(input_path)
                json_path = save_json_result(
                    result_type="din",
                    original_name=filename,
                    output_video=output_video_path,
                    output_text_path=output_txt_path,
                    pond_number=pond_number,
                    total_larvae=total_larvae
                )
                results.append({"type": "shrimp_video", "filename": filename, "json": json_path})

            else:
                raise HTTPException(status_code=400, detail="ไม่รองรับไฟล์ประเภทนี้")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"❗ Error processing {filename}: {e}")

    return {
        "status": "success",
        "message": f"✅ ประมวลผลไฟล์สำเร็จ {len(results)} รายการ",
        "results": results
    }
# ==========================
# CONFIG เพิ่มเติมสำหรับไฟล์/ไดเรกทอรี และปลายทางส่ง JSON
# ==========================
# โฟลเดอร์ฐานสำหรับ local storage
BASE_LOCAL = os.environ.get("LOCAL_STORAGE_ROOT", "/data/local_storage")

# ปลายทาง (URL) สำหรับส่งสถานะไปยังแอปภายนอก (ตั้งค่าใน Railway ENV ได้)
APP_STATUS_URL = os.environ.get("APP_STATUS_URL")
APP_SIZE_URL = os.environ.get("APP_SIZE_URL")

# โฟลเดอร์ย่อยภายใต้ BASE_LOCAL
FS_SENSOR_DIR = os.path.join(BASE_LOCAL, "sensor")
FS_SAN_DIR = os.path.join(BASE_LOCAL, "san")
FS_WATER_DIR = os.path.join(BASE_LOCAL, "water")
FS_SHRIMP_DIR = os.path.join(BASE_LOCAL, "shrimp")
FS_SIZE_DIR = os.path.join(BASE_LOCAL, "size")
FS_DIN_DIR = os.path.join(BASE_LOCAL, "din")

# ไฟล์สรุปสถานะล่าสุด
POND_STATUS_FILE = os.path.join(BASE_LOCAL, "pond_status.json")
SHRIMP_SIZE_FILE = os.path.join(BASE_LOCAL, "shrimp_size.json")

# โฟลเดอร์รับข้อมูล sensor (สำหรับ endpoint /data)
SENSOR_DIR = os.environ.get("SENSOR_DIR", "/data/local_storage/sensor")
os.makedirs(SENSOR_DIR, exist_ok=True)  # สร้างหากยังไม่มี


# ==========================
# HELPERS: อ่านไฟล์ล่าสุด / ส่ง JSON / ดึงค่า size
# ==========================
def _latest_json_in_dir(dir_path: str, pond_id: int | None = None):
    """คืน (path, dict) ของไฟล์ JSON ล่าสุดในโฟลเดอร์ (ที่ตรง pond_id ถ้าระบุ)"""
    if not os.path.isdir(dir_path):
        return None, None

    files = glob.glob(os.path.join(dir_path, "*.json"))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    if not files:
        return None, None

    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            pid = d.get("pond_id", d.get("pond_number"))
            if pond_id is None or pid == pond_id:
                return p, d
        except Exception:
            continue

    return None, None


def _pick_url_maybe_list(v):
    """ถ้าเป็นลิสต์ให้คืนสมาชิกแรก ถ้าเป็นสตริงคืนสตริง"""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _send_json_to(url: str, data: dict):
    """ส่ง JSON ไปยัง URL ที่กำหนด (ถ้าไม่ได้ตั้งค่า url จะข้าม)"""
    try:
        if not url:
            print("ℹ️ Skip push: No URL set")
            return
        r = requests.post(url, json=data, timeout=6)
        if r.status_code == 200:
            print(f"✅ Sent to {url}")
        else:
            print(f"⚠️ App responded {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Push to app failed ({url}): {e}")


def _extract_size_from_json(size_json: dict):
    """ดึงค่า length_cm / weight_g จากฟิลด์ shrimp_size หรือจากข้อความ text_content"""
    if "shrimp_size" in size_json:
        sc = size_json["shrimp_size"]
        return sc.get("length_cm"), sc.get("weight_avg_g")

    txt = size_json.get("text_content") or ""
    # Match pattern: "Shrimp 1: 0.33 cm / 0.00 g"
    matches = re.findall(r"Shrimp\s+\d+:\s*([\d.]+)\s*cm\s*/\s*([\d.]+)\s*g", txt)
    if matches:
        lengths = [float(m[0]) for m in matches]
        weights = [float(m[1]) for m in matches]
        avg_length = sum(lengths) / len(lengths)
        avg_weight = sum(weights) / len(weights)
        return avg_length, avg_weight

    return None, None


# ==========================
# CACHE (เก็บของล่าสุดที่อ่านได้)
# ==========================
last_seen_data = {
    "sensor": None,
    "san": None,
    "water": None,
    "shrimp": None,
    "size": None,
    "din": None,
}


# ==========================
# HEARTBEAT MONITORING
# ==========================
# เก็บเวลาล่าสุดที่ได้รับ heartbeat ของแต่ละ device
device_heartbeats = {}
HEARTBEAT_TIMEOUT = 10  # วินาที


# ==========================
# BUILDERS: รวมข้อมูลออกเป็น JSON สั้นๆ สำหรับแอป
# ==========================
def build_pond_status_json(pond_id: int) -> dict:
    sensor_d = last_seen_data["sensor"]
    san_d = last_seen_data["san"]
    water_d = last_seen_data["water"]
    shrimp_d = last_seen_data["shrimp"]

    # ส่วน sensor
    sensor_part = {"temperature": None, "ph": None, "do": None}
    if sensor_d:
        sensor_part = {
            "temperature": sensor_d.get("temperature"),
            "ph": sensor_d.get("ph"),
            "do": sensor_d.get("do"),
        }

    # ส่วนแร่ธาตุ/สาร
    minerals = {"Mineral_1": 0.0, "Mineral_2": 0.0, "Mineral_3": "0.0", "Mineral_4": "0.0"}
    if san_d:
        arr = san_d.get("remaining_g") or []
        for i in range(4):
            if i < len(arr):
                if i < 2:
                    # กล่อง 1-2: ตัวเลข (น้ำหนัก)
                    minerals[f"Mineral_{i+1}"] = float(arr[i]) if isinstance(arr[i], (int, float)) else 0.0
                else:
                    # กล่อง 3-4: สถานะเป็นสตริง
                    if isinstance(arr[i], float):
                        minerals[f"Mineral_{i+1}"] = arr[i]
                    else:
                        minerals[f"Mineral_{i+1}"] = "0.0" if arr[i] else "0.0"

    # รูปสีน้ำ + สี
    water_image = None
    water_color = "unknown"
    if water_d:
        water_image = _pick_url_maybe_list(water_d.get("output_image"))
        water_color = (water_d.get("text_content") or "").strip() or "unknown"

    # รูปกุ้งลอย
    shrimp_float_image = None
    if shrimp_d:
        shrimp_float_image = _pick_url_maybe_list(shrimp_d.get("output_image"))

    data = {
        "pondId": str(pond_id) if pond_id is not None else None,
        "timestamp": format_timestamp(),
        "DO": sensor_part["do"],
        "PH": sensor_part["ph"],
        "Temp": sensor_part["temperature"],
        "ColorWater": water_color,
        "Mineral_1": minerals["Mineral_1"],
        "Mineral_2": minerals["Mineral_2"],
        "Mineral_3": minerals["Mineral_3"],
        "Mineral_4": minerals["Mineral_4"],
        "PicColorWater": water_image,
        "PicKungOnWater": shrimp_float_image,
    }

    with open(POND_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def build_shrimp_size_json(pond_id: int) -> dict:
    size_d = last_seen_data["size"]
    din_d = last_seen_data["din"]

    size_image = None
    raw_image = None
    length_cm, weight_g = None, None

    if size_d:
        size_image = _pick_url_maybe_list(size_d.get("output_image"))
        raw_image = size_d.get("raw_input_image")
        length_cm, weight_g = _extract_size_from_json(size_d)

    video_url = None
    if din_d:
        video_url = din_d.get("output_video")
    
    data = {
        "pondId": pond_id,
        "timestamp": format_timestamp(),
        "Size_CM": round(length_cm, 2),   # ปัดทศนิยม 2 ตำแหน่ง
        "Size_gram": round(weight_g, 2),  # ปัดทศนิยม 1 ตำแหน่ง
        "SizePic": size_image,
        "PicFood": raw_image or size_image,
        "PicKungDin": video_url,
    }


    with open(SHRIMP_SIZE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


# ==========================
# ENDPOINTS: รับ stock / sensor
# ==========================
@app.post("/data_ponds")
async def receive_stock_json(request: Request):
    """รับข้อมูลจำนวนปล่อยลงบ่อ (initial stock) และบันทึกเป็นไฟล์ pond_{id}_*.json"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    required_keys = ["pond_id", "date", "initial_stock"]
    if not all(k in data for k in required_keys):
        raise HTTPException(status_code=400, detail="Missing required data fields")

    pond_id = data["pond_id"]
    timestamp = now_bangkok().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"pond_{pond_id}_{timestamp}.json"
    file_path = os.path.join(DATA_PONDS_DIR, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save stock data: {e}")

    print(f"✅ Saved pond JSON data: {file_path}")
    return {"status": "success", "saved_file": file_path}


@app.post("/data")
async def receive_sensor_data(request: Request):
    """รับข้อมูล sensor JSON และเรียก auto_dose หลังบันทึก"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    required_keys = ["pond_id", "ph", "temperature", "do", "timestamp"]
    if not all(k in data for k in required_keys):
        raise HTTPException(status_code=400, detail="Missing required fields")

    filename = f"sensor_{now_bangkok().strftime('%Y%m%dT%H%M%S%f')}.json"
    file_path = os.path.join(SENSOR_DIR, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save sensor data: {e}")

    print(f"✅ Saved sensor JSON: {file_path}")

    # 🟢 เรียก auto_dose หลังบันทึกข้อมูล
    pond_id = int(data["pond_id"])
    ph = float(data["ph"])
    temp = float(data["temperature"])
    do = float(data["do"])
    pond_size_rai = 1.0  # 👉 ปรับได้เอง หรืออ่านจากไฟล์ pond_xxx.json

    process_auto_dose(pond_id, pond_size_rai, ph, temp, do, last_dose={})

    return {"status": "success", "saved_file": file_path}


# ==========================
# ENDPOINTS: ดูสถานะรวม / ไซส์กุ้ง
# ==========================
@app.get("/ponds/{pond_id}/status")
def get_status(pond_id: int):
    if os.path.exists(POND_STATUS_FILE):
        with open(POND_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "no pond_status.json yet"}


@app.get("/ponds/{pond_id}/shrimp_size")
def get_size(pond_id: int):
    if os.path.exists(SHRIMP_SIZE_FILE):
        with open(SHRIMP_SIZE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "no shrimp_size.json yet"}


# ==========================
# ENDPOINTS: list / view / json (utility)
# ==========================
@app.get("/list")
def list_dir(path: str = ""):
    """
    list directory/file จาก root ของ container
    ตัวอย่าง: /list?path=/data/local_storage  หรือ /list?path=sensor
    """
    base = Path("/")           # จุดเริ่ม root ของ container
    target = (base / path).resolve()  # ป้องกัน traversal ออกนอก root

    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    items = []
    for p in sorted(target.iterdir()):
        items.append({
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if p.is_file() else None,
            "path": str(p)
        })
    return JSONResponse(items)


@app.get("/view")
def view_file(path: str):
    """
    ดูไฟล์ที่อยู่ใน container (เช่น JSON หรือ TXT)
    ใช้ query param เช่น /view?path=/data/local_storage/pond_status.json
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    # เดิมตั้งเป็น JSON เสมอ; ถ้าต้องการ auto-detect MIME สามารถปรับได้
    return FileResponse(path, media_type="application/json")


@app.get("/json")
def read_json(path: str):
    """อ่านไฟล์ JSON แล้วคืนเนื้อหาเป็น object"""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading JSON: {e}")


# ==========================
# HEARTBEAT ENDPOINT
# ==========================
@app.post("/heartbeat")
async def receive_heartbeat(request: Request):
    """
    รับ heartbeat จาก Raspberry Pi
    JSON ตัวอย่าง:
    {
      "device_id": "raspi_pond_1",
      "status": "ok",
      "timestamp": "2025-09-29T10:22:00",
      "pond_id": 1
    }
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    required_keys = ["device_id", "status", "timestamp", "pond_id"]
    if not all(k in data for k in required_keys):
        raise HTTPException(status_code=400, detail="Missing required fields")

    device_id = data["device_id"]
    status = data["status"]
    timestamp = data["timestamp"]
    pond_id = data["pond_id"]

    # อัพเดทเวลาล่าสุดที่ได้รับ heartbeat
    device_heartbeats[device_id] = time.time()
    print(f"💓 Received heartbeat from {device_id} (pond {pond_id}) at {timestamp} status={status}")

    return {
        "status": "success",
        "message": f"Heartbeat received from {device_id}",
        "device_id": device_id,
        "pond_id": pond_id
    }


# ==========================
# HEALTH CHECK
# ==========================
@app.get("/")
def health_check():
    return {"status": "ok"}


# ==========================
# BACKGROUND LOOP
# ==========================
last_sent_status = None
last_sent_size = None

def _strip_timestamp(d: dict) -> dict:
    """คืนค่า dict โดยตัดฟิลด์ timestamp ออก (ใช้เช็คการเปลี่ยนแปลงจริง)"""
    if not d:
        return {}
    d_copy = copy.deepcopy(d)
    d_copy.pop("timestamp", None)
    return d_copy


async def check_device_heartbeats():
    """ตรวจสอบ device heartbeat และส่งการแจ้งเตือนถ้า offline"""
    global device_heartbeats
    current_time = time.time()
    offline_devices = []

    for device_id, last_heartbeat_time in list(device_heartbeats.items()):
        if current_time - last_heartbeat_time > HEARTBEAT_TIMEOUT:
            offline_devices.append(device_id)

    # ส่งแจ้งเตือนสำหรับ device ที่ offline
    for device_id in offline_devices:
        try:
            # คาดรูปแบบ device_id = raspi_pond_{N}
            pond_id = int(device_id.split("_")[-1])
            print(f"🚨 Device {device_id} is offline! Sending notification...")
            send_device_offline_notification(device_id, pond_id)
            # นำออกจากรายการ
            del device_heartbeats[device_id]
        except (ValueError, IndexError):
            print(f"⚠️ Cannot parse pond_id from device_id: {device_id}")


async def loop_build_and_push(pond_id: int):
    """วนลูปโหลดข้อมูลล่าสุด -> build json -> push ไปยังแอปเมื่อมีการเปลี่ยนแปลง"""
    global last_seen_data, last_sent_status, last_sent_size

    while True:
        try:
            # ตรวจ heartbeat
            await check_device_heartbeats()

            # โหลดข้อมูลล่าสุดจากแต่ละโฟลเดอร์
            sensor_path, sensor_d = _latest_json_in_dir(FS_SENSOR_DIR, pond_id=pond_id)
            if sensor_d:
                last_seen_data["sensor"] = sensor_d

            san_path, san_d = _latest_json_in_dir(FS_SAN_DIR, pond_id=pond_id)
            if san_d:
                last_seen_data["san"] = san_d

            water_path, water_d = _latest_json_in_dir(FS_WATER_DIR, pond_id=pond_id)
            if water_d:
                last_seen_data["water"] = water_d

            shrimp_path, shrimp_d = _latest_json_in_dir(FS_SHRIMP_DIR, pond_id=pond_id)
            if shrimp_d:
                last_seen_data["shrimp"] = shrimp_d

            size_path, size_d = _latest_json_in_dir(FS_SIZE_DIR, pond_id=pond_id)
            if size_d:
                last_seen_data["size"] = size_d

            din_path, din_d = _latest_json_in_dir(FS_DIN_DIR, pond_id=pond_id)
            if din_d:
                last_seen_data["din"] = din_d

            # 📝 build json ทุกครั้ง
            status_json = build_pond_status_json(pond_id)
            size_json = build_shrimp_size_json(pond_id)

            # 📤 ส่งเฉพาะตอนข้อมูลเปลี่ยนจริง (ไม่ดู timestamp)
            status_clean = _strip_timestamp(status_json)
            if APP_STATUS_URL and status_clean != last_sent_status:
                print("📤 Sending pond_status_json:", status_json)
                _send_json_to(APP_STATUS_URL, status_json)
                last_sent_status = status_clean

            size_clean = _strip_timestamp(size_json)
            if APP_SIZE_URL and size_clean != last_sent_size:
                print("📤 Sending shrimp_size_json:", size_json)
                _send_json_to(APP_SIZE_URL, size_json)
                last_sent_size = size_clean

        except Exception as e:
            print("🚨 Loop error:", e)

        # หน่วงคาบวนรอบ (ลดโหลด CPU/IO)
        await asyncio.sleep(5)


# ==========================
# STARTUP HOOK: เริ่มแบ็คกราวด์ลูป
# ==========================
@app.on_event("startup")
async def startup_event():
    # สามารถแก้ pond_id ให้ dynamic ได้ตามระบบ login/หลายบ่อ
    pond_id = 1
    asyncio.create_task(loop_build_and_push(pond_id))

# ==========================
# ENTRYPOINT
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port)




