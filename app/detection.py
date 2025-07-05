import os
import json
import torch
import cv2
from ultralytics import YOLO

def run_detection(
    input_source: str,
    model_path: str,
    conf_thres: float = 0.5,
    iou_thres: float = 0.5,
    frame_threshold: int = 10,
    gap_tolerance: int = 3,
    write_json: bool = False,
    output_json_dir: str = None,
):
    """
    Runs YOLO detection + run-length filtering, returns a dict:
      {
        "video_filename": str,
        "total_frames": int,
        "frames": [ {frame, objects_detected, num_detections, detections}, … ]
      }
    Optionally writes the filtered list to JSON (if write_json=True).
    """
    # resolve video filename for metadata & JSON path
    if input_source == 0 or str(input_source).lower() == "webcam":
        video_name = "webcam"
    else:
        base = os.path.basename(input_source)
        video_name = os.path.splitext(base)[0]

    json_path = None
    if write_json:
        if output_json_dir is None:
            raise ValueError("output_json_dir must be set if write_json=True")
        os.makedirs(output_json_dir, exist_ok=True)
        json_path = os.path.join(output_json_dir, f"{video_name}.json")

    # open capture
    cap = cv2.VideoCapture(input_source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input {input_source!r}")

    # load model
    model = YOLO(model_path)

    # pick device and move model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.model.to(device)
    if device == "cuda":
        torch.backends.cudnn.benchmark = True

    # 1) raw per-frame detections
    records = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # inference on chosen device, half‐precision if GPU
        res = model(
            frame,
            device=device,
            conf=conf_thres,
            iou=iou_thres,
            half=(device == "cuda")
        )[0]

        dets = []
        for box, conf, cls in zip(res.boxes.xyxy, res.boxes.conf, res.boxes.cls):
            cval = float(conf)
            if cval < conf_thres:
                continue
            x1, y1, x2, y2 = map(float, box)
            dets.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": cval,
                "class_id": int(cls),
                "class_name": model.names[int(cls)]
            })

        records.append({
            "frame": frame_idx,
            "objects_detected": bool(dets),
            "num_detections": len(dets),
            "detections": dets
        })

    cap.release()
    cv2.destroyAllWindows()

    # 2) build class→frames map
    class_to_frames = {}
    for rec in records:
        for det in rec["detections"]:
            class_to_frames.setdefault(det["class_name"], set()).add(rec["frame"])

    # 3) filter runs per class
    valid_frames_per_class = {}
    for cls_name, frames_set in class_to_frames.items():
        valid_frames = set()
        if not frames_set:
            continue
        sorted_f = sorted(frames_set)
        run = [sorted_f[0]]
        for f in sorted_f[1:]:
            if f - run[-1] <= gap_tolerance + 1:
                run.append(f)
            else:
                if len(run) > frame_threshold:
                    valid_frames.update(run)
                run = [f]
        if len(run) > frame_threshold:
            valid_frames.update(run)
        valid_frames_per_class[cls_name] = valid_frames

    # 4) apply filter to build final list
    filtered = []
    for rec in records:
        fidx = rec["frame"]
        keep = [
            d for d in rec["detections"]
            if fidx in valid_frames_per_class.get(d["class_name"], ())
        ]
        filtered.append({
            "frame": fidx,
            "objects_detected": bool(keep),
            "num_detections": len(keep),
            "detections": keep
        })

    # 5) assemble result
    result = {
        "video_filename": video_name,
        "total_frames": frame_idx,
        "frames": filtered
    }

    # 6) optionally write JSON
    if write_json and json_path:
        with open(json_path, "w") as f:
            json.dump(result["frames"], f, indent=2)
        print(f"Saved filtered results to {json_path}")

    return result

