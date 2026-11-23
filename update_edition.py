"""Validate the chapter files and refresh the standalone Devin reader and download."""
import argparse
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree
from urllib.parse import urlsplit
from copy_rules import check_payload, page_boxes, check_case
from reader_checks import validate_reader, expand_catalogs
from edition_trust import valid_basis, valid_source, hardcoded, PRODUCT_GROUPS, FIELD, chapter_field
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

book = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true', help='check without writing')
parser.add_argument('--review', metavar='PAGE', help='record a completed hands-on human review of one page')
parser.add_argument('--date', type=date.fromisoformat, help='review date as YYYY-MM-DD (default: today)')
parser.add_argument('--note', help='short, shareable description of the review')
args = parser.parse_args()
if args.review:
    if args.check or not args.note or not args.note.strip():
        parser.error('--review requires --note and cannot be combined with --check')
    from review_history import record_review
    record_review(book, args.review, args.date or date.today(), args.note.strip())
    sys.exit(0)
if args.date or args.note:
    parser.error('--date and --note require --review')


def require(value, message):
    if not value:
        raise SystemExit(message)


def words(values):
    return isinstance(values, list) and values and all(isinstance(v, str) and v.strip() for v in values)


# The exclusion list is a build rule, never part of the reader or its content.
other_tools = re.compile(r'\b(?:ChatGPT|OpenAI|Claude|Anthropic|Gemini|Copilot|Grok|Perplexity|Muse|Firefly|Vibe|Antigravity|Codex)\b', re.I)


def check_sample_text(value, path):
    """Reject personal contact details or device paths accidentally pasted into book files."""
    require(not other_tools.search(value), f'Remove unrelated product material from {path}')
    for match in re.finditer(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})', value):
        host = match[1].lower()
        require(host.endswith(('.test', '.invalid')) or host in {'example.org','example.net','example.com'}, f'Use a made-up email address in {path}')
    require(not re.search(r'(?:/Users/|C:\\Users\\|/home/)[A-Za-z0-9._-]+', value, re.I), f'Remove the personal home folder in {path}')
    require(not re.search(r'(?<![\w.-])(?:\+1[-. ]?)?\(\d{3}\)[-. ]*\d{3}[-. ]\d{4}\b', value), f'Remove the personal phone number in {path}')

    secret = re.search(r'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|'
                       r'\b(?:gh[pousr]_[A-Za-z0-9]{32,}|github_pat_[A-Za-z0-9_]{44,}|'
                       r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}|AKIA[A-Z0-9]{16})\b', value)
    require(not secret, f'Remove the credential from {path}')


def check_sources(sources, key):
    require(sources, f'Missing sources in {key}')
    for label, link in sources:
        require(label and valid_source(link), f'Invalid source in {key}')


legacy = ['Starter'] * 3 + ['Intermediate'] * 4 + ['Advanced'] * 3 + ['Expert'] * 5
second = ['Starter'] * 6 + ['Intermediate'] * 7 + ['Advanced', 'Expert']
track_levels = {'devin': legacy + second}


def check_lab(lab, track, number):
    key = lab['id']
    require(key == f'lab-{track}-{number:02}', f'Unexpected lab order for {key}')
    require(words([lab[k] for k in ('level', 'requires', 'features', 'prompt')]), f'Incomplete brief in {key}')
    require(lab['level'] == track_levels[track][number-1], f'Unexpected level in {key}')
    require(words(lab['roles']) and len(lab['roles']) == 3, f'Check roles in {key}')
    require(len(lab['steps']) >= 3 and words(lab['check']), f'Incomplete walkthrough in {key}')
    for step in lab['steps']:
        require(words([step[k] for k in ('title', 'text', 'help')]), f'Step missing guidance in {key}')
        if 'code' in step:
            require(words([step['code']]), f'Empty example in {key}')
    check_sources(lab['sources'],key)


def refresh_kit(folder):
    # Fixed file order and metadata make identical kits produce identical editions.
    for name in ('mailboxes.csv', 'Test-Inventory.ps1', 'Reference/Get-MailboxInventory.ps1', 'README.md'):
        require((folder / name).is_file(), f'Missing practice file {name}')
    expected = {'README.md','Test-Inventory.ps1','mailboxes.csv','Reference/Get-MailboxInventory.ps1'}
    require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and not p.name.startswith('.')} == expected,
            'The kit should include only the four inventory exercise files')
    packed = io.BytesIO()
    with ZipFile(packed, 'w') as archive:
        for source in sorted(folder.rglob('*')):
            if source.is_file() and not any(p.startswith('.') for p in source.relative_to(folder).parts):
                info = ZipInfo((Path(folder.name) / source.relative_to(folder)).as_posix())
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())
    output = folder.with_suffix('.zip')
    if not output.exists() or packed.getvalue() != output.read_bytes():
        require(not args.check, f'Run update_edition.py to refresh {output.name}')
        output.write_bytes(packed.getvalue())
    return output.relative_to(book).as_posix()


manifest = json.loads((book / 'edition.json').read_text())
edition_date = date.fromisoformat(manifest['reviewed'])
groups = manifest['groups']
ids = set()
assets = ['index.html', 'reader.css', 'reader.js', 'guides.js', 'guide.css', 'content/figures.json', 'content/worked.json', 'content/models.json', 'edition.json', 'book-pager.js', 'cover.svg', 'worker.js']
kit = refresh_kit(book / 'practice' / 'exchange-inventory')
assets.append(kit)
assets.append('content/facts.json')
fact_rows = json.loads((book/'content/facts.json').read_text())
facts = {row['key']:row for row in fact_rows}
used_facts = set()
require(len(facts)==len(fact_rows), 'Duplicate product fact key')
for name,row in facts.items():
    require(re.fullmatch(r'[a-z0-9.-]+',name) and words([row['value']]) and valid_source(row['source']), 'Invalid product fact '+name)
    require(valid_basis(row['basis']) and date.fromisoformat(row['verifiedOn']) <= edition_date and '{{fact.' not in row['value'], 'Invalid date, basis or nested product fact in '+name)
expected_groups = {'begin-basics.json':10, 'begin-devin.json':4, 'devin.json':14,
                   'devin-reference.json':12, 'labs-devin.json':30}
require(manifest['title'] == 'All About Devin' and isinstance(manifest['version'],int)
        and manifest['version'] > 0, 'Check the book title and edition')
require(len(groups)==len(expected_groups) and {g['file'] for g in groups}==set(expected_groups),
        'List all five Devin groups exactly once')
group_titles = {'devin.json':'{{fact.devin.enterprise.name}}',
                'labs-devin.json':'{{fact.devin.enterprise.name}} Hands-On Labs',
                'devin-reference.json':'Devin: full potential',
                'begin-basics.json':'First steps','begin-devin.json':'Cognition · Devin'}
require(all(g['title'] == group_titles[g['file']] for g in groups), 'Check the five group titles')
lab_count = 0
guide_ids = set()
reference_ids = set()
page_text = {}
writing_labs = []
require(groups, 'List at least one group in edition.json.')
for group in groups:
    require(group['title'] and date.fromisoformat(group['reviewed']) <= edition_date, 'Check group title and review date.')
    require(re.fullmatch(r'[a-z0-9-]+\.json', group['file']), 'Use a plain JSON filename for each group.')
    path = 'content/' + group['file']
    require(path not in assets, f'Duplicate group file {path}')
    assets.append(path)
    chapters = json.loads((book / path).read_text())
    require(len(chapters) == expected_groups[group['file']], f'Unexpected page count in {path}')
    if group.get('track'):
        require(words([group['startLabel'],group['gettingStarted']]) and (urlsplit(group['startUrl']).scheme == 'https' or group['startUrl'] in {'#get-kit','#first-project','#which-account'}), f'Check setup help in {path}')
        require(group['track'] in track_levels and len(chapters) == len(track_levels[group['track']]), f'Incorrect track or lab count in {path}')
    for number, ch in enumerate(chapters, start=1):
        key = ch['id']
        require(re.fullmatch(r'[a-z0-9-]+', key) and key not in ('contents', 'labs', 'start') and key not in ids, f'Invalid or duplicate ID {key}')
        ids.add(key)
        require(words([ch['title'], ch['summary']]), f'Incomplete page {key}')
        page_text[key] = ch
        require(valid_basis(ch.get('basis')) and 'ai-drafted' in ch['basis'], 'Invalid review basis in '+key)
        require(date.fromisoformat(ch['lastVerified']) <= date.fromisoformat(group['reviewed']), 'Invalid review date in '+key)
        if group.get('guide'):
            require(words(ch['where']) and words(ch['roles']) and len(ch['roles']) == 3, f'Check setup and roles in {key}')
            require(len(ch['actions']) >= 4 and ch['topic'], f'Incomplete guide {key}')
            for step in ch['actions']:
                require(words([step[k] for k in ('title','do','see','stuck')]), f'Missing walkthrough in {key}')
            check_sources(ch['sources'],key)
            guide_ids.add(key)
            continue
        if group.get('track'):
            check_lab(ch, group['track'], number)
            if 'writeYourOwn' in ch:
                exercise = ch['writeYourOwn']
                require(ch['level'] in {'Intermediate','Advanced'} and
                        words([exercise[k] for k in ('goal','given','compare')]), f'Check prompt-writing exercise in {key}')
                writing_labs.append(group['track'])
            require('kit' not in ch or ch['kit'] == kit, f'Unknown kit in {key}')
            lab_count += 1
            continue
        reference_ids.add(key)
        require(words(ch['tags']) and len(set(ch['tags'])) == len(ch['tags']) and
                all(re.fullmatch(r'[a-z0-9-]+', tag) for tag in ch['tags']), f'Invalid reference tags in {key}')
        require(date.fromisoformat(ch['lastVerified']) <= date.fromisoformat(group['reviewed']) and
                valid_basis(ch['basis']), f'Invalid page review in {key}')
        require('unverified' not in ch or words(ch['unverified']), f'Empty unverified details in {key}')
        require(ch['sections'], f'Incomplete chapter {key}')
        intro = ch['intro']
        require(words([intro[k] for k in ('what', 'features', 'exchange', 'm365', 'developer')]) and intro['sources'], f'Incomplete introduction in {key}')
        for label, link in intro['sources']:
            require(label and valid_source(link), f'Invalid introduction source in {key}')
        for section in ch['sections']:
            require(section['title'] and words(section['paragraphs']) and section['sources'], f'Incomplete section in {key}')
            for label, link in section['sources']:
                require(label and valid_source(link), f'Invalid source in {key}')
            if 'exercise' in section:
                exercise = section['exercise']
                require(words([exercise['prompt']]) and words(exercise['answer']), f'Incomplete exercise in {key}')
                for question in exercise.get('questions', []):
                    choices = question['choices']
                    require(words([question['prompt'], question['why']]) and words(choices) and
                            len(set(choices)) == len(choices) >= 2 and type(question['correct']) is int and
                            0 <= question['correct'] < len(choices), f'Invalid practice choice in {key}')
            if 'table' in section:
                tbl = section['table']
                require(words(tbl['columns']) and tbl['rows'], f'Empty table in {key}')
                require(all(words(row) and len(row) == len(tbl['columns']) for row in tbl['rows']), f'Invalid table in {key}')

surface_names = set('ask agent deepwiki review skills blueprints cli apps scheduled workflows integrations outposts'.split())
surface_titles = ['What it is for','Do this first','What it cannot do','Plan and availability','Gotchas','Official docs']
for surface in surface_names:
    key = 'devin-reference-' + surface
    row = page_text.get(key, {})
    require(row.get('summary') != row.get('intro', {}).get('what'), 'Give the surface its own introduction: '+key)
    require(row.get('surface') == surface and key in reference_ids, 'Missing surface '+surface)
    sections = row['sections']
    require([s['title'] for s in sections] == surface_titles, 'Check sections in '+key)
    availability = key+'.availability'
    require(sections[3]['paragraphs'] == ['{{fact.'+availability+'}}'] and availability in facts,
            'Missing availability record for '+surface)
    official = {url for _,url in sections[-1]['sources']}
    require(len({urlsplit(u).path.rstrip('/') for u in official}) >= 2, 'Use two distinct sources for '+key)
    links = {url for part in [row['intro'],*sections] for _,url in part['sources']} | {facts[availability]['source']}
    require(all(valid_source(u) and urlsplit(u).hostname=='docs.devin.ai' and urlsplit(u).path.strip('/') for u in links), 'Use official Devin docs for '+key)
require(lab_count==30 and len(reference_ids)==26 and len(guide_ids)==14, 'Incorrect chapter mix')
for record in manifest.get('reviews',[]):
    require(record['where'] in ids and words([record['what']]) and date.fromisoformat(record['date'])<=edition_date,
            'Invalid review record')
catalog = json.loads((book / 'content/models.json').read_text())
require(date.fromisoformat(catalog['reviewed']) <= edition_date, 'Check model catalog date')
values = catalog['values']
require(isinstance(values, dict), 'Invalid model catalog')
for field, entry in values.items():
    require(re.fullmatch(r'[a-z0-9.-]+',field) and words([entry['text']]), f'Invalid model field {field}')
    check_sources([[field,entry['source']]],field)
used = set()
def check_refs(value):
    if isinstance(value, str):
        def take(match):
            field = match[1]
            require(field in values, f'Unknown model field {field}')
            used.add(field)
            return values[field]['text']
        clean = re.sub(r'\{\{model\.([a-z0-9.-]+)\}\}',take,value)
        require('{{model.' not in clean, 'Unresolved model field')
        for field in re.findall(r'\{\{fact\.([a-z0-9.-]+)\}\}',clean):
            require(field in facts,'Unknown product fact '+field)
            used_facts.add(field)
        require('{{fact.' not in re.sub(r'\{\{fact\.[a-z0-9.-]+\}\}','',clean),'Malformed product fact')
    elif isinstance(value, list):
        for item in value: check_refs(item)
    elif isinstance(value, dict):
        for item in value.values(): check_refs(item)
def strings_in_content(value):
    if isinstance(value, str):
        if not value.startswith('https://'): yield value
    elif isinstance(value, list):
        for item in value: yield from strings_in_content(item)
    elif isinstance(value, dict):
        for key,item in value.items():
            if key not in {'id','sources'}: yield from strings_in_content(item)

def check_rendered_payload(text, label):
    # Catalog entries are resolved by the reader before the clipboard sees them.
    check_payload(text, label)
    check_payload(expand_catalogs(text, facts, values), label)

for group in groups:
    rows = json.loads((book/'content'/group['file']).read_text())
    for item in rows:
        for section in item.get('sections', []):
            for prompt in section.get('prompts', []):
                require(words([prompt['tool'],prompt['title'],prompt['text']]) and prompt['page'] in reference_ids, 'Invalid prompt library reference')
        if 'relatedLabs' in item:
            links = item['relatedLabs']
            require(words(links) and len(links) == len(set(links)) and all(link in ids and link.startswith('lab-') for link in links), 'Unknown or repeated lab link in '+item['id'])
        require('firstGuide' not in item or item['firstGuide'] in guide_ids, 'Invalid first lesson for '+item['id'])
    if group['file'] in PRODUCT_GROUPS:
        for line in strings_in_content(rows):
            require(not hardcoded(line), 'Put plan names and numeric product limits in the facts or models catalog: '+group['file']+' / '+line[:95])
    for page in rows:
        for name, body in page_boxes(page): check_rendered_payload(body,page['id']+' / '+name)
    check_refs(rows)
examples = json.loads((book / 'content/worked.json').read_text())
require(len(examples) == len(ids - guide_ids) and {ex['id'] for ex in examples} == ids - guide_ids, 'Every reference and lab needs its own worked example')
for ex in examples:
    page = page_text[ex['id']]
    text_fields = set(strings_in_content(page))
    for name in ('before','try','after','why','premise','rescue'):
        field = ex[name]
        ref = re.fullmatch(r'\{\{chapter\.([A-Za-z0-9_.-]+)\}\}',field)
        if ref:
            ex[name] = chapter_field(page,ref[1])
        else:
            require('{{chapter.' not in field and field not in text_fields, 'Reference the original chapter field in '+ex['id']+' / '+name)
    require(words([ex[k] for k in ('premise','before','try','after','why','rescue')]), 'Incomplete worked example '+ex['id'])
    key = ex['id']
    require(len(ex['before']) >= 100 and re.search(r'[?]|\b(?:list|read|return|count|give|match|paste|report)\b',ex['before'],re.I), 'Worked card needs data and an instruction in '+key)
    check_rendered_payload(ex['before'],key+' / worked input')
    check_rendered_payload(ex['rescuePrompt'],key+' / worked follow-up')
    resolved = {name:expand_catalogs(value,facts,values) for name,value in ex.items()}
    check_case(resolved, {'prompt':expand_catalogs(page.get('prompt',''),facts,values)})
    steps = ex['try'].splitlines()
    require(2 <= len(steps) <= 5 and all(line.startswith(f'{n}. ') and len(line)>12 for n,line in enumerate(steps,1)), 'Number the worked steps in '+key)
    require(re.fullmatch(r'First run: .+?\. Second run: .+?\. .+',ex['after']) and len(ex['after']) >= 40, 'Show the checked result of both runs in '+key)
    require(len(ex['why']) >= 20 and len(ex['rescue']) >= 35 and re.search(r'\b(?:send|ask|type|write|retry|repeat)\b',ex['rescue'],re.I), 'Give the reader a rescue message in '+key)
from copy_rules import validate_worked
validate_worked(examples)
check_refs(examples)
check_refs(manifest)
from collections import Counter
role_lines = Counter(' '.join(ch['intro'][role].lower().split()) for ch in page_text.values()
                     if 'intro' in ch for role in ('exchange','m365','developer'))
require(all(count <= 2 for count in role_lines.values()), 'Give reference introductions distinct role examples')
layout_words = re.compile(r'\b(?:below|above|(?:next|previous) section)\b',re.I)
for key, page in page_text.items():
    for field in strings_in_content(page):
        require(not layout_words.search(field), 'Replace screen-relative wording in '+key)
for ex in examples:
    for field in ex.values():
        require(not layout_words.search(field), 'Replace screen-relative wording in worked example '+ex['id'])
figures = json.loads((book / 'content/figures.json').read_text())
check_refs(figures)
check_refs(fact_rows)
require(used_facts == set(facts), 'Unused product facts: '+', '.join(sorted(set(facts)-used_facts)))
require({p.name for p in (book/'content').glob('*.json')} ==
        {Path(a).name for a in assets if a.startswith('content/')}, 'Register every content file for offline reading')
require(used == set(values), 'Unused model fields: ' + ', '.join(sorted(set(values)-used)))
illustrated = {page for figure in figures for page in [figure['lesson'],*figure.get('also',[])]}
required_pages = reference_ids | {'lab-devin-01','lab-devin-15','lab-devin-29','lab-devin-30'}
require(required_pages <= illustrated, 'Missing pictures for '+', '.join(sorted(required_pages-illustrated)))
require({p.name for p in (book/'pictures').iterdir() if not p.name.startswith('.')} == {f['file'] for f in figures},
        'Picture list does not match the files')
for fig in figures:
    name = fig['file']
    require(re.fullmatch(r'[a-z0-9-]+\.(webp|svg)', name), f'Invalid picture name {name}')
    path = 'pictures/' + name
    require(fig['lesson'] in ids and path not in assets and words([fig['credit'], fig['caption'], fig['alt']]), f'Check picture {name}')
    related = fig.get('also', [])
    require(set(related) <= ids and len(set([fig['lesson'],*related])) == len(related) + 1, f'Unknown or duplicate figure target in {name}')
    if fig['source'].startswith('#'):
        require(fig['source'][1:] in ids, f'Unknown local figure source {name}')
    else:
        check_sources([[fig['credit'], fig['source']]],name)
    if name.endswith('.svg'):
        svg = ElementTree.parse(book / path).getroot()
        ns = '{http://www.w3.org/2000/svg}'
        colors = {el.get(attr) for el in svg.iter() for attr in ('fill', 'stroke')
                      if el.get(attr) not in (None, 'none')}
        require(colors == {'#faf6ea', '#182c2d', '#145756', '#8b571b'}, f'Check the book palette in {name}')
        require(svg.tag == ns+'svg' and svg.get('viewBox') and svg.findtext(ns+'title') and svg.findtext(ns+'desc'), f'Diagram needs a title and description: {name}')
        require(all(el.tag in {ns+t for t in ('svg','title','desc','defs','marker','rect','text','path')} for el in svg.iter()), f'Unexpected SVG element {name}')
    else:
        require((book / path).read_bytes()[8:12] == b'WEBP', f'Invalid WebP {name}')
    assets.append(path)

for path in [*assets, 'UPDATING.md', *[p.relative_to(book).as_posix() for p in (book/'practice/exchange-inventory').rglob('*') if p.is_file()]]:
    if Path(path).suffix in {'.json','.svg','.csv','.md','.ps1','.html','.js','.css','.txt','.eml'}:
        check_sample_text((book/path).read_text(), path)

validate_reader(book, manifest, page_text, examples, figures, facts, values)
# Check the cover and every local entry point before producing either edition.
cover = ElementTree.parse(book/'cover.svg').getroot()
ns = '{http://www.w3.org/2000/svg}'
require(cover.findtext(ns+'title') == manifest['title'] and cover.findtext(ns+'desc'), 'Check the cover title and description')
require(set(re.findall(r'#[0-9a-fA-F]{6}',(book/'cover.svg').read_text())) == {'#faf6ea','#182c2d','#145756','#8b571b'}, 'Use the book palette on the cover')
for filename in ('Read me.txt','UPDATING.md'):
    check_sample_text((book/filename).read_text(),filename)
html = (book/'index.html').read_text()
for href in re.findall(r'(?:href|src)="([^"]+)"',html):
    if href.startswith('#'):
        require(href[1:] in ids | {'main','contents','start','labs','pictures'},'Broken home link: '+href)
    else:
        require(href.startswith('./') and (href[2:] in assets or href=='./All-About-Devin.zip'), 'Unknown home asset: '+href)
digest = sha256()
for path in assets:
    digest.update(path.encode()+b'\0'+sha256((book/path).read_bytes()).digest())
edition = 'all-about-devin-'+digest.hexdigest()[:16]
worker = '// Generated by update_edition.py\nconst edition = '+json.dumps(edition)+';\nconst files = '+json.dumps(assets,indent=2)+";\nimportScripts('./worker.js');\n"
target = book/'sw.js'
if not target.is_file() or target.read_text() != worker:
    require(not args.check,'Refresh the offline cache with update_edition.py')
    target.write_text(worker)
subprocess.run([sys.executable, str(book/'export_book.py'), *(['--check'] if args.check else [])], check=True)
print(f'{len(ids)} pages, {lab_count} labs, {len(figures)} illustrations. {edition}')
