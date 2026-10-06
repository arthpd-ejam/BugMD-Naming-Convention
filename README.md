# BugMD Video Renamer

A Windows app that renames a folder of video files to the BugMD naming convention.

```
{Task}-{Var}_{Intro}_{Brand}_{Product}_{Channel}_{Format}_{Strategist}_{Editor}_{Script}_{ProjectType}_{TestType}_{PestAngle}_{dd-mm-yyyy}
```

Example: `BM-75415-1_VEO3_BMD_VMS_META_VID-1080x1920_DAV_ART_BigBeautifulSale_Unproven_MICE_25_03-10-2026.mp4`

## Download

Every push builds the app on GitHub Actions. Open the **Actions** tab, pick the latest
**Build Windows app** run, and download the **BugMD-Video-Renamer** artifact. Tagging a
commit `v1.0.0` (etc.) also publishes a zip on the **Releases** page.

Unzip it anywhere and keep `BugMD-Video-Renamer.exe` and `settings.json` together.
Windows SmartScreen may warn the first time because the app isn't code-signed:
click **More info → Run anyway**.

## First launch: Setup

The first time each person opens the app, a **Setup** screen asks for the options in every
dropdown: brands and their products, project types and their test types, channels,
formats, intro styles, strategists and editors. It starts filled with the current
BugMD lists, so edit what's different and click **Save**. Reopen it any time with
**Setup (dropdown lists)...** at the bottom of the window.

Setup is saved per Windows user (in `%APPDATA%\BugMD-Video-Renamer\settings.json`).
The `settings.json` next to the .exe is only the starting point for people who haven't
saved their own setup yet, so a team can share one file to pre-fill everyone's lists.

## How to use

1. Paste the folder path (or click **Browse...**) and press **Load / Refresh**.
   The app lists the videos directly in that folder (not subfolders).
2. Fill in the ClickUp task fields once. They apply to every file.
   Required fields that are still empty have **red labels**. Pest_Angle, Project Type,
   Test Type, Strategist and Intro Style are optional; empty ones are left out of the name
   (pick the blank entry at the top of a dropdown to empty it).
   Click the date box (or the calendar button) to pick a date. **Clear all fields**
   empties every field and resets the date to today.
3. Check the table. Each file gets:
   - **Var**: the first number in the original filename (ignoring the task number,
     resolutions like `1080x1920`, ratios like `9x16`, `1080p`, `4K` and dates).
     Files without a number get the next numbers after the highest one found
     (1, 2, 3... if none have numbers).
   - **Intro**: the Intro Style chosen above.
   - **Format**: read from the video's resolution. Sizes not in the list are flagged orange.

   Double-click Var, Intro or Format to change a single file. Select rows and press
   **Delete** to leave files out.
4. Click **Rename**. If anything is missing or wrong (an empty field, duplicate names,
   a name that already exists), the app tells you exactly what to fix instead.
5. **Undo last rename** restores the original names of the most recent batch.

Typed values are cleaned automatically: spaces at the ends are trimmed, repeated
underscores collapse, leading/trailing underscores are removed, and characters Windows
doesn't allow are dropped. Your last-used field values are remembered (the date always
starts as today).

## Advanced settings

`settings.json` also holds things the Setup screen doesn't show: which fields are
required (`required_fields`), the order of the name (`name_template`), the date format,
and which file extensions count as videos. Edit your own copy in
`%APPDATA%\BugMD-Video-Renamer\` (or the shared one next to the .exe), then restart.

## Development

```
pip install -r requirements-dev.txt
python -m pytest
python main.py
```

Code lives in `renamer/`: `core.py` (naming rules), `media.py` (reads video resolution),
`ops.py` (renaming and undo), `settings.py` (lists and remembered values),
`widgets.py` (calendar and Setup screen), `app.py` (main window).
