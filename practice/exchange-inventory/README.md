# Make a practice mailbox report

Use a computer with PowerShell 7. All the mailboxes in this kit are made up. The practice run reads the CSV file on your computer. It needs no sign-in.

## Give Devin the exercise

Put mailboxes.csv and Test-Inventory.ps1 in a fresh practice project that Devin can open. Ask it to create Get-MailboxInventory.ps1 beside them. The Reference folder holds a finished answer you can use to compare. Read your new script before running it. Open PowerShell in the folder with the sample CSV and run this test.

    ./Test-Inventory.ps1 -Script ./Get-MailboxInventory.ps1

## Try the finished answer

Use a new report file name each time. These commands make a report, show it, and test the script.

    ./Reference/Get-MailboxInventory.ps1 -InputCsv ./mailboxes.csv -OutputCsv ./report.csv
    Import-Csv ./report.csv | Format-Table -AutoSize
    ./Test-Inventory.ps1 -Script ./Reference/Get-MailboxInventory.ps1

Look for four rows sorted by address. Two are user mailboxes and two are shared mailboxes. The test prints five PASS lines. Its last check stands in for the Exchange service, so you can test a broken connection without reaching a real one.

## Run a real report only when you have read access

Devin lab 1 explains the optional live step on an approved work computer. It reads mailbox details and saves a report on that computer. Keep real mailbox data out of the practice project.
