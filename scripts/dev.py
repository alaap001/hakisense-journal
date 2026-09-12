"""Run the web preview, Supabase-backed API and durable AI worker."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
processes=[]


def stop(*_):
    for p in processes:
        if p.poll() is None:
            try:
                os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass


def main():
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    commands=[
        [str(ROOT/'.venv/bin/python'),'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--reload'],
        ['npm','run','dev'],
        [str(ROOT/'.venv/bin/python'),'-m','backend.worker'],
    ]
    try:
        for command in commands:
            processes.append(subprocess.Popen(command,cwd=ROOT,start_new_session=True))
        print('\nHakiSenseJournal: http://127.0.0.1:5173/\nAPI reference: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop all processes.\n',flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
        failed=next((p.returncode for p in processes if p.returncode),0)
        if failed:
            print('A server stopped. Check the message above (ports 5173 and 8000 must be available).',file=sys.stderr)
        return failed
    except KeyboardInterrupt:
        return 0
    finally:
        stop()
        for p in processes:
            try:
                p.wait(timeout=200)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL)


if __name__=='__main__':
    sys.exit(main())
