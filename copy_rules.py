"""Audit the actual text a reader can copy, including local trial excerpts."""
import re

READER = re.compile(r'^\s*(?:paste|copy|send|open|save)\b|\bfresh chat\b|\bthis card\b|\bbelow the data\b|\bon paper\b|(?:^|[.!?]\s+)(?:paste|copy|open|save|send)\s+(?:this|these|the (?:prompt|sample|card|file))\b', re.I)
# Look inside multiline examples as well as at their first sentence.
COPY_DIRECTION = re.compile(
    r"\b(?:paste (?:this|the following)|copy (?:this|the following) (?:into|to)|"
    r"in (?:a|your) fresh chat|below the data|on paper|this card)\b|"
    r"(?:^|[.!?]\s+|\n)\s*(?:open|launch|start) (?:a |your )?(?:new|fresh) (?:chat|session)\b|"
    r"(?:^|[.!?]\s+|\n)\s*(?:paste|send) (?:this|the) (?:code|prompt|request|sample|text)\b", re.I)

# Split at sentence and run boundaries while keeping decimals, filenames and
# ordinary words like 'Open' in quoted filenames intact.
RUN_LABEL = re.compile(r'(?:^|(?<=[.!?])\s+)(?:First|Second) run:\s*', re.I)
ACTION = re.compile(
    r"^(?:(?:now|then|next|first|finally)[:,]?\s+)?(?:please\s+)?(?:write|ask|allow|give|change|keep|"
    r"compare|paste|open|send|save|run|use|choose|add|remove|read|record|include|hold|close|say|pick|"
    r"update|select|mark|check|test|start|stop|try|reject|return|list|follow|wait|repeat|roll back|"
    r"reopen|make|press|accept|leave|put|replay|play|take|expect|treat|switch|enter|hide|tap|restore|"
    r"quote|skip|find|click|show|set|count|look|print|attach|cover|replace|have|reset|clear|answer|reply|label)\b", re.I)
ROUTES = re.compile(r'\b(?:choose one route|either|on paper|or solve it by hand|or grade your own)\b', re.I)

def sentences(text):
    text = RUN_LABEL.sub(' ', text)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.M)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|[;\n]+', text) if s.strip()]

def normalized(text):
    return ' '.join(re.findall(r'[\w]+', text.casefold()))

def check_case(ex, page):
    key = ex['id']
    before = normalized(ex['before'])
    prompt = normalized(page.get('prompt', ''))
    if prompt and ' '+prompt+' ' in ' '+before+' ':
        raise ValueError('Give the worked example its own input in '+key)
    terms = ex.get('caseTerm','').split('|')
    for term in terms:
        if not normalized(term) or any(' '+normalized(term)+' ' not in ' '+normalized(ex[field])+' '
                                       for field in ('try','before')):
            raise ValueError('Use the same concrete case term in the input and steps: '+key+' / '+term)
    if any(ROUTES.search(v) for v in ex.values() if isinstance(v,str)):
        raise ValueError('Keep one worked route in '+key)
    actions = {normalized(line) for line in sentences(ex['try'])}
    for line in sentences(ex['after']):
        if normalized(line) in actions:
            raise ValueError('A result repeats a step in '+key+': '+line)
        if ACTION.search(line.lstrip('“\"‘')) or re.search(r'\b(?:you (?:should|must|need to)|(?:then|so) (?:ask|paste|click|give|write))\b', line, re.I):
            raise ValueError('Describe the outcome without a reader instruction in '+key+': '+line)

def check_payload(text, label):
    if not isinstance(text,str) or not text.strip() or READER.search(text) or COPY_DIRECTION.search(text):
        raise ValueError('Remove reader instructions from the copy box in '+label)

def page_boxes(row):
    if 'prompt' in row: yield 'lab request',row['prompt']
    for step in row.get('steps',[]):
        if 'code' in step:yield step['title'],step['code']
    for section in row.get('sections',[]):
        if 'practiceCode' in section:yield 'starter file',section['practiceCode']
        for prompt in section.get('prompts',[]):yield prompt['title'],prompt['text']
    for name in ('prompt','followUp'):
        if 'buildSpec' in row:yield name,row['buildSpec'][name]

def validate_worked(examples):
    """Reject repeated teaching patterns and messages whose boundaries are unclear."""
    from collections import Counter
    def normal(value):
        return ' '.join(re.findall(r'[a-z0-9]+', value.casefold()))
    whys, endings, questions = Counter(), Counter(), Counter()
    stale = ('before looking below','match the values, labels and order shown','in the original card',
             'show the changed row separately','cross out','paste this fictional practice card')
    tools = {'devin':'Devin'}
    for ex in examples:
        key = ex['id']
        message = ex.get('rescuePrompt','')
        check_payload(message, key+' / follow-up')
        joined = ' '.join(ex[k] for k in ('premise','before','try','after','why','rescue','rescuePrompt')).casefold()
        if any(phrase in joined for phrase in stale):
            raise ValueError('Replace old worked-example wording in '+key)
        opened = None
        for index,character in enumerate(message):
            before = message[index-1] if index else ' '
            after = message[index+1] if index+1 < len(message) else ' '
            if character in ("'", "’") and before.isalnum() and after.isalnum():
                continue  # Apostrophe inside a word, such as driver's.
            if character in ('“','‘'):
                if opened: raise ValueError('Nested follow-up quotes in '+key)
                opened = {'“':'”','‘':'’'}[character]
            elif character in ('”','’'):
                if opened != character: raise ValueError('Mismatched follow-up quotes in '+key)
                opened = None
            elif character in ('"', "'"):
                if opened == character: opened = None
                elif opened: raise ValueError('Nested follow-up quotes in '+key)
                else: opened = character
        if opened: raise ValueError('Unclosed follow-up quote in '+key)
        why = normal(ex['why'])
        whys[why] += 1
        # A request can end in an imperative. Check that ending too.
        sentences = re.split(r'(?<=[.!?])\s+', ex['before'].strip())
        endings[normal(sentences[-1])] += 1
        actual_questions = re.findall(r'(?:^|(?<=[.!?\n]))\s*([^.!?\n]+\?)', ex['before'])
        if actual_questions:
            questions[re.sub(r'\d+', '#', normal(actual_questions[-1]))] += 1
        for track,tool in tools.items():
            if key.startswith('lab-'+track+'-') and tool.casefold() not in ex['try'].casefold():
                raise ValueError('Show how to use '+tool+' in '+key)
    if max(whys.values()) > 1:
        raise ValueError('A worked explanation is repeated')
    if max(endings.values()) > 3 or max(questions.values(), default=0) > 3:
        raise ValueError('A worked request ending occurs more than three times')
