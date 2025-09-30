[1mdiff --git a/main.py b/main.py[m
[1mindex 29e58b1..4e77d06 100644[m
[1m--- a/main.py[m
[1m+++ b/main.py[m
[36m@@ -3,6 +3,7 @@[m [mimport shutil[m
 import os[m
 import uuid[m
 import json[m
[32m+[m[32mimport time[m[41m[m
 from typing import List[m
 from datetime import datetime, timedelta, timezone[m
 import requests[m
[36m@@ -352,6 +353,60 @@[m [mdef send_shrimp_alert_notification(pond_id, image_url, output_image_url):[m
         print(f"❌ Push notification error: {e}")[m
         return False[m
 [m
[32m+[m[32mdef send_device_offline_notification(device_id, pond_id):[m[41m[m
[32m+[m[32m    """ส่งการแจ้งเตือนเมื่อ device offline"""[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    # 1. Login เพื่อรับ token[m[41m[m
[32m+[m[32m    access_token = login_and_get_token()[m[41m[m
[32m+[m[32m    if not access_token:[m[41m[m
[32m+[m[32m        print("❌ Cannot get access token for offline notification")[m[41m[m
[32m+[m[32m        return False[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    # 2. สร้างข้อมูลการแจ้งเตือน[m[41m[m
[32m+[m[32m    alert_data = {[m[41m[m
[32m+[m[32m        "user_id": 1,[m[41m[m
[32m+[m[32m        "title": "ยอกุ้งดับเรียบร้อยแล้ว",[m[41m[m
[32m+[m[32m        "body": "ยอกุ้งดับเรียบร้อยแล้ว ตรวจสอบยอกุ้งด่วน!!!",[m[41m[m
[32m+[m[32m        "icon": "/icons/icon-192x192.png",[m[41m[m
[32m+[m[32m        "badge": "/icons/icon-72x72.png",[m[41m[m
[32m+[m[32m        "url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTIM0syGxE_4zEiuWSroBXGlfRIcdIXR97v2Q&s",[m[41m[m
[32m+[m[32m        "tag": "general-notification",[m[41m[m
[32m+[m[32m        "data": {[m[41m[m
[32m+[m[32m            "type": "info",[m[41m[m
[32m+[m[32m            "source": "system",[m[41m[m
[32m+[m[32m            "device_id": device_id,[m[41m[m
[32m+[m[32m            "pond_id": str(pond_id),[m[41m[m
[32m+[m[32m            "timestamp": format_timestamp(),[m[41m[m
[32m+[m[32m            "alert_type": f"DeviceOffline-{device_id}",[m[41m[m
[32m+[m[32m            "severity": "high"[m[41m[m
[32m+[m[32m        }[m[41m[m
[32m+[m[32m    }[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    # 3. ส่งการแจ้งเตือน[m[41m[m
[32m+[m[32m    push_url = "https://web-production-7909d.up.railway.app/api/v1/push/send"[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    try:[m[41m[m
[32m+[m[32m        response = requests.post([m[41m[m
[32m+[m[32m            push_url,[m[41m[m
[32m+[m[32m            headers={[m[41m[m
[32m+[m[32m                "Content-Type": "application/json",[m[41m[m
[32m+[m[32m                "Authorization": f"Bearer {access_token}"[m[41m[m
[32m+[m[32m            },[m[41m[m
[32m+[m[32m            json=alert_data,[m[41m[m
[32m+[m[32m            timeout=10[m[41m[m
[32m+[m[32m        )[m[41m[m
[32m+[m[41m        [m
[32m+[m[32m        if response.status_code == 200:[m[41m[m
[32m+[m[32m            print(f"✅ Device offline notification sent successfully for {device_id}")[m[41m[m
[32m+[m[32m            return True[m[41m[m
[32m+[m[32m        else:[m[41m[m
[32m+[m[32m            print(f"❌ Push notification failed: {response.status_code} - {response.text}")[m[41m[m
[32m+[m[32m            return False[m[41m[m
[32m+[m[41m            [m
[32m+[m[32m    except Exception as e:[m[41m[m
[32m+[m[32m        print(f"❌ Push notification error: {e}")[m[41m[m
[32m+[m[32m        return False[m[41m[m
[32m+[m[41m[m
 def get_latest_pond_info_for_pond(data_ponds_dir, pond_id):[m
     pond_files = glob.glob(os.path.join(data_ponds_dir, f"pond_{pond_id}_*.json"))[m
     if not pond_files:[m
[36m@@ -626,6 +681,13 @@[m [mlast_seen_data = {[m
     "din": None[m
 }[m
 [m
[32m+[m[32m# =========================[m[41m[m
[32m+[m[32m# HEARTBEAT MONITORING[m[41m[m
[32m+[m[32m# =========================[m[41m[m
[32m+[m[32m# เก็บข้อมูล heartbeat ของแต่ละ device[m[41m[m
[32m+[m[32mdevice_heartbeats = {}[m[41m[m
[32m+[m[32mHEARTBEAT_TIMEOUT = 10  # วินาที[m[41m[m
[32m+[m[41m[m
 # =========================[m
 # 4) BUILDERS[m
 # =========================[m
[36m@@ -643,7 +705,7 @@[m [mdef build_pond_status_json(pond_id: int) -> dict:[m
             "do": sensor_d.get("do"),[m
         }[m
 [m
[31m-    minerals = {"Mineral_1": 0.0, "Mineral_2": 0.0, "Mineral_3": "false", "Mineral_4": "false"}[m
[32m+[m[32m    minerals = {"Mineral_1": 0.0, "Mineral_2": 0.0, "Mineral_3": 0.0, "Mineral_4": 0.0}[m[41m[m
     if san_d:[m
         arr = san_d.get("remaining_g") or [][m
         for i in range(4):[m
[36m@@ -730,10 +792,36 @@[m [mdef _strip_timestamp(d: dict) -> dict:[m
     d_copy.pop("timestamp", None)[m
     return d_copy[m
 [m
[32m+[m[32masync def check_device_heartbeats():[m[41m[m
[32m+[m[32m    """ตรวจสอบ device heartbeat และส่งการแจ้งเตือนถ้า offline"""[m[41m[m
[32m+[m[32m    global device_heartbeats[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    current_time = time.time()[m[41m[m
[32m+[m[32m    offline_devices = [][m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    for device_id, last_heartbeat_time in device_heartbeats.items():[m[41m[m
[32m+[m[32m        if current_time - last_heartbeat_time > HEARTBEAT_TIMEOUT:[m[41m[m
[32m+[m[32m            offline_devices.append(device_id)[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    # ส่งการแจ้งเตือนสำหรับ device ที่ offline[m[41m[m
[32m+[m[32m    for device_id in offline_devices:[m[41m[m
[32m+[m[32m        # ดึง pond_id จาก device_id (format: raspi_pond_1)[m[41m[m
[32m+[m[32m        try:[m[41m[m
[32m+[m[32m            pond_id = int(device_id.split('_')[-1])[m[41m[m
[32m+[m[32m            print(f"🚨 Device {device_id} is offline! Sending notification...")[m[41m[m
[32m+[m[32m            send_device_offline_notification(device_id, pond_id)[m[41m[m
[32m+[m[32m            # ลบ device ที่ offline ออกจากรายการ[m[41m[m
[32m+[m[32m            del device_heartbeats[device_id][m[41m[m
[32m+[m[32m        except (ValueError, IndexError):[m[41m[m
[32m+[m[32m            print(f"⚠️ Cannot parse pond_id from device_id: {device_id}")[m[41m[m
[32m+[m[41m[m
 async def loop_build_and_push(pond_id: int):[m
     global last_seen_data, last_sent_status, last_sent_size[m
     while True:[m
         try:[m
[32m+[m[32m            # ตรวจสอบ device heartbeats[m[41m[m
[32m+[m[32m            await check_device_heartbeats()[m[41m[m
[32m+[m[41m            [m
             # โหลดข้อมูลล่าสุด[m
             sensor_path, sensor_d = _latest_json_in_dir(FS_SENSOR_DIR, pond_id=pond_id)[m
             if sensor_d:[m
[36m@@ -856,6 +944,35 @@[m [mdef read_json(path: str):[m
     except Exception as e:[m
         raise HTTPException(status_code=500, detail=f"Error reading JSON: {e}")[m
     [m
[32m+[m[32m@app.post("/heartbeat")[m[41m[m
[32m+[m[32masync def receive_heartbeat(request: Request):[m[41m[m
[32m+[m[32m    """รับ heartbeat จาก Raspberry Pi"""[m[41m[m
[32m+[m[32m    try:[m[41m[m
[32m+[m[32m        data = await request.json()[m[41m[m
[32m+[m[32m    except Exception:[m[41m[m
[32m+[m[32m        raise HTTPException(status_code=400, detail="Invalid JSON")[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    required_keys = ["device_id", "status", "timestamp", "pond_id"][m[41m[m
[32m+[m[32m    if not all(k in data for k in required_keys):[m[41m[m
[32m+[m[32m        raise HTTPException(status_code=400, detail="Missing required fields")[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    device_id = data["device_id"][m[41m[m
[32m+[m[32m    status = data["status"][m[41m[m
[32m+[m[32m    timestamp = data["timestamp"][m[41m[m
[32m+[m[32m    pond_id = data["pond_id"][m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    # อัพเดทเวลาล่าสุดที่ได้รับ heartbeat[m[41m[m
[32m+[m[32m    device_heartbeats[device_id] = time.time()[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    print(f"💓 Received heartbeat from {device_id} (pond {pond_id}) at {timestamp}")[m[41m[m
[32m+[m[41m    [m
[32m+[m[32m    return {[m[41m[m
[32m+[m[32m        "status": "success",[m[41m [m
[32m+[m[32m        "message": f"Heartbeat received from {device_id}",[m[41m[m
[32m+[m[32m        "device_id": device_id,[m[41m[m
[32m+[m[32m        "pond_id": pond_id[m[41m[m
[32m+[m[32m    }[m[41m[m
[32m+[m[41m[m
 @app.get("/")[m
 def health_check():[m
     return {"status": "ok"}[m
