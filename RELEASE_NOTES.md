## 🏠 ESPHome Lights v0.3.7

### What's new

#### Persistent daemon logging
The daemon now writes a rotating log file by default, alongside its existing console output.

- **Default location:** `~/.local/share/esphome-lights/esphome-lightsd.log`
- **Rotation:** 1 MB per file, 3 backups kept (~4 MB total on disk)
- **Command audit log:** every command received over the socket is logged at `INFO` with a structured one-line format — `cmd=set device=living_room action=on → ok: Turned ON`
- **Daemon version** is logged at startup
- **Disable or override** via `ESPHOME_LIGHTS_LOG_FILE`:
  ```
  ESPHOME_LIGHTS_LOG_FILE=none          # disable
  ESPHOME_LIGHTS_LOG_FILE=/var/log/...  # custom path
  ```

#### Installer upgrade and repair modes
`install.sh` now handles the full lifecycle of an existing installation:

| Command | Effect |
|---|---|
| `bash install.sh --install` | Explicit install (same as no args) |
| `bash install.sh --upgrade` | `git pull`, stop service, update scripts + packages, restart |
| `bash install.sh --repair` | Stop service, reinstall scripts, recreate venv if missing, restart |
| `bash install.sh` *(existing install detected)* | Interactive menu: Upgrade / Repair / Fresh / Cancel |

- **Health checks** run automatically when an existing install is detected — missing venv, missing service file, broken symlinks, `aioesphomeapi` not importable, service in failed state — and the menu defaults to **Repair** if any issue is found
- `--fast` mode auto-selects Upgrade
- `--verbose` shows full output from `git` and `pip` commands (quiet by default)
- The running service is stopped before any script files are overwritten
- `--upgrade` re-executes itself after `git pull` so installer fixes take effect immediately in the same run

#### Multi-target OpenClaw skill installer
The skill installer now supports per-agent workspace targeting with a multi-select menu:

```
  Where should the ESPHome Lights skill be installed?
  (multiple choices allowed, e.g:  g   or   1 2   or   g 2)

  [g] Global — ~/.openclaw/skills/  (available to all agents)  [default]
  [1] Agent  — ~/.openclaw/workspace/skills/
  [2] Agent  — ~/.openclaw/workspace-layla/skills/
  [o] Other  — enter a custom path
  [n] Skip
```

- Workspaces are discovered automatically from `~/.openclaw/workspace*/`
- On `--upgrade` and `--repair`, existing skill links are refreshed silently with no prompt

### Fixes

- **SKILL.md PATH fix:** agents now invoke the shell wrapper via full skill-dir path (`bash $SKILL_DIR/esphome-lights`) instead of relying on `PATH` — fixes OpenClaw agents falling back to the slower Python CLI
- **Installer symlink reliability:** all `ln -sf` calls changed to `ln -sfn`, preventing `ln` from following existing symlink-to-directory targets and accidentally overwriting the shell wrapper
- **Installer cp conflict:** `_install_scripts()` now defensively removes stale directories before copying, fixing `cp: cannot overwrite directory` errors during upgrade
- **Installer self-update:** `--upgrade` re-executes itself after `git pull` so that fixes to `install.sh` itself take effect in the same run (previously the old in-memory script continued running)
- **ASCII-only output:** replaced Unicode characters (em dashes, arrows, crosses) with ASCII equivalents in all user-visible installer output — fixes garbled rendering on terminals with limited locale/font support
- **Quiet git output:** `git pull` and `git clone` no longer print object-count noise by default; use `--verbose` to restore full output
- **Clean uninstall output:** `systemctl --user disable` no longer prints the "Removed ..." path line during uninstall
- **ASCII-only daemon and CLI output:** replaced Unicode ellipsis, arrows, and em dashes in daemon log messages and CLI error messages with ASCII equivalents — fixes garbled `_` characters in journalctl and on terminals with limited locale support
- **Installer post-install info:** log file location and `ESPHOME_LIGHTS_LOG_FILE` config hint now shown in the "Next steps" output after install
- **Test fix:** `test_oserror_on_dir_creation` no longer creates a stale `d:\no_such_root` directory on Windows (now mocks `os.makedirs`)

### Upgrade from v0.2.x or v0.3.0
```bash
cd /path/to/ESPHome-Lights
bash install.sh --upgrade
```
Or, if installed via the one-liner, run `bash install.sh --upgrade` from the install directory at `~/.local/lib/esphome-lights/`.
