#!/usr/bin/env python
import os, sys, time, logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy.exc import IntegrityError

# startup banner — prints to stderr immediately
print(
    f"▶️  watcher.py PID={os.getpid()} cwd={os.getcwd()} "
    f"watching={os.environ.get('WATCH_FOLDER')}",
    file=sys.stderr,
    flush=True
)

from watcher_app.config     import Config
from watcher_app.detection  import run_detection
from watcher_app.models     import Video, Detection, db
from watcher_app            import create_app

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# bootstrap
app = create_app()
watch_folder = os.environ.get("WATCH_FOLDER", Config.WATCH_FOLDER)
detect_folder= os.path.join(watch_folder, "detections")
os.makedirs(watch_folder, exist_ok=True)
os.makedirs(detect_folder, exist_ok=True)

class Handler(FileSystemEventHandler):
    ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in self.ALLOWED_EXT: return

        # wait for copy to finish
        last, stable = -1, 0
        while stable < 2:
            try:
                sz = os.path.getsize(event.src_path)
            except OSError:
                time.sleep(1); continue
            if sz == last:
                stable += 1
            else:
                last, stable = sz, 0
            time.sleep(1)

        with app.app_context():
            self._add_video(event.src_path)

    def on_deleted(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in self.ALLOWED_EXT: return

        with app.app_context():
            self._remove_video(event.src_path)

    def _add_video(self, full_path):
        filename = os.path.basename(full_path)

        # 1) refuse duplicate
        if Video.query.filter_by(filename=filename).first():
            logger.info(f"[watcher] Duplicate '{filename}' → deleting file")
            try: os.remove(full_path)
            except: pass
            return

        # 2) insert Video
        vid = Video(filename=filename)
        try:
            db.session.add(vid)
            db.session.commit()
            logger.info(f"[watcher] ✅ Video row created (id={vid.id})")
        except IntegrityError:
            db.session.rollback()
            logger.error(f"[watcher] ❌ IntegrityError inserting '{filename}'")
            try: os.remove(full_path)
            except: pass
            return

        # 3) run detection
        try:
            det = run_detection(
                full_path,
                os.environ.get("YOLO_MODEL_PATH", Config.YOLO_MODEL_PATH)
            )
            logger.info(f"[watcher] 🦌 Detection succeeded for '{filename}'")
        except Exception as e:
            db.session.delete(vid); db.session.commit()
            logger.error(f"[watcher] ❌ run_detection failed: {e}")
            return

        # 4) write JSON
        import json
        json_path = os.path.join(detect_folder, f"{os.path.splitext(filename)[0]}.json")
        with open(json_path, "w") as jf:
            json.dump(det, jf, indent=2)

        # 5) summarize & insert Detection row
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
            max_count_per_frame=max_counts or None
        )
        db.session.add(rec)
        try:
            db.session.commit()
            logger.info(f"[watcher] ✅ Detection row created for video_id={vid.id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"[watcher] ❌ Failed to insert Detection: {e}")

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

        db.session.delete(vid)
        db.session.commit()
        logger.info(f"[watcher] 🗑️ Removed DB records for '{filename}'")

if __name__ == "__main__":
    handler  = Handler()
    observer = Observer()
    observer.schedule(handler, watch_folder, recursive=False)
    observer.start()
    logger.info(f"[watcher] Watching folder: {watch_folder}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
