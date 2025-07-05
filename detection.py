import os, time, cv2, torch
from ultralytics import YOLO

def run_detection(
    input_source: str,
    model_path:   str,
    conf_thres:   float = 0.5,
    iou_thres:    float = 0.5,
    frame_thresh: int   = 10,
    gap_tol:      int   = 3,
):
    # ── wait for file to finish copying ─────────────────
    last, stable = -1, 0
    while stable < 2:
        try:
            sz = os.path.getsize(input_source)
        except OSError:
            time.sleep(1); continue
        if sz == last:
            stable += 1
        else:
            last, stable = sz, 0
        time.sleep(1)

    # ── load model & send to GPU if available ────────────
    model  = YOLO(model_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.model.to(device)
    if device=="cuda":
        torch.backends.cudnn.benchmark = True

    # ── open video ────────────────────────────────────────
    cap = cv2.VideoCapture(input_source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {input_source!r}")

    records, idx = [], 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        idx += 1

        res = model(
            frame,
            conf=conf_thres,
            iou=iou_thres,
            device=device,
            half=(device=="cuda")
        )[0]

        dets = []
        for box, conf, cls in zip(res.boxes.xyxy, res.boxes.conf, res.boxes.cls):
            cval = float(conf)
            if cval < conf_thres:
                continue
            x1,y1,x2,y2 = map(float, box)
            dets.append({
                "bbox":        [x1,y1,x2,y2],
                "confidence":  cval,
                "class_id":    int(cls),
                "class_name":  model.names[int(cls)]
            })

        records.append({
            "frame": idx,
            "objects_detected": bool(dets),
            "num_detections":   len(dets),
            "detections":       dets
        })

    cap.release()
    cv2.destroyAllWindows()

    # ── run‐length filtering ───────────────────────────────
    class2frames, valid = {}, {}
    for rec in records:
        for d in rec["detections"]:
            class2frames.setdefault(d["class_name"], set()).add(rec["frame"])
    for cls, frames in class2frames.items():
        sorted_f = sorted(frames)
        run, good = [sorted_f[0]], set()
        for f in sorted_f[1:]:
            if f - run[-1] <= gap_tol + 1:
                run.append(f)
            else:
                if len(run) > frame_thresh:
                    good.update(run)
                run = [f]
        if len(run) > frame_thresh:
            good.update(run)
        valid[cls] = good

    # ── assemble filtered output ─────────────────────────
    filtered = []
    for rec in records:
        fidx = rec["frame"]
        keep = [d for d in rec["detections"] if fidx in valid.get(d["class_name"],())]
        filtered.append({
            "frame": fidx,
            "objects_detected": bool(keep),
            "num_detections":   len(keep),
            "detections":       keep
        })

    return {"video_filename": os.path.basename(input_source),
            "total_frames":    idx,
            "frames":          filtered}
