#!/usr/bin/env python
import os, time, json
from watchdog.observers import Observer
from watchdog.events    import FileSystemEventHandler
from sqlalchemy.exc     import IntegrityError
from config             import Config
from models             import SessionLocal, Video, Detection
from detection          import run_detection

watch_folder  = Config.WATCH_FOLDER
detect_folder = os.path.join(watch_folder, "detections")
os.makedirs(watch_folder, exist_ok=True)
os.makedirs(detect_folder, exist_ok=True)

class Handler(FileSystemEventHandler):
    ALLOWED = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED: return

        # wait for file to finish copying
        last, stable = -1, 0
        while stable < 2:
            try: sz = os.path.getsize(event.src_path)
            except OSError:
                time.sleep(1); continue
            if sz == last:
                stable += 1
            else:
                stable, last = 0, sz
            time.sleep(1)

        self._add_video(event.src_path)

    def on_deleted(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED: return
        self._remove_video(event.src_path)

    def _add_video(self, path):
        fn = os.path.basename(path)
        session = SessionLocal()
        if session.query(Video).filter_by(filename=fn).first():
            session.close()
            os.remove(path)
            return

        vid = Video(filename=fn)
        session.add(vid)
        try:
            session.commit()
        except IntegrityError:
            session.rollback(); session.close()
            os.remove(path)
            return

        # run detection
        try:
            det = run_detection(path, Config.YOLO_MODEL_PATH)
        except Exception as e:
            session.delete(vid); session.commit(); session.close()
            return

        # write JSON
        jp = os.path.join(detect_folder, f"{os.path.splitext(fn)[0]}.json")
        with open(jp, "w") as jf:
            json.dump(det, jf, indent=2)

        # summarize & store
        classes, maxc = set(), {}
        for fr in det["frames"]:
            cnt = {}
            for d in fr["detections"]:
                cn = d["class_name"]; classes.add(cn)
                cnt[cn] = cnt.get(cn, 0) + 1
            for cn, c in cnt.items():
                maxc[cn] = max(maxc.get(cn,0), c)

        rec = Detection(
            video_id=vid.id,
            detection_json=det,
            classes_detected=",".join(sorted(classes)) or None,
            max_count_per_frame=maxc or None
        )
        session.add(rec)
        session.commit()
        session.close()

    def _remove_video(self, path):
        fn = os.path.basename(path)
        session = SessionLocal()
        vid = session.query(Video).filter_by(filename=fn).first()
        if vid:
            jp = os.path.join(detect_folder, f"{os.path.splitext(fn)[0]}.json")
            if os.path.exists(jp):
                os.remove(jp)
            session.delete(vid)
            session.commit()
        session.close()

if __name__ == "__main__":
    handler  = Handler()
    observer = Observer()
    observer.schedule(handler, watch_folder, recursive=False)
    observer.start()
    print(f"[watcher] Watching {watch_folder!r}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
