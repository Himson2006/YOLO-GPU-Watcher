#!/usr/bin/env python
import os
import sys
import time
import json

# make sure our package is importable
sys.path.insert(0, os.path.dirname(__file__))

from watchdog.observers import Observer
from watchdog.events    import FileSystemEventHandler
from sqlalchemy.exc     import IntegrityError

from flask import Flask
from watcher_app.config    import Config
from watcher_app.models    import db, Video, Detection
from watcher_app.detection import run_detection

# ─── bootstrap Flask + SQLAlchemy ────────────────────
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# ensure folders exist
os.makedirs(Config.WATCH_FOLDER, exist_ok=True)
os.makedirs(Config.JSON_FOLDER, exist_ok=True)

class Handler(FileSystemEventHandler):
    ALLOWED = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory: return
        ext = os.path.splitext(event.src_path.lower())[1]
        if ext not in self.ALLOWED: return

        # wait for file to finish copying
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
                last, stable = sz, 0
            time.sleep(1)

        with app.app_context():
            self._add_video(event.src_path)

    def on_deleted(self, event):
        if event.is_directory: return
        ext = os.path.splitext(event.src_path.lower())[1]
        if ext not in self.ALLOWED: return
        with app.app_context():
            self._remove_video(event.src_path)

    def _add_video(self, full_path):
        fn = os.path.basename(full_path)
        if Video.query.filter_by(filename=fn).first():
            app.logger.info(f"[watcher] Duplicate '{fn}' → deleting file")
            try: os.remove(full_path)
            except: pass
            return

        vid = Video(filename=fn)
        try:
            db.session.add(vid)
            db.session.commit()
            app.logger.info(f"[watcher] ✅ Video row created id={vid.id}")
        except IntegrityError:
            db.session.rollback()
            app.logger.error(f"[watcher] ❌ IntegrityError inserting '{fn}'")
            try: os.remove(full_path)
            except: pass
            return

        try:
            det = run_detection(full_path, app.config["YOLO_MODEL_PATH"])
            app.logger.info(f"[watcher] 🦌 Detection succeeded for '{fn}'")
        except Exception as e:
            db.session.delete(vid); db.session.commit()
            app.logger.error(f"[watcher] ❌ run_detection failed: {e}")
            return

        # write JSON
        base = os.path.splitext(fn)[0]
        jfp  = os.path.join(app.config["JSON_FOLDER"], base + ".json")
        with open(jfp, "w") as jf:
            json.dump(det, jf, indent=2)

        # summarize & insert Detection row
        classes, maxc = set(), {}
        for frame in det["frames"]:
            counts = {}
            for d in frame["detections"]:
                cn = d["class_name"]; classes.add(cn)
                counts[cn] = counts.get(cn,0) + 1
            for cn,ct in counts.items():
                maxc[cn] = max(maxc.get(cn,0), ct)

        rec = Detection(
            video_id=vid.id,
            detection_json=det,
            classes_detected=",".join(sorted(classes)) or None,
            max_count_per_frame=maxc or None
        )
        db.session.add(rec)
        try:    db.session.commit()
        except: db.session.rollback()

    def _remove_video(self, full_path):
        fn = os.path.basename(full_path)
        vid = Video.query.filter_by(filename=fn).first()
        if not vid:
            return

        # delete JSON file if present
        base = os.path.splitext(fn)[0]
        jfp  = os.path.join(Config.JSON_FOLDER, base + ".json")
        if os.path.exists(jfp):
            try: os.remove(jfp)
            except: pass

        db.session.delete(vid)
        db.session.commit()
        app.logger.info(f"[watcher] 🗑️ Removed DB records for '{fn}'")

if __name__ == "__main__":
    handler  = Handler()
    observer = Observer()
    observer.schedule(handler, Config.WATCH_FOLDER, recursive=False)
    observer.start()
    app.logger.info(f"[watcher] Watching folder: {Config.WATCH_FOLDER}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
