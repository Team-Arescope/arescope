# InstaBox + Unity Hub: verified command detail

Concrete commands confirmed on the InstaBox XFCE machine (`DISPLAY=:1`, Xvnc on localhost 5901).

## Hub AppImage

```bash
sudo -n mkdir -p /data/unity-hub && sudo -n chown user:user /data/unity-hub
curl -fL --retry 2 -o /data/unity-hub/UnityHub.AppImage \
  https://public-cdn.cloud.unity3d.com/hub/prod/UnityHubSetup-x86_64.AppImage
chmod 755 /data/unity-hub/UnityHub.AppImage
mkdir -p /data/unity-hub/tmp
DISPLAY=:1 TMPDIR=/data/unity-hub/tmp nohup /data/unity-hub/UnityHub.AppImage \
  --appimage-extract-and-run --no-sandbox >/data/unity-hub/hub.log 2>&1 </dev/null &
```

Guest user cannot create top-level dirs under `/data` directly — `sudo -n mkdir` + `chown` first. `--appimage-extract-and-run` replaces the FUSE mount that is absent on minimal images.

## Headless Hub CLI

```bash
DISPLAY=:1 TMPDIR=/data/unity-hub/tmp /data/unity-hub/UnityHub.AppImage \
  --appimage-extract-and-run --no-sandbox -- --headless editors -r
DISPLAY=:1 TMPDIR=/data/unity-hub/tmp /data/unity-hub/UnityHub.AppImage \
  --appimage-extract-and-run --no-sandbox -- --headless install-modules --version 6000.6.7f1 -m android --cm
```

`--headless help` lists the real subcommands. `install-modules` without `--version` fails with "Missing [-v|--version] argument". Without `DISPLAY` the Electron app never returns.

## OAuth callback handler

```bash
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/unityhub.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Unity Hub
Exec=/data/unity-hub/UnityHub.AppImage --appimage-extract-and-run --no-sandbox %u
Terminal=false
MimeType=x-scheme-handler/unityhub;
NoDisplay=true
EOF
xdg-mime default unityhub.desktop x-scheme-handler/unityhub
xdg-mime query default x-scheme-handler/unityhub   # must print unityhub.desktop
```

Without this the browser shows "Failed to open URI. Operation not supported" and the Hub stays on "Signing in...".

## Driving the shared desktop

```bash
DISPLAY=:1 xrandr --output VNC-0 --mode 1280x800
DISPLAY=:1 xwininfo -root -tree | grep Unity     # window ids
DISPLAY=:1 xdotool mousemove X Y click 1
DISPLAY=:1 xdotool mousemove 700 400 click --repeat 900 --delay 1 5   # scroll to end
DISPLAY=:1 scrot /data/unity-hub/shot.png
```

Get button coordinates from a vision pass over the screenshot rather than guessing. `xdotool key ctrl+End` does not scroll the license text; repeated wheel events over the text body do.

## Upload a project

Tarball locally (exclude `Library/ Temp/ Logs/ obj/ .git`), then PUT the raw bytes:

```python
PUT https://api.instabox.sh/v1/machines/<id>/files?path=/data/home/src.tgz&mode=0644
```

Compare the returned `sha256` with the local file. On the machine: unpack into a `chown`ed directory (the build user must write `Library/`), and stage it under `/opt` when the editor runs as a non-root user.

## Disk cleanup on a 20 GB volume

```bash
du -sh /data/home/Unity/Hub/Editor/*/Editor/Data/* | sort -rh | head
sudo -n rm -rf /data/home/Unity/Hub/Editor/*/Editor/Data/PlaybackEngines/WebGLSupport
sudo -n rm -rf /data/home/.config/unityhub/downloads
```

Observed sizes: editor 6000.6.7f1 ≈ 15 GB installed, WebGLSupport ≈ 7 GB, documentation ≈ 1.3 GB, Tools ≈ 1.4 GB.

## Editor launch

```bash
U=/data/home/Unity/Hub/Editor/6000.6.7f1/Editor/Unity
DISPLAY=:1 HOME=/data/home $U -batchmode -nographics -quit \
  -projectPath /opt/arescope-quest -logFile /data/build/import.log
```

`ldd $U` may report a missing `libembree.so.2`; Debian ships `libembree4.so.4`, so install `libembree4-4` and symlink the soname. Headless import segfaulted in `Data/Tools/UnwrapCL` on this setup — the import step was not completed, so the batch build path is unproven; retry with the project-matching editor or run the editor against the virtual display without `-nographics`.
