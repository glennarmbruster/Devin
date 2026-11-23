// The practice desk uses only two built-in sample notes. It never reads device files.
function actionButton(label, onClick) {
  const button = element('button', label, 'lab-action');
  button.type = 'button';
  button.onclick = onClick;
  return button;
}

function practiceDesk() {
  const box = element('section', undefined, 'desk');
  box.setAttribute('aria-label','Practice desk');
  box.append(element('div','Practice desk · works offline','eyebrow'), element('h2','Harbor Notes'));
  const files = element('div', undefined, 'desk-files');
  const paper = element('article', undefined, 'note-paper');
  paper.setAttribute('aria-live','polite');
  const notice = 'Meet at Pier 6 at 9:15 a.m. Bring a hat.';
  const draft = 'Meet at Pier 6 at 9:50 a.m. Bring a hat.';
  const fileContents = {
    'schedule.txt': 'Saturday ferry walk\nMeet at Pier 6 at 9:15 a.m.\nBring a hat.',
    'notice.txt': draft
  };
  function select(name) {
    for (const b of files.children) b.setAttribute('aria-pressed',String(b.textContent === name));
    paper.replaceChildren(element('h3',name),element('p',fileContents[name]));
  }
  for (const name of Object.keys(fileContents)) files.append(actionButton(name,()=>select(name)));
  const verdict = element('p', undefined, 'desk-verdict');
  verdict.setAttribute('role','status');
  const choices = element('div', undefined, 'desk-choices');
  const accept = actionButton('Use 9:15 a.m.',()=>decide(true));
  const reject = actionButton('Keep 9:50 a.m.',()=>decide(false));
  function decide(correct) {
    if (!correct) {
      verdict.textContent = 'Look again at schedule.txt. The ferry meeting starts at 9:15. Which time makes the notice match?';
      return;
    }
    fileContents['notice.txt'] = notice;
    select('notice.txt');
    verdict.textContent = 'You fixed the notice. Both notes now say Pier 6 at 9:15 a.m. The packing reminder stayed the same.';
    accept.disabled = reject.disabled = true;
  }
  const reset = actionButton('Start practice again',()=>{
    fileContents['notice.txt'] = draft;
    accept.disabled = reject.disabled = false;
    verdict.textContent = '';
    select('schedule.txt');
  });
  choices.append(accept, reject, reset);
  box.append(files,paper,element('h3','Which time belongs in the notice?'),choices,verdict);
  select('schedule.txt');
  return box;
}

function stepControls(list, single) {
  const nav = element('div', undefined, 'step-controls');
  nav.setAttribute('role','group');
  nav.setAttribute('aria-label','Walkthrough steps');
  const items = Array.from(list.children);
  const progress = element('span',undefined,'step-count');
  progress.setAttribute('role','status');
  let current = 0;
  const back = actionButton('← Previous step',()=>{ current--; draw(); });
  const next = actionButton('Next step →',()=>{ current++; draw(); });
  const toggle = actionButton('',()=>{ single = !single; draw(); });
  function draw() {
    for (const [i, item] of items.entries()) { item.hidden = single && i !== current; item.value = i + 1; }
    progress.textContent = single ? 'Step ' + (current + 1) + ' of ' + items.length : items.length + ' steps';
    toggle.textContent = single ? 'Show all steps' : 'One step at a time';
    back.hidden = next.hidden = !single;
    back.disabled = current === 0;
    next.disabled = current === items.length - 1;
  }
  nav.append(progress,back,next,toggle);
  draw();
  return nav;
}

function picture(figure) {
  const view = element('figure',undefined,'book-figure');
  const photo = element('img');
  photo.alt = figure.alt;
  photo.src = assetURL('./pictures/' + figure.file);
  photo.loading = 'lazy';
  const caption = element('figcaption');
  caption.append(element('span',figure.caption));
  const credit = element('a',figure.credit);
  credit.href = figure.source;
  if (!figure.source.startsWith('#')) credit.target = '_blank';
  credit.rel = 'noopener noreferrer';
  if (figure.source.startsWith('#')) caption.append(credit);
  else caption.append(element('span',figure.credit),externalLink('Check source',figure.source,'Check source · ' + figure.credit));
  const enlarge = actionButton('',()=>{
    const dialog = element('dialog',undefined,'image-view');
    const close = actionButton('Close picture',()=>dialog.close());
    const big = photo.cloneNode();
    big.loading = 'eager';
    dialog.setAttribute('aria-label','Enlarged picture');
    dialog.append(close,big,caption.cloneNode(true));
    dialog.addEventListener('close',()=>{dialog.remove();enlarge.focus();},{once:true});
    document.body.append(dialog);
    dialog.showModal();
  });
  enlarge.className = 'enlarge';
  enlarge.setAttribute('aria-label','Enlarge picture · ' + figure.alt);
  enlarge.append(photo,element('span','Enlarge picture'));
  view.append(enlarge,caption);
  return view;
}

function chapterPictures(id) {
  return illustrations.filter(f=>f.lesson === id || f.also?.includes(id));
}

function guideBody(chapter) {
  const block = element('section',undefined,'section');
  block.append(element('h2','Where to begin'));
  const places = element('ul');
  chapter.where.forEach(line => places.append(element('li',line)));
  block.append(places);
  const link = toolLink(chapter);
  if (link) {
    block.append(link);
    const basics = element('details',undefined,'step-help');
    basics.append(element('summary','Help with opening apps and files'));
    const links = element('nav',undefined,'quick-links');
    for (const [id,title] of [['open-web','Find your browser'],['make-folder','Make a practice folder'],['first-terminal','Open a terminal'],['first-project','Practice without an account']]) {
      const a = element('a',title);
      a.href = '#' + id;
      links.append(a);
    }
    basics.append(links);
    block.append(basics);
  }
  const walkthrough = element('section',undefined,'section');
  const list = element('ol',undefined,'lab-steps');
  for (const step of chapter.actions) {
    const item = element('li');
    const help = element('details',undefined,'step-help');
    help.append(element('summary','If you get stuck'),element('p',step.stuck));
    item.append(element('h3',step.title),element('p',step.do),element('strong','What you should see'),element('p',step.see),help);
    list.append(item);
  }
  walkthrough.append(element('h2','Walk through it'),stepControls(list,true),list);
  const sections = [block];
  if (chapter.id === 'first-project') sections.push(practiceDesk());
  sections.push(walkthrough);
  for (const figure of chapterPictures(chapter.id)) sections.push(picture(figure));
  const work = element('details',undefined,'sources');
  work.append(element('summary','Try it in your own work'));
  const roles = element('dl',undefined,'role-list');
  ['Exchange','Microsoft 365','Personal App'].forEach((role,i)=>roles.append(element('dt',role),element('dd',chapter.roles[i])));
  work.append(roles);
  sections.push(work,sourceLinks(chapter.sources));
  return sections;
}

function launchHelp(chapter) {
  const id = chapter.firstGuide || 'open-devin';
  const guide = guideChapters.find(c=>c.id === id) || guideChapters[0];
  const strip = element('aside',undefined,'launch-help');
  strip.append(element('strong','First time here? '));
  const link = element('a',guide.title);
  link.href = '#' + guide.id;
  strip.append(link);
  return strip;
}

const wordHelp = {
  'agent':'A helper that can take several steps toward a goal. It might read a file, make a change and show you the result.',
  'API':'A way for one program to ask another program to do something. A weather app can ask a weather service for a forecast.',
  'API key':'A secret used by an app to send requests on an account. Treat it like a password.',
  'artifact':'Something the helper makes that you can open and use, such as a checklist, chart or web page.',
  'branch':'A separate line of work in a project. You can try a change there before it becomes part of the shared copy.',
  'browser':'The app that opens websites. Safari, Chrome and Edge are browsers.',
  'cache':'A saved copy that an app can reuse later. This book saves its pages and pictures so you can read offline.',
  'chat':'A conversation made of turns. You send a message and the helper answers.',
  'CLI':'Short for command-line interface. It lets you tell a tool what to do by typing a command.',
  'cloud':'Computers reached over a network. A job that runs in the cloud can keep going away from your computer.',
  'command':'A typed instruction such as pwd. Press Enter to run it in a terminal.',
  'commit':'A saved checkpoint in the history of a project. Give it a name that tells you what changed.',
  'connector':'A link that lets a helper use another service, such as your calendar. Its permissions decide what it can reach.',
  'context':'The material a helper has available for this task, such as your directions and a file you supplied.',
  'CSV':'A plain-text table. Commas usually separate its columns, and each new line starts a row.',
  'diff':'A before-and-after view of an edit. Look for the old line and the proposed replacement.',
  'draft':'A first version you can still change. A draft email can be checked before you send it.',
  'export':'Save a copy in a form another app can open, such as a table saved as a CSV file.',
  'extension':'An extra feature you add to an app. A browser extension might help you read the page in front of you.',
  'fixture':'A small sample prepared for a test. It gives you a known input and a result you can check.',
  'folder':'A named place to keep related files together.',
  'grounding':'Giving the helper evidence it can use, such as a schedule, so you can trace where an answer came from.',
  'hallucination':'A made-up or mistaken answer that sounds convincing. Check its claim against the original source.',
  'integration':'A connection that lets two tools work together.',
  'JSON':'A text format that pairs names with values. For example, {"pier":6} stores a pier number.',
  'license':'Permission to use a product or feature. Your workplace may give different licenses to different people.',
  'local':'On the device in front of you. A local file is stored on that device.',
  'mailbox':'The place a mail service uses to store messages, calendar items and other material for an address.',
  'Markdown':'Plain text with simple marks for layout. For example, a line beginning with # and a space is a heading.',
  'MCP':'A common way for an AI tool to connect to other tools or information. Each connection still needs permission.',
  'model':'The part of an AI product that produces an answer or picture. One app may let you choose among several.',
  'permission':'A rule about what an account or app can see or change.',
  'PowerShell':'A program for typing commands and running saved instructions called scripts.',
  'project':'A named place for related work. It might hold chats, files or tasks depending on the app.',
  'prompt':'The request you type or say. “Put these three stops in time order” is a prompt.',
  'pull request':'A request for people to review changes before adding them to a shared project.',
  'read-only':'Allowed to look at information. Changes to the original are outside that permission.',
  'receipt':'A record of what a helper says it did. Open the actual result and check it.',
  'repo':'Short for repository, a collection of project files and their saved history.',
  'repository':'A collection of project files together with a record of their changes.',
  'role':'A bundle of permissions assigned to a person or app.',
  'schema':'A description of the fields a piece of data should have, such as name, time and place.',
  'scope':'The boundary of a request or permission. “Read these two files” describes a small scope.',
  'script':'A file containing instructions for a computer to run.',
  'session':'One stretch of work with a tool. Its messages and results are often kept together.',
  'source':'The original material behind a claim, such as the schedule that lists a sailing time.',
  'spreadsheet':'A grid of rows and columns. A cell is one box in that grid.',
  'SSO':'Single sign-on. Your organization’s usual sign-in page handles access to another app.',
  'synthetic':'Made up for practice. A synthetic mailbox record can stand in for a real person’s information.',
  'tenant':'An organization’s own area in a service such as Microsoft 365.',
  'terminal':'A window where you type commands. It usually shows a new prompt once a command finishes.',
  'token':'A piece of text a model processes. A word may use one or several tokens.',
  'workspace':'The area where a tool keeps a person’s or group’s work.'
};
function glossary(text) {
  const found = Object.entries(wordHelp).filter(([word])=>new RegExp('\\b'+word+'(?:s)?\\b','i').test(text));
  if (!found.length) return null;
  const details = element('details',undefined,'words');
  details.append(element('summary','Words on this page'));
  const list = element('dl');
  found.forEach(([word,meaning])=>list.append(element('dt',word),element('dd',meaning)));
  details.append(list);
  return details;
}

function toolLink(chapter) {
  const target = chapter.id === 'devin-review-first' ? ['Open Devin Review','https://app.devin.ai/review']
    : chapter.topic === 'Devin' ? ['Open Devin','https://app.devin.ai/'] : null;
  if (!target) return null;
  const link = element('a',target[0] + ' ↗','lab-action');
  link.href = target[1];
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}

function workedExample(example, chapterSummary) {
  const wrap = element('section',undefined,'section worked');
  wrap.append(element('h2','See a worked example'));
  if (example.premise !== chapterSummary) wrap.append(element('p',example.premise));
  const flow = element('ol',undefined,'example-flow');
  for (const [label,value] of [['Start with this',example.before],['Try this',example.try],['Look for this result',example.after]]) {
    const step = element('li');
    step.append(element('h3',label));
    if (label === 'Start with this') {
      if (example.buildPrompt) step.append(snippet(example.buildPrompt,'build prompt','Shared build prompt · send alone'));
      step.append(snippet(value,'practice card',example.caption || 'Message for the tool'));
    }
    else if (label === 'Try this') {
      const instructions = element('ol');
      for (const line of value.split(/\n(?=\d+\. )/)) instructions.append(element('li',line.replace(/^\d+\. /,'')));
      step.append(instructions);
    } else step.append(element('p',value));
    flow.append(step);
  }
  wrap.append(flow,element('p',example.why));
  const fix=element('details',undefined,'step-help');
  fix.append(element('summary','Something look different?'),element('p',example.rescue));
  if (example.rescuePrompt) fix.append(snippet(example.rescuePrompt,'follow-up','Follow-up message for the tool'));
  wrap.append(fix);
  if (example.noAccount) wrap.append(element('p','No account? '+example.noAccount));
  return wrap;
}

function drawGallery() {
  const wrap = byId('thumbs');
  for (const ch of chapters) {
    for (const figure of illustrations.filter(f=>f.lesson === ch.id)) {
      const link = element('a',undefined,'thumb');
      link.href = '#' + ch.id;
      const image = element('img');
      image.src = assetURL('./pictures/' + figure.file);
      image.alt = figure.alt;
      image.loading = 'lazy';
      link.append(image,element('strong',ch.title),element('span',figure.caption));
      wrap.append(link);
    }
  }
}
