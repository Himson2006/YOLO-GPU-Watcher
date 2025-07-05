#!/usr/bin/env python
import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import Video, Detection
from app.detection import run_detection

# ─── Bootstrap ────────────────────────────────────────────────────────────────
app = create_app()

# Make sure INFO‐level goes to stdout
app.logger.setLevel(logging.INFO)
handler_stdout = logging.StreamHandler()
handler_stdout.setLevel(logging.INFO)
app.logger.addHandler(handler_stdout)

watch_folder = app.config["WATCH_FOLDER"]
detect_folder = os.path.join(watch_folder, "detections")
os.makedirs(watch_folder, exist_ok=True)
os.makedirs(detect_folder, exist_ok=True)

class Handler(FileSystemEventHandler):
    ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED_EXT:
            return

        full_path = event.src_path

        # ─── wait for file to finish copying ───────────────────────────────
        last_size = -1
        stable = 0
        while stable < 2:
            try:
                size = os.path.getsize(full_path)
            except OSError:
                time.sleep(1)
                continue
            if size == last_size:
                stable += 1
            else:
                stable = 0
                last_size = size
            time.sleep(1)

        with app.app_context():
            self._add_video(full_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED_EXT:
            return

        with app.app_context():
            self._remove_video(event.src_path)

    def _add_video(self, full_path):
        filename = os.path.basename(full_path)

        if Video.query.filter_by(filename=filename).first():
            app.logger.info(f"[watcher] Duplicate '{filename}' → deleting file")
            try: os.remove(full_path)
            except OSError: pass
            return

        vid = Video(filename=filename)
        try:
            db.session.add(vid)
            db.session.commit()
            app.logger.info(f"[watcher] ✅ Video row created (id={vid.id})")
        except IntegrityError:
            db.session.rollback()
            app.logger.error(f"[watcher] ❌ IntegrityError inserting '{filename}'")
            try: os.remove(full_path)
            except: pass
            return

        try:
            det = run_detection(full_path, app.config["YOLO_MODEL_PATH"])
            app.logger.info(f"[watcher] 🦌 Detection succeeded for '{filename}'")
        except Exception as e:
            db.session.delete(vid)
            db.session.commit()
            app.logger.error(f"[watcher] ❌ run_detection failed: {e}")
            return

        json_path = os.path.join(detect_folder, f"{os.path.splitext(filename)[0]}.json")
        with open(json_path, "w") as jf:
            import json
            json.dump(det, jf, indent=2)

        classes_seen, max_counts = set(), {}
        for frame in det["frames"]:
            counts = {}
            for d in frame["detections"]:
                cn = d["class_name"]
                classes_seen.add(cn)
                counts[cn] = counts.get(cn, 0) + 1
            for cn, ct in counts.items():
                max_counts[cn] = max(max_counts.get(cn, 0), ct)

        rec = Detection(
            video_id=vid.id,
            detection_json=det,
            classes_detected=",".join(sorted(classes_seen)) or None,
            max_count_per_frame=max_counts or None,
        )
        db.session.add(rec)
        try:
            db.session.commit()
            app.logger.info(f"[watcher] ✅ Detection row created for video_id={vid.id}")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"[watcher] ❌ Failed to insert Detection: {e}")

    def _remove_video(self, full_path):
        filename = os.path.basename(full_path)
        vid = Video.query.filter_by(filename=filename).first()
        if not vid:
            return

        json_path = os.path.join(detect_folder, f"{os.path.splitext(filename)[0]}.json")
        if os.path.exists(json_path):
            try: os.remove(json_path)
            except OSError: pass

        db.session.delete(vid)
        db.session.commit()
        app.logger.info(f"[watcher] 🗑️ Removed DB records for '{filename}'")

if __name__ == "__main__":
    handler = Handler()
    observer = Observer()
    observer.schedule(handler, watch_folder, recursive=False)
    observer.start()
    # also print so you definitely see it in watcher.log
    print(f"[watcher] Watching folder: {watch_folder}", flush=True)
    app.logger.info(f"[watcher] Watching folder: {watch_folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
