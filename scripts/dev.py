"""Run the web preview, Supabase-backed API and durable AI worker."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime

ROOT=Path(__file__).resolve().parent.parent
processes=[]
log_threads=[]

def capture(name, process):
    path=ROOT/'logs'/f'{name}.log'
    with path.open('a',buffering=1) as output:
        output.write(f'\n--- Started {datetime.now().astimezone().isoformat()} PID {process.pid} ---\n')
        for line in process.stdout:
            output.write(line)
            print(f'[{name}] {line}',end='',flush=True)


def stop(*_):
    for p in processes:
        if p.poll() is None:
            try:
                os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass


def main():
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    (ROOT/'logs').mkdir(exist_ok=True)
    commands=[
        ('api',[str(ROOT/'.venv/bin/python'),'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--reload','--reload-dir',str(ROOT/'backend')]),
        ('frontend',['npm','run','dev']),
        ('worker',[str(ROOT/'.venv/bin/python'),'-u','-m','backend.worker']),
    ]
    try:
        for name,command in commands:
            process=subprocess.Popen(command,cwd=ROOT,start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            processes.append(process)
            reader=threading.Thread(target=capture,args=(name,process),daemon=True)
            reader.start();log_threads.append(reader)
        print('\nHakiSenseJournal: http://127.0.0.1:5173/\nAPI reference: http://127.0.0.1:8000/docs\nLogs: logs/api.log, logs/worker.log, logs/frontend.log\nPress Ctrl+C to stop all processes.\n',flush=True)
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
        for reader in log_threads:
            reader.join(timeout=1)


if __name__=='__main__':
    sys.exit(main())
