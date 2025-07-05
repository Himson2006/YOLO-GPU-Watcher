#!/usr/bin/env python
import os, time, json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from config     import Config
from models     import Base, Video, Detection
from detection  import run_detection

# —── Database setup ─────────────────────────────────────
engine = create_engine(Config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# —── Ensure folders exist ──────────────────────────────
watch_folder  = Config.WATCH_FOLDER
detect_folder = os.path.join(watch_folder, "detections")
os.makedirs(watch_folder,   exist_ok=True)
os.makedirs(detect_folder,  exist_ok=True)

class Handler(FileSystemEventHandler):
    ALLOWED = {".mp4", ".avi", ".mov", ".mkv"}

    def on_created(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED: return

        # wait for file to stabilize
        last, stable = -1, 0
        while stable < 2:
            try: sz = os.path.getsize(event.src_path)
            except OSError:
                time.sleep(1); continue
            if sz==last: stable+=1
            else: last,stable=sz,0
            time.sleep(1)

        session = SessionLocal()
        try:
            fname = os.path.basename(event.src_path)
            if session.query(Video).filter_by(filename=fname).first():
                os.remove(event.src_path)
                return

            vid = Video(filename=fname)
            session.add(vid); session.commit()

            det = run_detection(event.src_path, Config.YOLO_MODEL_PATH)
            # save JSON
            jpath = os.path.join(detect_folder, f"{os.path.splitext(fname)[0]}.json")
            with open(jpath,"w") as jf:
                json.dump(det, jf, indent=2)

            # summarize
            seen, maxc = set(), {}
            for frame in det["frames"]:
                counts = {}
                for d in frame["detections"]:
                    cn = d["class_name"]; seen.add(cn)
                    counts[cn] = counts.get(cn,0)+1
                for cn,ct in counts.items():
                    maxc[cn] = max(maxc.get(cn,0), ct)

            rec = Detection(
                video_id=vid.id,
                detection_json=det,
                classes_detected=",".join(sorted(seen)) or None,
                max_count_per_frame=maxc or None
            )
            session.add(rec); session.commit()

        except IntegrityError:
            session.rollback()
        except Exception as e:
            session.rollback()
            if 'vid' in locals():
                session.delete(vid)
                session.commit()
            print("❌ run_detection failed:", e)
        finally:
            session.close()

    def on_deleted(self, event):
        if event.is_directory: return
        _, ext = os.path.splitext(event.src_path.lower())
        if ext not in self.ALLOWED: return

        fname = os.path.basename(event.src_path)
        session = SessionLocal()
        try:
            vid = session.query(Video).filter_by(filename=fname).first()
            if not vid: return

            jpath = os.path.join(detect_folder, f"{os.path.splitext(fname)[0]}.json")
            if os.path.exists(jpath):
                os.remove(jpath)

            session.delete(vid)
            session.commit()
        finally:
            session.close()

if __name__=="__main__":
    obs = Observer()
    obs.schedule(Handler(), watch_folder, recursive=False)
    obs.start()
    print(f"[watcher] Watching {watch_folder}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
