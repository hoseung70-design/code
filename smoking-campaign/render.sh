#!/usr/bin/env bash
# Render the campaign video: concatenate clips, then mix narration over
# background music (music ducks automatically while narration plays).
#
# Usage: ./render.sh [output-file]
# Env overrides: WIDTH HEIGHT FPS MUSIC_VOL CRF
set -euo pipefail

cd "$(dirname "$0")"

OUT="${1:-output/campaign.mp4}"
WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"
FPS="${FPS:-30}"
MUSIC_VOL="${MUSIC_VOL:-0.35}"
CRF="${CRF:-20}"

CLIPS=(clips/scene1.mp4 clips/scene2.mp4 clips/scene3.mp4)
NARRATION=audio/narration.wav
MUSIC=audio/music.mp3

for f in "${CLIPS[@]}" "$NARRATION" "$MUSIC"; do
  [[ -f "$f" ]] || { echo "missing input: $f" >&2; exit 1; }
done
mkdir -p "$(dirname "$OUT")"

# Total video length = sum of clip durations; audio is cut to exactly this.
total=0
for f in "${CLIPS[@]}"; do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  total=$(awk -v a="$total" -v b="$d" 'BEGIN { printf "%.3f", a + b }')
done
fade_start=$(awk -v t="$total" 'BEGIN { s = t - 1.5; printf "%.3f", (s < 0 ? 0 : s) }')

# Normalize every clip to the same size/fps/pixel format so concat works
# even when sources differ; letterbox instead of stretching.
filter=""
for i in "${!CLIPS[@]}"; do
  filter+="[$i:v]scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,"
  filter+="pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=${FPS},format=yuv420p[v$i];"
done
for i in "${!CLIPS[@]}"; do filter+="[v$i]"; done
filter+="concat=n=${#CLIPS[@]}:v=1:a=0[vout];"

n=${#CLIPS[@]}
nar=$n
mus=$((n + 1))
# Narration is padded with silence (so it never ends before the video) and
# split: one copy is heard, the other drives the ducking.
filter+="[$nar:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,asplit=2[nar][key];"
filter+="[$mus:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=${MUSIC_VOL}[bg];"
filter+="[bg][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked];"
filter+="[nar][ducked]amix=inputs=2:duration=longest:normalize=0,atrim=duration=${total},afade=t=out:st=${fade_start}:d=1.5,alimiter=limit=0.95[aout]"

inputs=()
for f in "${CLIPS[@]}"; do inputs+=(-i "$f"); done
# Loop music so it always covers the full video; atrim above ends the audio.
inputs+=(-i "$NARRATION" -stream_loop -1 -i "$MUSIC")

ffmpeg -hide_banner -y "${inputs[@]}" \
  -filter_complex "$filter" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset medium -crf "$CRF" \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "$OUT"

echo "wrote $OUT"
