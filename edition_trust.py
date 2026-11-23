"""Shared rules for source-backed product facts and editorial review records."""
from datetime import date
import re
from urllib.parse import urlsplit

BASIS = {'ai-drafted', 'source-read', 'human-tested'}
PRODUCT_GROUPS = {'devin.json','devin-reference.json'}
FIELD = re.compile(r'\{\{(model|fact)\.([a-z0-9.-]+)\}\}')
# Product limits have a unit or a quota phrase. A made-up score or time on a clock is exercise data.
QUOTA = re.compile(r'\b(?:up to|maximum(?: of)?|at most|limited to|limit(?: of| is)?|at least)\s+(?:\d[\d,.]*|one|two|three|four|five|ten|twenty)\s+(?:files?|projects?|requests?|tokens?|messages?|tasks?|years? old|MB|GB|uploads?|credits?|seats?)\b|\b\d[\d,.]*\s*(?:MB|GB|TB|tokens? per|files? per|messages? per|requests? per|credits? per|tokens? of context)\b|\b(?:quota|allowance|upload limit|context window)\s*(?:of|is|:|=)?\s*\d', re.I)
BOUND = re.compile(r'\b(?:maximum(?: of)?|up to|at most|limit(?:ed)? (?:of |to )?|allows? (?:up to )?)\s*\d[\d,.]*\s*(?:K|M|million)?\s*(?:input |output |concurrent |active |scheduled )?(?:minutes?|hours?|days?|pages?|characters?|pixels?|GB|MB|TB|tokens?|files?|uploads?|requests?|sessions?|tasks?|seats?|projects?|messages?)\b|\b\d[\d,.]*\s+(?:calls?|requests?|messages?|images?|videos?|tasks?)\s+(?:per|each|a)\s+(?:day|week|month|hour|minute|user|seat|session)\b',re.I)
PLAN = re.compile(r'\bDevin (?:Core|Team|Enterprise)\b|\b(?:Free|Plus|Pro|Max|Team|Enterprise) (?:plan|tier|subscription|accounts?)\b', re.I)
FORMATS = re.compile(r'\b(?:supports?|accepts?|upload limits?|available to|requires? (?:a |an )?(?:paid|eligible)|paid (?:plan|recurring task)|free and paid plans|supported (?:file types|formats))\b',re.I)
def hardcoded(text):
    clean = FIELD.sub('',text)
    return bool(PLAN.search(clean) or QUOTA.search(clean) or BOUND.search(clean) or clean in {'Free','Plus','Pro','Max','Ultra','Business','Enterprise','Team'})
def valid_basis(values):
    return isinstance(values,list) and bool(values) and all(isinstance(v,str) and v in BASIS for v in values) and len(values)==len(set(values))
def valid_source(url):
    parsed = urlsplit(url)
    return parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username and not parsed.password
def oldest_first(rows):
    return sorted(rows,key=lambda r:(r['verifiedOn'],r['key']))
def stale(row, today):
    return 'Not verified' in row['value'] or (today-date.fromisoformat(row['verifiedOn'])).days>=30
def chapter_field(page,path):
    node=page
    for part in path.split('.'):
        node=node[int(part)] if isinstance(node,list) else node[part]
    if not isinstance(node,str) or not node.strip():
        raise ValueError('Worked reference must name a nonempty chapter text field')
    return node
