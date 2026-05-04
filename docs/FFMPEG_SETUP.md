# FFmpeg Setup

FFmpeg is required only for real render mode. Mock render mode works without FFmpeg.

## Windows

Options:

```powershell
winget install Gyan.FFmpeg
```

or:

```powershell
choco install ffmpeg
```

After installation:

```powershell
ffmpeg -version
```

If `ffmpeg` is not on `PATH`, set:

```env
FFMPEG_BINARY=C:\path\to\ffmpeg.exe
```

## Linux

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install ffmpeg
ffmpeg -version
```

## macOS

```bash
brew install ffmpeg
ffmpeg -version
```

## RaatVerse Config

```env
VIDEO_RENDERER=ffmpeg
FFMPEG_BINARY=ffmpeg
RENDER_OUTPUT_DIR=./outputs/renders
RENDER_WIDTH=1080
RENDER_HEIGHT=1920
RENDER_FPS=30
```
