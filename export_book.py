"""Build or verify the portable reader and editable, self-contained book download."""
import argparse
import base64
from datetime import date
import io
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from reader_checks import check_html, check_public_text


book = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true', help='check generated files without writing')
args = parser.parse_args()
worker = (book / 'sw.js').read_text()
assets = json.loads(re.search(r'^const files = (\[.*?\]);', worker, re.M | re.S)[1])
reviewed = date.fromisoformat(json.loads((book / 'edition.json').read_text())['reviewed'])
portable_name = 'Read All About Devin.html'
output = book / 'All-About-Devin.zip'


def generated(path, data):
    if path.is_file() and path.read_bytes() == data:
        return
    if args.check:
        raise SystemExit(f'{path.name} is missing or stale. Run python3 update_edition.py.')
    with NamedTemporaryFile(dir=book, delete=False) as temp:
        temp.write(data)
    scratch = Path(temp.name)
    try:
        scratch.chmod(0o644)
        scratch.replace(path)
    finally:
        scratch.unlink(missing_ok=True)


bundle = {'json': {}, 'media': {}}
media_types = {'.svg': 'image/svg+xml', '.webp': 'image/webp', '.zip': 'application/zip'}
for name in assets:
    path = book / name
    key = './' + name
    if path.suffix == '.json':
        bundle['json'][key] = json.loads(path.read_text())
    elif path.suffix in media_types:
        raw = base64.b64encode(path.read_bytes()).decode('ascii')
        bundle['media'][key] = f'data:{media_types[path.suffix]};base64,{raw}'

html = (book / 'index.html').read_text()
html = re.sub(r'<a class="book-download\b[^"]*"[^>]*>.*?</a>', '', html)
html = html.replace('src="./cover.svg"', 'src="' + bundle['media']['./cover.svg'] + '"')
html = re.sub(r'<link rel="stylesheet" href="\./([^"]+)">',
              lambda m: '<style>\n' + (book / m[1]).read_text() + '\n</style>', html)
scripts = re.findall(r'<script src="([^"]+)" defer></script>', html)
html = re.sub(r'<script src="[^"]+" defer></script>', '', html)
html = re.sub(r'(?m)^[ \t]+$', '', html)
payload = json.dumps(bundle, ensure_ascii=True, separators=(',', ':')).replace('<', r'\u003c')
inline = '<script>window.portableDevinBook=' + payload + ';</script>\n'
for script in scripts:
    inline += '<script>\n' + (book / script).read_text() + '\n</script>\n'
html = html.replace('</body>', inline + '</body>')
check_html(html, 'portable HTML')
check_public_text((book / 'Read me.txt').read_text(), 'Read me.txt')
portable = html.encode('utf-8')

build_files = {'update_edition.py', 'export_book.py', 'review_history.py', 'copy_rules.py',
               'reader_checks.py', 'edition_trust.py', 'Read me.txt', 'UPDATING.md', 'sw.js'}
kit = book / 'practice/exchange-inventory'
members = set(assets) | build_files | {portable_name}
members.update(path.relative_to(book).as_posix() for path in kit.rglob('*')
               if path.is_file() and not any(part.startswith('.') for part in path.relative_to(kit).parts))
buffer = io.BytesIO()
with ZipFile(buffer, 'w') as archive:
    for name in sorted(members):
        entry = ZipInfo('all-about-devin/' + name, (reviewed.year, reviewed.month, reviewed.day, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, portable if name == portable_name else (book / name).read_bytes())
generated(book / portable_name, portable)
generated(output, buffer.getvalue())
print(f'{output.name}: {len(members)} files, {len(buffer.getvalue()):,} bytes')
