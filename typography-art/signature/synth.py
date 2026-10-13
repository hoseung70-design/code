"""Soundtrack for "The Signature" — an original piece, every note placed on a picture event.

    python3 synth.py  ->  signature.wav (48 kHz, 16-bit, stereo, 8 s)

Timeline (must match index.html):
    0.50–1.70  harp arpeggio rising with the pen as it circles the emblem
    1.70       bell bloom as the disc fills; glass shimmer under the ring sweep
    2.20/2.60  two mallet notes for the shield
    2.90 + i·0.28  plucked melody, one note per Korean syllable (8)
    4.15 + j·0.06  soft glass ticks, one per English letter (20)
    5.60       final chord: bells, warm pad, sub — long hall tail
"""
import math
import wave
import numpy as np

SR, DUR = 48000, 8.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(58)

PEN0, PEN1, RING0, RING1 = .5, 1.7, 1.75, 2.55
SH0, KR0, KR_STEP, EN0, EN_STEP, FINAL = 2.2, 2.9, .28, 4.15, .06, 5.6

L = np.zeros(N); R = np.zeros(N)
SL = np.zeros(N); SRv = np.zeros(N)      # reverb sends


def hz(note):                             # 'E4' style → Hz
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3,
             'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    return 440 * 2 ** ((names[note[:-1]] + 12 * (int(note[-1]) - 4)) / 12)


def place(sig, start, gain=1., pan=0., verb=.35):
    i0 = int(start * SR)
    if i0 >= N:
        return
    seg = sig[: N - i0] * gain
    l, r = seg * math.sqrt(.5 * (1 - pan)), seg * math.sqrt(.5 * (1 + pan))
    L[i0:i0 + len(seg)] += l; R[i0:i0 + len(seg)] += r
    SL[i0:i0 + len(seg)] += verb * l; SRv[i0:i0 + len(seg)] += verb * r


def tt(d):
    return np.arange(int(d * SR)) / SR


def pluck(f, d=1.6, bright=1.0):
    x = tt(d); s = np.zeros_like(x)
    for k in range(1, 14):
        fk = f * k * (1 + .0006 * k * k)                       # slight string stiffness
        if fk > 16000: break
        s += np.sin(2 * np.pi * fk * x) * np.exp(-x * (1.2 + 1.9 * k / bright)) / k ** 1.15
    att = np.minimum(1, x / .002)
    return s * att


def bell(f, d=3.5):
    x = tt(d); s = np.zeros_like(x)
    for ratio, amp, dec in ((1, 1, 2.4), (2.0, .55, 1.6), (2.76, .4, 1.1), (5.40, .25, .6), (8.93, .12, .35)):
        s += amp * np.sin(2 * np.pi * f * ratio * x) * np.exp(-x / dec)
    return s * np.minimum(1, x / .003)


def mallet(f, d=1.4):
    x = tt(d)
    s = (np.sin(2 * np.pi * f * x) * np.exp(-x / .55)
         + .35 * np.sin(2 * np.pi * f * 4 * x) * np.exp(-x / .09)
         + .12 * np.sin(2 * np.pi * f * 9.9 * x) * np.exp(-x / .03))
    return s * np.minimum(1, x / .002)


def tick(f, d=.25):
    x = tt(d)
    n = rng.standard_normal(len(x)) * np.exp(-x / .004)
    return .6 * np.sin(2 * np.pi * f * x) * np.exp(-x / .05) + .25 * n


# ---------------------------------------------------------------- pen arpeggio
arp = ['E3', 'B3', 'E4', 'F#4', 'G#4', 'B4', 'D#5', 'E5', 'F#5', 'G#5', 'B5', 'D#6', 'E6']
for k, note in enumerate(arp):
    p = k / (len(arp) - 1)
    u = math.acos(1 - 2 * p) / math.pi                          # invert the pen's sine ease
    at = PEN0 + (PEN1 - PEN0) * u
    pan = math.sin(-math.pi / 2 + 2 * math.pi * p) * .7          # follows the pen around the circle
    place(pluck(hz(note), 1.8, 1.4), at, .32, pan, .45)

# ---------------------------------------------------------------- bloom when the disc fills
sw = np.clip((t - 1.2) / (PEN1 - 1.2), 0, 1) ** 3 * (t < PEN1)  # reversed-swell into the hit
air = rng.standard_normal(N)
air -= np.convolve(air, np.ones(8) / 8, mode='same')
L += .05 * air * sw; R += .05 * np.roll(air, 91) * sw
place(bell(hz('E5'), 3.5), PEN1, .22, -.2, .6)
place(bell(hz('B5'), 3.0), PEN1 + .01, .14, .25, .6)
x = tt(1.8)
place(np.sin(2 * np.pi * hz('E2') * x) * np.exp(-x / .6) * np.minimum(1, x / .01), PEN1, .45, 0, .2)

# glass shimmer under the ring sweep
for i in range(16):
    at = RING0 + (RING1 - RING0) * i / 16
    place(bell(hz(['B6', 'E7', 'G#6', 'D#7'][i % 4]), .9), at, .035, math.sin(i * 1.3) * .8, .7)

# ---------------------------------------------------------------- shield mallets
place(mallet(hz('B2')), SH0, .55, -.1, .35)
place(mallet(hz('E3')), SH0 + .4, .6, .1, .35)

# ---------------------------------------------------------------- melody for 인하공업전문대학
melody = ['E4', 'G#4', 'B4', 'C#5', 'B4', 'E5', 'D#5', 'G#5']
for i, note in enumerate(melody):
    place(pluck(hz(note), 2.0, 1.1), KR0 + i * KR_STEP, .42, -.35 + i * .1, .4)
    place(pluck(hz(note) / 2, 1.2, .7), KR0 + i * KR_STEP, .12, 0, .3)  # soft octave below

# ---------------------------------------------------------------- ticks for INHA TECHNICAL COLLEGE
for j in range(20):
    place(tick(3200 + 140 * (j % 7)), EN0 + j * EN_STEP, .07, -.6 + j * .06, .25)

# ---------------------------------------------------------------- pad: enters with the pen, swells to the final chord
pad_notes = ['E2', 'B2', 'E3', 'G#3', 'D#4', 'F#4']
env_p = np.clip((t - PEN0) / (FINAL - PEN0), 0, 1) ** 1.4
env_p *= np.where(t > FINAL, 1 + .6 * np.exp(-(t - FINAL) / .4), 1) * np.clip((DUR - .2 - t) / 1.8, 0, 1)
for i, note in enumerate(pad_notes):
    f = hz(note)
    for det, side in ((-.0025, L), (.0025, R)):
        ph = rng.random() * 6.28
        v = (np.sin(2 * np.pi * f * (1 + det) * t + ph)
             + .3 * np.sin(2 * np.pi * 2 * f * (1 + det) * t + ph)
             + .1 * np.sin(2 * np.pi * 3 * f * (1 + det) * t))
        trem = 1 + .12 * np.sin(2 * np.pi * (.17 + .05 * i) * t + ph)
        side += .028 * env_p * v * trem

# ---------------------------------------------------------------- final chord
for k, note in enumerate(['E3', 'B3', 'E4', 'G#4', 'D#5', 'F#5', 'B5', 'E6']):
    place(bell(hz(note), 3.2), FINAL + k * .012, .16 / (1 + .1 * k), (k / 7 - .5) * 1.2, .65)
x = tt(2.4)
place(np.sin(2 * np.pi * hz('E1') * 2 * x) * np.exp(-x / .9) * np.minimum(1, x / .02), FINAL, .5, 0, .25)
sh = np.clip((t - FINAL) * 3, 0, 1) * np.exp(-np.clip(t - FINAL, 0, None) / .9)
L += .03 * air * sh; R += .03 * np.roll(air, 211) * sh

# ---------------------------------------------------------------- hall reverb
ir_n = int(SR * 3.0); ir_t = np.arange(ir_n) / SR
for send, out, s in ((SL, L, 1), (SRv, R, 2)):
    ir = np.random.default_rng(s).standard_normal(ir_n) * np.exp(-ir_t / .9)
    ir[: int(.02 * SR)] = 0
    ir = np.convolve(ir, np.ones(5) / 5, mode='same')               # darker tail
    ir /= np.sqrt(np.sum(ir ** 2))
    n = N + ir_n
    out += .55 * np.fft.irfft(np.fft.rfft(send, n) * np.fft.rfft(ir, n), n)[:N]

# ---------------------------------------------------------------- master
mix = np.stack([L, R], 1) * np.clip((DUR - t) / .6, 0, 1)[:, None]
mix /= np.max(np.abs(mix))
mix = np.tanh(1.3 * mix) / np.tanh(1.3)
mix *= .89 / np.max(np.abs(mix))
with wave.open('signature.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('signature.wav', DUR, 's')
