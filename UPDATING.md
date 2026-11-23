# Maintaining All About Devin

Use Python 3.9 or newer in this folder. The builder uses the standard library.
The same folder can be hosted at the root of a website or in a subfolder.

## Edit and check an edition

1. Open `edition.json` to find the five groups and the date of this edition.
   Edit the matching page in `content/`. Keep published IDs so saved links work. Use Exchange, Microsoft 365 and Internal Automation / CLI Tools for the three work examples.
2. For a feature or access change, reopen the official sources on that page.
   Change its availability record in `content/facts.json` and record the date
   you checked it. Keep official source links and use made-up practice data.
3. Check that each worked example uses the same task from input to result.
   Add each illustration to `content/figures.json` and link it to its lesson.
   Keep the four book colors in diagrams. Put each needed practice file in
   the Exchange kit folder and update the inventory check if the kit changes.
4. Run `python3 update_edition.py` and then `python3 update_edition.py --check`.
   The build refreshes the practice ZIP, offline file list, portable HTML and
   complete ZIP. The check reports missing or stale files without writing them.
   For a newly unpacked download, run the build once to create its outer ZIP.
5. Open the portable HTML with networking off. Test a search, a diagram,
   a lab and the kit download. Serve this folder with `python3 -m http.server`.
   Open the local address in a browser, wait for “Ready offline”, switch the
   browser offline and reload. Check that the same pages and kit open.
6. Publish the checked folder, including the generated files. Keep the hosted
   reader at the same address so existing bookmarks and lab progress work.

For a completed hands-on review, run
`python3 update_edition.py --review devin-start --note "Checked the training repository walkthrough."`.
Use that command only after carrying out the check. It updates the page,
group and edition dates and records the note in the edition history.

## Practice kit

Read `practice/exchange-inventory/README.md`. On a computer with PowerShell,
open that folder and run
`pwsh -NoProfile -File ./Test-Inventory.ps1 -Script ./Reference/Get-MailboxInventory.ps1`.
The local test uses the bundled CSV. A live mailbox connection is a separate
exercise with its own access requirements.

## Sharing

Share `All-About-Devin.zip` for an editable copy, or `Read All About Devin.html`
for the portable reader. Both contain the full book and the downloadable kit.
Reading progress is kept by the browser on that device.

### Placing a picture

Read the picture and the target paragraph together. A shared picture must explain the same idea and use a case the reader has met. Record the page ID, paragraph field and a short exact excerpt in the picture’s `placements` map. The reader shows the picture beside that passage. The build flags a changed or missing excerpt for review. If a reference page needs a different example, give it its own illustration.
