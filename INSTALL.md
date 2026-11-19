# Install

Written so an agent (Claude Code) can follow it step by step; a person can too.
Each step: run the **command**, then the **check**. Only go on when the check succeeds.
If a check fails, try the **if it fails** advice, then the check again.

- Windows: use **PowerShell** (not Command Prompt).
- macOS: use **Terminal**.
- After installing something on Windows, open a **new** PowerShell window before the check, so the new
  program is on the PATH. (An agent: start a new shell, or refresh PATH with
  `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`.)

---

## Windows 10 / 11

### 1. Git

| | |
| --- | --- |
| check | `git --version` prints a version |
| command | `winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements` |
| if it fails | `winget` missing: install "App Installer" from the Microsoft Store, or download Git from https://git-scm.com/download/win |

### 2. uv (installs Python and the app's packages)

| | |
| --- | --- |
| check | `uv --version` prints a version |
| command | `winget install --id astral-sh.uv -e --source winget --accept-package-agreements --accept-source-agreements` |
| if it fails | use uv's own installer (command below) |

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. GNU Octave (runs the MATLAB code)

| | |
| --- | --- |
| check | `Get-ChildItem "$env:ProgramFiles\GNU Octave", "$env:LOCALAPPDATA\Programs\GNU Octave" -ErrorAction SilentlyContinue` lists an `Octave-<version>` folder |
| command | `winget install --id GNU.Octave -e --source winget --accept-package-agreements --accept-source-agreements` (about 570 MB; takes a few minutes) |
| if it fails | Download the installer from https://octave.org/download (Windows, "octave-<version>-w64-installer.exe") and run it with default options |

The app finds Octave in its standard folders by itself. If it's somewhere else, create a file `.env`
in the repo folder with `OCTAVE=C:\path\to\mingw64\bin\octave-cli.exe`.

### 4. Get the app

The repo is public, so no GitHub account or sign-in is needed.

| | |
| --- | --- |
| command | `cd $HOME\Documents` then `git clone https://github.com/akhmelni/matlab-practice.git` then `cd matlab-practice` |
| check | `Test-Path .\start.bat` prints `True` |

### 5. Python packages

| | |
| --- | --- |
| command | `uv sync` |
| check | the command ends without an error |

### 6. Claude Code (problem creation, reviews and hints)

Skip if Claude Code is already installed and signed in (for example, if an agent is following this file).

| | |
| --- | --- |
| check | `claude --version` prints a version |
| command | `winget install --id Anthropic.ClaudeCode -e --source winget --accept-package-agreements --accept-source-agreements` (or the installer below) |
| then | run `claude` once and sign in with the Claude subscription (`/login`), then exit with `/exit` |

```powershell
irm https://claude.ai/install.ps1 | iex
```

### 7. Check everything

| | |
| --- | --- |
| command | `uv run check-setup` |
| check | the last line says `All required checks passed.` and the Claude Code line says `OK` |
| if it fails | follow the `fix:` line printed under each failed check |

### 8. Start it

Double-click `start.bat` in the repo folder (or run `.\start.bat`). The app opens in the browser at
http://127.0.0.1:8770. Close the black window (or press Ctrl+C in it) to stop the app.

Optional desktop shortcut (PowerShell, from the repo folder):

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\MATLAB Practice.lnk"); $s.TargetPath = (Resolve-Path .\start.bat).Path; $s.WorkingDirectory = (Get-Location).Path; $s.Save()
```

---

## macOS

### 1. Homebrew

| | |
| --- | --- |
| check | `brew --version` prints a version |
| command | follow https://brew.sh (one command in Terminal; it asks for the Mac password) |

### 2. Git, uv and GNU Octave

| | |
| --- | --- |
| command | `brew install git uv octave` (Octave is large; this can take 10+ minutes) |
| check | `git --version && uv --version && octave-cli --version` all print versions |

### 3. Get the app

| | |
| --- | --- |
| command | `cd ~/Documents && git clone https://github.com/akhmelni/matlab-practice.git && cd matlab-practice` |
| check | `ls start.sh` prints `start.sh` |

### 4. Python packages

| | |
| --- | --- |
| command | `uv sync` |
| check | the command ends without an error |

### 5. Claude Code

Skip if already installed and signed in.

| | |
| --- | --- |
| check | `claude --version` prints a version |
| command | the installer below |
| then | run `claude` once and sign in with the Claude subscription (`/login`), then `/exit` |

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### 6. Check everything

| | |
| --- | --- |
| command | `uv run check-setup` |
| check | the last line says `All required checks passed.` and the Claude Code line says `OK` |
| if it fails | follow the `fix:` line printed under each failed check |

### 7. Start it

`./start.sh` (from the repo folder). The app opens at http://127.0.0.1:8770. Ctrl+C stops it.

---

## Updating

From the repo folder: `git pull`, then `uv sync`, then `uv run check-setup --no-claude`.
Your problems, solutions and submissions are in `my-work/`, which updates never touch.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Octave wasn't found" | Install it (step 3), or put `OCTAVE=<full path to octave-cli>` in `.env` |
| Plots don't show | `uv run check-setup` → the Plots line. On Windows, try adding `QT_QPA_PLATFORM=windows` to `.env` |
| "Port 8770 is busy" | The app is already running: open http://127.0.0.1:8770. Or set `PORT=8766` in `.env` |
| "Claude review is off" / "not reviewed" | Run `claude` and sign in (`/login`). Without it the app still works, without reviews and hints |
| Anything else | `uv run check-setup` and read the `fix:` lines |
