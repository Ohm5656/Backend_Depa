import os
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import numpy as np
import imageio.v2 as imageio
import cv2
from torchvision.ops import nms

# โหลดโมเดลกุ้งดิ้นจากโฟลเดอร์ Model/
model_path = os.environ.get("MODEL_DIN", os.path.join("Model", "din.pt"))
model = YOLO(model_path)

tracker = DeepSort(max_age=30, n_init=3, max_cosine_distance=0.3)

# --------------------------
# PARAMS
# --------------------------
NO_MOVE_THRESHOLD = 2.5   # ใช้แบบเวอร์ชันที่สอง
shrimp_moved_once = set()
movement_status = {}
CONFIDENCE_THRESHOLD = 0.85


def analyze_video(input_path, original_name: str = None):
    if not os.path.exists(input_path):
        print(f"❌ ไม่พบวิดีโอ: {input_path}")
        return

    # ===============================
    # ใช้ path ของ Railway (/data)
    # ===============================
    output_dir = os.environ.get("OUTPUT_DIN", "/data/local_storage/din")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(original_name or os.path.basename(input_path))[0]
    output_video_path = os.path.join(output_dir, f"{base_name}.mp4")
    output_txt_path = os.path.join(output_dir, f"{base_name}.txt")

    # ------------------------------
    # เปิด video
    # ------------------------------
    try:
        reader = imageio.get_reader(input_path)
        meta = reader.get_meta_data()
        fps = meta.get("fps", 25)
        size = meta.get("size", None)
    except Exception as e:
        print(f"⚠️ imageio เปิดไม่ได้: {e}")
        reader, fps, size = None, None, None

    if size is None:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print("❌ ทั้ง imageio และ OpenCV ไม่สามารถเปิดวิดีโอได้")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        size = (width, height)

        def frame_generator_cv2(path):
            cap = cv2.VideoCapture(path)
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cap.release()

        reader = frame_generator_cv2(input_path)

    width, height = size
    writer = imageio.get_writer(output_video_path, fps=fps)
    prev_positions = {}

    # ------------------------------
    # วน loop frame
    # ------------------------------
    for frame in reader:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        results = model.predict(source=frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        scores = results[0].boxes.conf.cpu().numpy()

        # 🔹 NMS
        if len(boxes) > 0:
            boxes_tensor = torch.tensor(boxes, dtype=torch.float32)
            scores_tensor = torch.tensor(scores, dtype=torch.float32)
            keep = nms(boxes_tensor, scores_tensor, iou_threshold=0.5)
            boxes = boxes[keep.numpy()]
            scores = scores[keep.numpy()]

        # DeepSort input
        detections = [([x1, y1, x2 - x1, y2 - y1], score, None)
                      for (x1, y1, x2, y2), score in zip(boxes, scores)
                      if score >= CONFIDENCE_THRESHOLD]

        tracks = tracker.update_tracks(detections, frame=frame)

        for track in tracks:
            if not track.is_confirmed():
                continue
            track_id = track.track_id
            x1, y1, x2, y2 = map(int, track.to_ltrb())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            if track_id in prev_positions:
                dx, dy = cx - prev_positions[track_id][0], cy - prev_positions[track_id][1]
                dist = np.sqrt(dx ** 2 + dy ** 2)

                # 🔹 Logic เวอร์ชันสอง
                if track_id in shrimp_moved_once:
                    movement_status[track_id] = "good"
                    color = (0, 255, 0)
                else:
                    if dist > NO_MOVE_THRESHOLD:
                        shrimp_moved_once.add(track_id)
                        movement_status[track_id] = "good"
                        color = (0, 255, 0)
                    else:
                        movement_status[track_id] = "sick"
                        color = (0, 0, 255)
            else:
                movement_status[track_id] = "sick"
                color = (0, 0, 255)

            prev_positions[track_id] = (cx, cy)
            label = f"id_{track_id} ({movement_status.get(track_id, 'None')})"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    if hasattr(reader, "close"):
        try:
            reader.close()
        except Exception:
            pass
    writer.close()

    # ------------------------------
    # Summary
    # ------------------------------
    total = len(prev_positions)
    moved = len(shrimp_moved_once)
    moved_percent = (moved / total) * 100 if total > 0 else 0
    overall_status = "✅ สุขภาพดี" if moved_percent >= 70 else "❌ มีตัวไม่ขยับเยอะ"

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(f"🦐 จำนวนกุ้งทั้งหมด: {total} ตัว\n")
        f.write(f"✅ เคยขยับ: {moved} ตัว ({moved_percent:.2f}%)\n")
        f.write(f"📊 สถานะรวม: {overall_status}\n\n")
        for tid in sorted(prev_positions.keys()):
            f.write(f"id_{tid}: {movement_status.get(tid, 'รอข้อมูล')}\n")

    print(f"✅ บันทึกวิดีโอที่: {output_video_path}")
    print(f"📄 บันทึกผลข้อความที่: {output_txt_path}")
    return output_video_path, output_txt_path

