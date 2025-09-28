import os
import math
import json
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import glob
import requests   # ✅ ยิง HTTP POST ไปแอป

# ================= CONFIG =================
# คาลิเบรต: cm -> grams
REF_POWDER = [
    (0.0,  20000.0),   # 0cm (เต็ม)   -> 300 g
    (5.0,  15000.0),
    (10.0, 10000.0),
    (25.0, 0.0)      # 15cm (หมด)   -> 0 g
]

# ✅ ค่าเริ่มต้นน้ำเต็มถัง (กำหนดเองตามขนาดถังจริง)
FULL_WATER_ML = [2000.0, 2000.0]   # [Probiotic, Green]

# ตัวแปรเก็บสถานะน้ำคงเหลือ (เริ่มเต็ม)
current_water_ml = FULL_WATER_ML.copy()

# ✅ ค่าคาลิเบรตอัตราปั๊ม (ยังคงไว้ใช้ในฟังก์ชัน auto_dose)
LIQUID_RATE = 50.0  # ml/sec

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT   = 1883
TOPIC_CMD   = "pond/doser/cmd"
TOPIC_STATUS= "pond/doser/status"

# ✅ Path
SENSOR_BASE     = os.environ.get("SENSOR_BASE", "/data/local_storage/sensor")
POND_INFO_BASE  = os.environ.get("POND_INFO_BASE", "/data/data_ponds")
TXT_WATER_DIR   = os.environ.get("TXT_WATER_DIR", "/data/output/water_output")
SAN_BASE        = os.environ.get("SAN_BASE", "/data/local_storage/san")
os.makedirs(SAN_BASE, exist_ok=True)

# ✅ Endpoint แอป (อ่านจาก ENV)
APP_ENDPOINT_STATUS = os.environ.get("APP_SAN_URL", "http://localhost:8000/api/sensor")
APP_ENDPOINT_ALERT  = os.environ.get("APP_ALERT_URL", "http://localhost:8000/api/alert")


# ===== Helpers: linear interpolation =====
def interp_from_points(points, x):
    """points: [(x0,y0), (x1,y1), ...]"""
    pts = sorted(points, key=lambda t: t[0])
    if x <= pts[0][0]:   return pts[0][1]
    if x >= pts[-1][0]:  return pts[-1][1]
    for i in range(len(pts)-1):
        x1,y1 = pts[i]
        x2,y2 = pts[i+1]
        if x1 <= x <= x2:
            if x2 == x1: return y1
            ratio = (x - x1) / (x2 - x1)
            return y1 + (y2 - y1) * ratio
    return 0.0

# ===== Water AI (.txt) =====
def read_latest_txt(txt_dir):
    txt_files = sorted(glob.glob(os.path.join(txt_dir, "*.txt")),
                       key=os.path.getmtime, reverse=True)
    if txt_files:
        with open(txt_files[0], "r", encoding="utf-8") as f:
            return f.read().strip(), txt_files[0]
    return "", ""

def should_dose_green_extract(txt):
    t = txt.lower()
    return ("clear" in t) or ("น้ำใส" in t) or ("ใสเกิน" in t)

# ===== MQTT handlers =====
def handle_san_status(data):
    """
    data example from Arduino:
      {
        "pond_id":1,
        "powder_distances":[d_caco3, d_mgso4],
        "water_levels":[remain_probiotic_ml, remain_green_ml]  # น้ำคงเหลือจริง (ml)
      }
    """
    try:
        pond_id   = data.get("pond_id", 1)
        powder    = data.get("powder_distances", [])
        water_lv  = data.get("water_levels", [])

                # 👉 ผง: แปลง cm -> kg + flag
       # 👉 ผง: แปลง cm -> kg + flag
        powder_flags = []
        remain_powder_kg = []
        for d in powder:
            try:
                val = float(d)
                remain_powder_kg.append(round(interp_from_points(REF_POWDER, val) / 1000, 1))
                # ✅ ถ้าเกิน 15 cm แปลว่าผงใกล้หมด → "true"
                powder_flags.append("true" if val > 15 else "false")
            except:
                remain_powder_kg.append(0.0)
                powder_flags.append("true")  # ถ้า error → ถือว่าใกล้หมด
        
        # 👉 น้ำ: Arduino ส่งมาเป็น L
        water_remaining = []
        water_flags = []
        for val in water_lv:
            try:
                remain = float(val)
                water_remaining.append(remain)
                # ✅ ถ้าเหลือน้อยกว่า 2 L → ใกล้หมด
                water_flags.append("true" if remain < 2.0 else "false")
            except:
                water_remaining.append(0.0)
                water_flags.append("true")  # error → ถือว่าใกล้หมด
            
            record = {
                "timestamp": datetime.now().isoformat(),
                "pond_id": pond_id,
            
                # ✅ ส่งออกแบบ array ให้ main.py ใช้ตรง ๆ
                "remaining_g": [
                    remain_powder_kg[0] if len(remain_powder_kg) > 0 else 0.0,    # Mineral_1 (kg)
                    remain_powder_kg[1] if len(remain_powder_kg) > 1 else 0.0,    # Mineral_2 (kg)
                    water_flags[0] if len(water_flags) > 0 else "false",          # Mineral_3 (true/false)
                    water_flags[1] if len(water_flags) > 1 else "false",          # Mineral_4 (true/false)
                ],
            
                # 👉 debug/backup fields (ไม่บังคับ แต่ช่วยเวลา test)
                "powder_remaining_kg": remain_powder_kg,
                "water_remaining_L": water_remaining,
                "powder_flags": powder_flags,
                "water_flags": water_flags,
            }
            



        # ====== Save log ======
        save_path = os.path.join(
            SAN_BASE, f"san_{pond_id}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
        )
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        # ====== Save ไฟล์ล่าสุด ======
        sent_path = os.path.join(SAN_BASE, "sent_san.json")
        with open(sent_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        print(f"[SAVE] ✅ {save_path}")
        print(f"[UPDATE] 📤 {sent_path}")
        print(f"       powder_g={remain_powder_kg}, water_ml={water_remaining}")

        # ====== ส่งข้อมูลไปแอป ======
        try:
            res = requests.post(APP_ENDPOINT_STATUS, json=record, timeout=5)
            print(f"[APP] 📡 Sent to status endpoint, code={res.status_code}")
        except Exception as e:
            print(f"[APP ERROR] ส่งข้อมูลล่าสุดไม่สำเร็จ: {e}")

        # ====== ส่ง alert ถ้าบางช่องใกล้หมด ======
        if any(flag == "true" for flag in powder_flags) or any(flag == "true" for flag in water_flags):

            alert_payload = {
                "user_id": 1,
                "title": "⚠️ พบสาร/น้ำบางถังใกล้หมด",
                "body": "ตรวจสอบสาร/น้ำในถังโดยด่วน",
                "image": "https://drive.google.com/xxx",
                "url": "https://drive.google.com/xxx",
                "tag": "shrimp-alert",
                "data": {
                    "pond_id": str(pond_id),
                    "timestamp": record["timestamp"],
                    "alert_type": "Item-runout",
                    "severity": "high",
                    "powder_remaining_kg": remain_powder_kg,
                    "water_remaining_L": water_remaining
                }
            }
            try:
                res = requests.post(APP_ENDPOINT_ALERT, json=alert_payload, timeout=5)
                print(f"[APP] 🚨 Alert sent, code={res.status_code}")
            except Exception as e:
                print(f"[APP ERROR] ส่ง alert ไม่สำเร็จ: {e}")

    except Exception as e:
        print(f"[ERROR] handle_san_status: {e}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        if "powder_distances" in data:
            handle_san_status(data)
    except Exception as e:
        print(f"[ERROR] on_message: {e}")

def setup_mqtt():
    client = mqtt.Client(transport="websockets")
    client.on_message = on_message

    # ====== Callback เมื่อเชื่อมต่อสำเร็จ ======
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("✅ MQTT connected")
            client.subscribe(TOPIC_STATUS)
        else:
            print("❌ MQTT connect failed, rc=", rc)

    # ====== Callback เมื่อหลุดการเชื่อมต่อ ======
    def on_disconnect(client, userdata, rc):
        print("⚠️ MQTT disconnected, trying to reconnect...")
        while True:
            try:
                client.reconnect()
                print("✅ MQTT reconnected")
                client.subscribe(TOPIC_STATUS)
                break
            except Exception as e:
                print("❌ reconnect failed:", e)
                time.sleep(5)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # ====== เลือกพอร์ตตาม environment ======
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        # 👉 ถ้าอยู่ใน Railway ใช้ WebSocket
        client.ws_set_options(path="/mqtt")
        client.connect("broker.emqx.io", 8083, 60)
    else:
        # 👉 ถ้า run บนเครื่อง local ใช้ TCP ปกติ
        client.connect("broker.emqx.io", 1883, 60)

    client.loop_start()
    return client



mqttc = setup_mqtt()

# ===== Dosing (ฟังก์ชันเก่ายังอยู่ครบ) =====
def calc_powder_rounds_per_gram(radius_cm=6.5, height_cm=6.5, bulk_density=0.8):
    vol_per_round_cm3 = math.pi * (radius_cm**2) * height_cm
    grams_per_round   = vol_per_round_cm3 * bulk_density
    return grams_per_round

def calc_powder_rounds(grams, grams_per_round=None):
    if grams_per_round is None:
        grams_per_round = calc_powder_rounds_per_gram()
    if grams_per_round <= 0: return 0
    return grams / grams_per_round

def calc_liquid_time(ml, rate_ml_per_sec=LIQUID_RATE):
    if rate_ml_per_sec <= 0: return 0
    return ml / rate_ml_per_sec

def send_servo_command(rounds_array, pond_id=1):
    cmd = {"type": "dose_servo", "pond_id": pond_id,
           "rounds": [int(round(x)) for x in rounds_array]}
    mqttc.publish(TOPIC_CMD, json.dumps(cmd), qos=1)
    print(f"[MQTT] ✅ dose_servo {cmd}")

def send_pump_command(durations_array, pond_id=1):
    cmd = {"type": "dose_pump", "pond_id": pond_id,
           "durations": [int(round(x)) for x in durations_array]}
    mqttc.publish(TOPIC_CMD, json.dumps(cmd), qos=1)
    print(f"[MQTT] ✅ dose_pump {cmd}")

def read_latest_txt_and_flag():
    ai_txt, _ = read_latest_txt(TXT_WATER_DIR)
    return ai_txt, should_dose_green_extract(ai_txt)

def process_auto_dose(pond_id, pond_size_rai, ph, temp, do, last_dose, now=None):
    if now is None: now = datetime.now()
    servo_rounds   = [0, 0]  # [CaCO3, MgSO4]
    pump_durations = [0, 0]  # [Probiotic, Green]

    # Probiotic -> ทุก 7 วัน
    if (now - last_dose.get("probiotic", now - timedelta(days=8))) > timedelta(days=7):
        ml = 200 * float(pond_size_rai)
        pump_durations[0] = int(round(calc_liquid_time(ml)))

    # CaCO3 -> pH < 6.8
    if ph < 6.8:
        grams = 2500 * float(pond_size_rai)
        servo_rounds[0] = int(round(calc_powder_rounds(grams)))

    # MgSO4 -> temp > 30
    if temp > 30:
        grams = 2500 * float(pond_size_rai)
        servo_rounds[1] = int(round(calc_powder_rounds(grams)))

    # Green Extract -> "น้ำใส"
    ai_txt, water_clear = read_latest_txt_and_flag()
    if water_clear:
        ml = 150 * float(pond_size_rai)
        pump_durations[1] = int(round(calc_liquid_time(ml)))

    if any(servo_rounds):   send_servo_command(servo_rounds, pond_id)
    if any(pump_durations): send_pump_command(pump_durations, pond_id)

    print(f"[ACTION] pond={pond_id} servo={servo_rounds} pump={pump_durations} ai='{ai_txt}'")

# ===== Demo run =====
if __name__ == "__main__":
    last_dose = {
        "probiotic":    datetime.now() - timedelta(days=8),
        "caco3":        datetime.now() - timedelta(hours=12),
        "mgso4":        datetime.now() - timedelta(days=3),
        "green_extract":datetime.now() - timedelta(hours=24),
    }
    process_auto_dose(pond_id=1, pond_size_rai=1.0, ph=6.5, temp=31, do=5, last_dose=last_dose)
    print("✅ Backend started. Waiting for MQTT messages...")
    while True:
        time.sleep(5)






