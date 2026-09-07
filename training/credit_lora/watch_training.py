"""Watch one explicitly identified Linux training process, preserving recovery time."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import time


def identity(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return stat[19] if stat[0] != 'Z' else None
    except (FileNotFoundError, ProcessLookupError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pid', type=int)
    parser.add_argument('run', type=Path)
    parser.add_argument('--deadline', required=True)
    parser.add_argument('--stale-seconds', type=float, default=600)
    parser.add_argument('--grace-seconds', type=float, default=120)
    args = parser.parse_args()
    token = identity(args.pid)
    if token is None:
        raise SystemExit('Training process is not running')
    command = Path(f'/proc/{args.pid}/cmdline').read_bytes().split(b'\0')
    if not any(x.endswith(b'/train.py') for x in command):
        raise SystemExit('Refusing to monitor a non-training process')
    deadline = datetime.fromisoformat(args.deadline).timestamp()
    observed = time.time()
    stop_at = None
    while identity(args.pid) == token:
        now = time.time()
        progress = args.run / 'progress.json'
        latest = max(observed, progress.stat().st_mtime if progress.exists() else observed)
        reason = 'deadline' if now >= deadline else 'no_progress' if now - latest > args.stale_seconds else None
        if reason and stop_at is None:
            stop_at = now
            record = {'time': datetime.now(timezone.utc).isoformat(), 'reason': reason,
                      'pid': args.pid, 'action': 'SIGTERM_save_requested'}
            (args.run / 'watchdog.json').write_text(json.dumps(record, indent=2))
            os.kill(args.pid, signal.SIGTERM)
            print(json.dumps(record), flush=True)
        elif stop_at is not None and now - stop_at > args.grace_seconds:
            # Kill only this exact process, never another notebook's process group.
            if identity(args.pid) == token:
                os.kill(args.pid, signal.SIGKILL)
            record['action'] = 'SIGKILL_after_save_grace'
            (args.run / 'watchdog.json').write_text(json.dumps(record, indent=2))
            print(json.dumps(record), flush=True)
            break
        time.sleep(10)
    print('WATCH_FINISHED', flush=True)


if __name__ == '__main__':
    main()
