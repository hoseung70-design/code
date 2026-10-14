#!/bin/sh
# Swap the soundtrack for an audio file you have the rights to use.
#   sh replace-audio.sh my-sound.mp3            -> inha-stripe-gate-custom.mp4
#   sh replace-audio.sh my-sound.mp3 0.3        -> shift the audio 0.3 s later
# Hits in the picture: 0.50 s, 0.95 s, peak at 4.50 s. Needs ffmpeg.
set -e
AUDIO="$1"; OFFSET="${2:-0}"
[ -n "$AUDIO" ] || { echo "usage: sh replace-audio.sh <audio file> [offset seconds]"; exit 1; }
ffmpeg -y -i inha-stripe-gate.mp4 -itsoffset "$OFFSET" -i "$AUDIO" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -shortest inha-stripe-gate-custom.mp4
echo "wrote inha-stripe-gate-custom.mp4"
