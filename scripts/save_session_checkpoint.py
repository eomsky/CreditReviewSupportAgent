"""Save the local dashboard and candidate without rerunning any test."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    now = datetime.now().astimezone()
    dest = ROOT / 'outputs' / 'session_checkpoints' / now.strftime('%Y%m%d-%H%M%S')
    monitor = ROOT / 'outputs/business_report_test'
    dest.mkdir(parents=True)
    # Preserve the exact pre-pause state before changing presentation status.
    shutil.copytree(monitor, dest / 'dashboard-before-pause',
                    ignore=shutil.ignore_patterns('*.log'))
    session_path = monitor / 'experiment-session.json'
    session = json.loads(session_path.read_text(encoding='utf-8-sig'))
    session.update(status='paused_by_user', paused_at=now.isoformat(),
                   active_candidate='C20.46-full-quality', allow_new_candidates=False,
                   stop_condition='User paused testing; resume only on user request.')
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    state_path = monitor / 'experiment-monitor-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8-sig'))
    state.update(stopped_at=now.isoformat(), updated_at=now.isoformat(),
                 stage='사용자 요청으로 중단 · C20.46 저장 · Step 19부터 재개 · 전체실행 미검증')
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    # Step data intentionally remains unchanged, including last highlighted row.
    shutil.copytree(monitor, dest / 'dashboard', ignore=shutil.ignore_patterns('*.log'))
    shutil.copytree(ROOT / 'outputs/step_trials/C20.46-full-quality', dest / 'candidate')
    steps = json.loads((monitor / 'experiment-structuring-steps.json').read_text(encoding='utf-8-sig'))
    metadata = {'saved_at': now.isoformat(), 'status': 'paused_by_user',
                'candidate': 'C20.46-full-quality', 'resume_step': 19,
                'end_to_end_verified': False, 'steps': steps,
                'restore_dashboard': 'Copy dashboard/* to outputs/business_report_test; serve that directory on 127.0.0.1:8766.',
                'note': 'Retain approved steps; do not rerun them merely to restore the dashboard.'}
    (dest / 'resume.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in dest.rglob('*') if p.is_file()}
    (dest / 'sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, digest in manifest.items():
        assert hashlib.sha256((dest / name).read_bytes()).hexdigest() == digest
    (ROOT / 'outputs/session_checkpoints/LATEST.txt').write_text(str(dest), encoding='utf-8')
    print(json.dumps({'checkpoint': str(dest), 'verified_files': len(manifest),
                      'resume_step': 19}, ensure_ascii=False))


if __name__ == '__main__':
    main()
