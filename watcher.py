#!/usr/bin/env python
import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from watcher_app import create_app, db
from watcher_app.models import Video, Detection
from watcher_app.detection import run_detection

# ─── Bootstrap ────────────────────────────────────────────────────────────────
app = create_app()
watch_folder = app.config["WATCH_FOLDER"]
detect_folder = os.path.join(watch_folder, "detections")
os.makedirs(detect_folder, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("watcher")

class Handler(FileSystemEventHandler):
    ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED_EXT:
            return

        # wait for file to settle
        last, stable = -1, 0
        while stable < 2:
            try:
                sz = os.path.getsize(event.src_path)
            except OSError:
                time.sleep(1)
                continue
            if sz == last:
                stable += 1
            else:
                stable, last = 0, sz
            time.sleep(1)

        logger.info(f"detected file: {event.src_path}")
        with app.app_context():
            self._add_video(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED_EXT:
            return

        logger.info(f"deleted file: {event.src_path}")
        with app.app_context():
            self._remove_video(event.src_path)

    def _add_video(self, full_path):
        filename = os.path.basename(full_path)
        # 1) refuse duplicates
        if Video.query.filter_by(filename=filename).first():
            logger.info(f"Duplicate '{filename}' → deleting file")
            try: os.remove(full_path)
            except: pass
            return

        # 2) insert Video
        vid = Video(filename=filename)
        try:
            db.session.add(vid)
            db.session.commit()
            logger.info(f"✅ Video row created (id={vid.id})")
        except Exception:
            db.session.rollback()
            logger.error(f"❌ IntegrityError inserting '{filename}'")
            try: os.remove(full_path)
            except: pass
            return

        # 3) run detection
        try:
            det = run_detection(full_path, app.config["YOLO_MODEL_PATH"])
            logger.info(f"🦌 Detection succeeded for '{filename}'")
        except Exception as e:
            db.session.delete(vid); db.session.commit()
            logger.error(f"❌ run_detection failed: {e}")
            return

        # 4) write JSON
        json_path = os.path.join(detect_folder, f"{os.path.splitext(filename)[0]}.json")
        with open(json_path, "w") as jf:
            import json
            json.dump(det, jf, indent=2)

        # 5) summarize & insert Detection row
        classes_seen = set()
        max_counts   = {}
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
            logger.info(f"✅ Detection row created for video_id={vid.id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to insert Detection: {e}")

    def _remove_video(self, full_path):
        filename = os.path.basename(full_path)
        vid = Video.query.filter_by(filename=filename).first()
        if not vid:
            return

        # remove JSON
        json_path = os.path.join(detect_folder, f"{os.path.splitext(filename)[0]}.json")
        if os.path.exists(json_path):
            try: os.remove(json_path)
            except: pass

        # cascade delete DB rows
        db.session.delete(vid)
        db.session.commit()
        logger.info(f"🗑️ Removed DB records for '{filename}'")

if __name__ == "__main__":
    handler  = Handler()
    observer = Observer()
    observer.schedule(handler, watch_folder, recursive=False)
    observer.start()
    logger.info(f"Watching: {watch_folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
