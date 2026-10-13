"""Soundtrack for "The Signature" — cosmic / heavy version (original piece).

    python3 synth.py  ->  signature.wav (48 kHz, 16-bit, stereo, 8 s)

Every sound sits on a picture event (timeline shared with index.html):
    0.00→      deep-space drone: 30–40 Hz sub bed, slow-beating dark cluster
    0.50–1.70  the pen: a rising Shepard-like whoosh and harmonic swirl orbiting L↔R
    1.70       disc fills: deep impact + sub drop + metallic ring-out
    1.75–2.55  ring lettering: a spinning metallic resonance
    2.20/2.60  shield: two heavy low hits
    2.90 + i·0.28  each Korean syllable: a dark gong strike (low, inharmonic)
    4.15 + j·0.06  English letters: distant starlight pings
    5.60       finale: a massive braam (detuned brass-like saws), sub drop,
               cosmic shimmer, 7 s cathedral-of-space reverb
"""
import math
import wave
import numpy as np

SR, DUR = 48000, 8.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(1977)

PEN0, PEN1, RING0, RING1 = .5, 1.7, 1.75, 2.55
SH0, KR0, KR_STEP, EN0, EN_STEP, FINAL = 2.2, 2.9, .28, 4.15, .06, 5.6

L = np.zeros(N); R = np.zeros(N)
SL = np.zeros(N); SR_ = np.zeros(N)


def hz(note):
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3,
             'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    return 440 * 2 ** ((names[note[:-1]] + 12 * (int(note[-1]) - 4)) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(sig, start, gain=1., pan=0., verb=.4):
    i0 = int(start * SR)
    seg = sig[: N - i0] * gain
    if np.ndim(pan):                                   # moving pan
        p = pan[: len(seg)]
        l, r = seg * np.sqrt(.5 * (1 - p)), seg * np.sqrt(.5 * (1 + p))
    else:
        l, r = seg * math.sqrt(.5 * (1 - pan)), seg * math.sqrt(.5 * (1 + pan))
    L[i0:i0 + len(seg)] += l; R[i0:i0 + len(seg)] += r
    SL[i0:i0 + len(seg)] += verb * l; SR_[i0:i0 + len(seg)] += verb * r


def stft_filter(x, gain_fn, n=2048, hop=512):
    w = np.hanning(n)
    pad = np.concatenate([np.zeros(n), x, np.zeros(n)])
    out = np.zeros_like(pad)
    f = np.fft.rfftfreq(n, 1 / SR)
    for i in range(0, len(pad) - n, hop):
        tc = (i + n / 2 - n) / SR
        out[i:i + n] += np.fft.irfft(np.fft.rfft(pad[i:i + n] * w) * gain_fn(tc, f), n) * w
    return out[n:n + len(x)] / 1.5


def lp(cut):
    return lambda tc, f: 1 / np.sqrt(1 + (f / (cut(tc) if callable(cut) else cut)) ** 6)


def bp(lo, hi):
    return lambda tc, f: (1 / np.sqrt(1 + ((lo(tc) if callable(lo) else lo) / np.maximum(f, 1)) ** 6)
                          / np.sqrt(1 + (f / (hi(tc) if callable(hi) else hi)) ** 6))


def saw_t(freq, x, ph=0.):
    return 2 * ((freq * x + ph) % 1) - 1


def impact(d=4.0, f0=70, f1=27, dec=1.6):
    x = tt(d)
    f = f1 + (f0 - f1) * np.exp(-x / .12)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / dec)
    s = np.tanh(2.2 * s) / np.tanh(2.2)
    n = rng.standard_normal(len(x)) * np.exp(-x / .25)
    n = stft_filter(np.pad(n, (0, 0)), bp(60, 900))
    return (s + .5 * n) * np.minimum(1, x / .004)


def gong(f, d=4.0, dark=1.0):
    x = tt(d); s = np.zeros_like(x)
    for ratio, amp, dec in ((1, 1, 3.2), (1.52, .7, 2.4), (2.31, .5, 1.6), (3.07, .35, 1.0),
                            (4.12, .2, .6), (5.86, .12, .35)):
        wob = 1 + .002 * np.sin(2 * np.pi * (.7 + ratio) * x)       # shimmering beat
        s += amp * np.sin(2 * np.pi * f * ratio * x * wob) * np.exp(-x / (dec * dark))
    return s * np.minimum(1, x / .006)


def ping(f, d=2.0):
    x = tt(d)
    return (np.sin(2 * np.pi * f * x) + .4 * np.sin(2 * np.pi * f * 2.76 * x)) * np.exp(-x / .5) * np.minimum(1, x / .002)


# ---------------------------------------------------------------- deep-space drone bed
drone_env = np.clip(t / 1.2, 0, 1) * np.clip((DUR - .3 - t) / 2.0, 0, 1)
drone_env *= .55 + .45 * np.clip((t - PEN0) / (FINAL - PEN0), 0, 1)
for f, g in ((hz('E1'), 1.0), (hz('E1') * 1.004, .8), (hz('B1'), .45), (hz('E2') * .997, .35)):
    ph = rng.random() * 6.28
    L += .15 * g * drone_env * np.sin(2 * np.pi * f * t + ph)
    R += .15 * g * drone_env * np.sin(2 * np.pi * f * 1.0015 * t + ph + .4)
# dark cluster pad (filtered saws, slow beating) breathing in and out
cluster = ['E2', 'F2', 'B2', 'C3', 'E3']                          # minor seconds = unease
pad = np.zeros(N)
for i, nte in enumerate(cluster):
    for d in (-.003, 0, .003):
        pad += saw_t(hz(nte) * (1 + d), t, rng.random())
pad = stft_filter(pad, lp(lambda tc: 220 + 900 * np.clip((tc - PEN0) / (FINAL - PEN0), 0, 1) ** 2))
breath = .65 + .35 * np.sin(2 * np.pi * .21 * t - 1.2)
for out, sh in ((L, 0), (R, 977)):
    out += .022 * np.roll(pad, sh) * drone_env * breath
SL += .01 * pad * drone_env; SR_ += .01 * np.roll(pad, 977) * drone_env

# ---------------------------------------------------------------- the pen: Shepard-like rise orbiting the field
seg = PEN1 - PEN0 + .25
x = tt(seg)
k = np.clip(x / (PEN1 - PEN0), 0, 1)
rise = np.zeros_like(x)
for o in range(6):                                                # octave-stacked glides
    f = 55 * 2 ** (o + 1.5 * k)
    w = np.exp(-((np.log2(f) - np.log2(440)) ** 2) / 2.5)         # bell-shaped loudness over pitch
    rise += w * np.sin(2 * np.pi * np.cumsum(f) / SR)
rise *= (k ** 1.5) * np.where(x > PEN1 - PEN0, np.exp(-(x - (PEN1 - PEN0)) / .06), 1)
orbit = np.sin(-math.pi / 2 + 2 * math.pi * (.5 - .5 * np.cos(math.pi * k))) * .8
place(rise, PEN0, .3, orbit, .6)
wh = stft_filter(np.pad(rng.standard_normal(len(x)), (0, 0)) * k ** 2 * (x < PEN1 - PEN0 + .02),
                 bp(lambda tc: 200 + 3000 * min(1, tc / (PEN1 - PEN0)) ** 2,
                    lambda tc: 600 + 7000 * min(1, tc / (PEN1 - PEN0)) ** 2))
place(wh, PEN0, .18, orbit, .5)

# ---------------------------------------------------------------- disc fills: impact + metallic ring-out
place(impact(4.5, 80, 28, 1.8), PEN1, .85, 0, .15)
place(gong(hz('E2'), 5.0, 1.3), PEN1, .22, -.15, .7)

# ring lettering: spinning metallic resonance (pan sweeps around)
d = RING1 - RING0 + 1.0
x = tt(d)
spin = np.zeros_like(x)
for f in (hz('B4'), hz('E5') * 1.01, hz('F5')):
    spin += np.sin(2 * np.pi * f * x + 3 * np.sin(2 * np.pi * 7 * x))
spin *= np.clip(x / .2, 0, 1) * np.exp(-np.clip(x - (RING1 - RING0), 0, None) / .4)
place(spin, RING0, .07, np.sin(2 * np.pi * 1.3 * x) * .9, .8)

# ---------------------------------------------------------------- shield: two heavy hits
place(impact(3.0, 95, 36, .7), SH0, .6, -.1, .12)
place(impact(3.0, 85, 31, .8), SH0 + .4, .7, .1, .12)

# ---------------------------------------------------------------- Korean syllables: dark gong strikes
gong_notes = ['E2', 'G2', 'B2', 'E2', 'C3', 'B2', 'G2', 'E2']
for i, nte in enumerate(gong_notes):
    place(gong(hz(nte), 3.5, .9), KR0 + i * KR_STEP, .20, -.5 + i * .14, .55)
    place(impact(1.5, 70, 40, .3), KR0 + i * KR_STEP, .16, 0, .08)

# ---------------------------------------------------------------- English letters: distant starlight
for j in range(20):
    place(ping(hz('E6') * 2 ** ((j * 5 % 12) / 12)), EN0 + j * EN_STEP, .07, rng.uniform(-.9, .9), .9)

# ---------------------------------------------------------------- finale: braam + sub drop + shimmer
d = DUR - FINAL
x = tt(d)
env_b = np.minimum(1, x / .05) * np.exp(-x / 1.6)
braam = np.zeros_like(x)
for nte, g in (('E1', 1), ('E2', .9), ('B2', .7), ('E3', .5), ('G3', .35)):
    for dt in (-.006, -.002, .002, .006):
        braam += g * saw_t(hz(nte) * (1 + dt), x, rng.random())
braam = stft_filter(braam * env_b, lp(lambda tc: 90 + 1600 * math.exp(-max(tc, 0) / .5)))   # brassy "bwaaam"
braam = np.tanh(1.8 * braam / (np.max(np.abs(braam)) + 1e-9))
place(braam, FINAL, .85, 0, .5)
place(impact(d, 60, 22, 1.8), FINAL, .9, 0, .12)
sh = np.zeros_like(x)
for f in (hz('B5'), hz('E6'), hz('G#6'), hz('B6'), hz('E7')):
    sh += np.sin(2 * np.pi * f * x + rng.random() * 6) * (.5 + .5 * np.sin(2 * np.pi * rng.uniform(3, 7) * x))
sh *= np.minimum(1, x / .6) * np.exp(-x / 1.4)
place(sh, FINAL, .08, 0, 1.0)

# ---------------------------------------------------------------- space reverb (long, dark)
ir_n = int(SR * 7.0); ir_t = np.arange(ir_n) / SR
for send, out, s in ((SL, L, 3), (SR_, R, 4)):
    ir = np.random.default_rng(s).standard_normal(ir_n) * np.exp(-ir_t / 2.0)
    ir[: int(.04 * SR)] = 0
    ir = np.convolve(ir, np.ones(9) / 9, mode='same')
    ir /= np.sqrt(np.sum(ir ** 2))
    n = N + ir_n
    wet = np.fft.irfft(np.fft.rfft(send, n) * np.fft.rfft(ir, n), n)[:N]
    wet = stft_filter(wet, lambda tc, f: 1 / np.sqrt(1 + (120 / np.maximum(f, 1)) ** 4))   # keep the sub dry
    out += .9 * wet

# ---------------------------------------------------------------- master
mix = np.stack([L, R], 1) * np.clip((DUR - t) / .7, 0, 1)[:, None]
mix /= np.max(np.abs(mix))
mix = np.tanh(1.7 * mix) / np.tanh(1.7)
mix *= .89 / np.max(np.abs(mix))
with wave.open('signature.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('signature.wav', DUR, 's')
