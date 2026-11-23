"""Record an explicit review or audit notice and rebuild the offline edition."""
import json
from datetime import date
from pathlib import Path
import subprocess
import sys


def save_rows(path, rows):
    temp = path.with_suffix('.json.tmp')
    with temp.open('x', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    temp.replace(path)


def apply_changes(book, changes):
    """Allow the normal validator to reject edits; restore inputs and outputs on failure."""
    originals = {path: path.read_bytes() for path in changes}
    build = [sys.executable, str(book / 'update_edition.py')]
    try:
        for path, value in changes.items():
            save_rows(path, value)
        subprocess.run(build, check=True)
        subprocess.run([*build, '--check'], check=True)
    except BaseException:
        for path, raw in originals.items():
            path.write_bytes(raw)
        subprocess.run(build, check=False)
        raise


def record_review(book, page_id, day, note):
    manifest_path = book / 'edition.json'
    manifest = json.loads(manifest_path.read_text())
    changes = {manifest_path: manifest}
    for group in manifest['groups']:
        path = book / 'content' / group['file']
        rows = changes.get(path) or json.loads(path.read_text())
        row = next((r for r in rows if r['id'] == page_id), None)
        if row is None:
            continue
        if day > date.today() or day < date.fromisoformat(row['lastVerified']):
            raise SystemExit('Use a review date from the previous review through today.')
        day_text = day.isoformat()
        row.update(lastVerified=day_text, basis=sorted(set(row['basis']) | {'human-tested'}))
        changes[path] = rows
        group['reviewed'] = max(group['reviewed'], day_text)
        manifest['reviewed'] = max(manifest['reviewed'], day_text)
        history = manifest.setdefault('reviews', [])
        entry = dict(date=day_text, where=page_id, what=note, kind='review')
        if entry not in history:
            history.append(entry)
        apply_changes(book, changes)
        return
    raise SystemExit('Unknown page ID.')
