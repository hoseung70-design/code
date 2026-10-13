# Smoking campaign video

Builds the final campaign video from three scene clips, a narration track and
background music using ffmpeg.

## Layout

```
clips/   scene1.mp4, scene2.mp4, scene3.mp4  (played in this order)
audio/   narration.wav, music.mp3
fonts/   fonts for titles/captions (not used yet)
output/  rendered video (git-ignored)
```

## Render

```bash
./render.sh                      # -> output/campaign.mp4
./render.sh output/draft.mp4     # custom output path
MUSIC_VOL=0.2 CRF=18 ./render.sh # quieter music, higher quality
```

What it does:

- Scales/letterboxes every clip to 1920x1080 at 30 fps and joins them in order.
- Plays the narration over the music; the music ducks automatically while
  narration is speaking.
- Loops the music if it is shorter than the video, cuts all audio to the exact
  video length, and fades out over the last 1.5 s.
- Encodes H.264 + AAC with `+faststart` for web playback.

| Variable    | Default | Meaning                         |
|-------------|---------|---------------------------------|
| `WIDTH`     | 1920    | Output width                    |
| `HEIGHT`    | 1080    | Output height                   |
| `FPS`       | 30      | Output frame rate               |
| `MUSIC_VOL` | 0.35    | Music level before ducking      |
| `CRF`       | 20      | x264 quality (lower = better)   |

Requires ffmpeg/ffprobe (tested with 6.1.1).
