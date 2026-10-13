"""Soundtrack for "The Signature" — low, heavy laser version (original piece).

"지잉~잉": buzzing, pitch-gliding laser tones built from FM + saw/square cores,
driven hard and filtered, all synced to the picture (timeline as index.html).

    python3 synth.py  ->  signature.wav (48 kHz, 16-bit, stereo, 8 s)

    0.50–1.70  the pen: a laser charges up — pitch climbs, buzz thickens, orbits L↔R
    1.70       disc fills: "ZWOOM" — pitch dives into a sub hit, then the beam hums ("잉~")
    1.75–2.55  ring lettering: a whirling high laser sweep
    2.20/2.60  shield: two heavy laser blasts (falling chirps)
    2.90 + i·0.28  each Korean syllable: a short laser "zing"
    4.15 + j·0.06  English letters: tiny zaps
    4.60–5.60  the hum charges up an octave, D1 → D2 ("지이이잉")
    5.60       big blast "ZWAAANG" + sub, then the beam rings out and dies
"""
import math
import wave
import numpy as np

SR, DUR = 48000, 8.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(404)

PEN0, PEN1, RING0, RING1 = .5, 1.7, 1.75, 2.55
SH0, KR0, KR_STEP, EN0, EN_STEP, FINAL = 2.2, 2.9, .28, 4.15, .06, 5.6

L = np.zeros(N); R = np.zeros(N)
SL = np.zeros(N); SR_ = np.zeros(N)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(sig, start, gain=1., pan=0., verb=.3):
    i0 = int(start * SR)
    seg = sig[: N - i0] * gain
    if np.ndim(pan):
        p = np.asarray(pan)[: len(seg)]
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


def lp(cut, q=0.):
    def g(tc, f):
        c = cut(tc) if callable(cut) else cut
        return (1 + q * np.exp(-((f - c) / (.2 * c + 1)) ** 2)) / np.sqrt(1 + (f / c) ** 6)
    return g


def laser(freq, cut, drive=3.0, fm=2.5, q=1.5):
    """freq: per-sample Hz array. Saw + square + FM sine, resonant low-pass, hard drive."""
    ph = np.cumsum(freq) / SR
    saw = 2 * (ph % 1) - 1
    sq = np.sign(np.sin(2 * np.pi * ph * 1.002))
    fmv = np.sin(2 * np.pi * ph + fm * np.sin(2 * np.pi * ph * 2.01))
    s = .6 * saw + .35 * sq + .5 * fmv
    s = stft_filter(s, lp(cut, q))
    return np.tanh(drive * s / (np.max(np.abs(s)) + 1e-9))


def sub_hit(d=2.5, f0=110, f1=30, dec=1.0):
    x = tt(d)
    f = f1 + (f0 - f1) * np.exp(-x / .08)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / dec)
    return np.tanh(2 * s) / np.tanh(2) * np.minimum(1, x / .003)


def chirp(d, f0, f1, curve=3.0):
    u = tt(d) / d
    return f1 + (f0 - f1) * np.exp(-u * curve)


# ---------------------------------------------------------------- pen: charging laser "지이잉"
d = PEN1 - PEN0 + .05
x = tt(d); u = np.clip(x / (PEN1 - PEN0), 0, 1)
f = 24 * 2 ** (2.1 * u ** 1.6) * (1 + .012 * np.sin(2 * np.pi * (5 + 9 * u) * x))      # climbing, wobbling
charge = laser(f, lambda tc: 220 + 2600 * min(1, tc / (PEN1 - PEN0)) ** 2, drive=2.8, fm=4.5)
charge *= u ** 1.3 * np.where(x > PEN1 - PEN0, np.exp(-(x - (PEN1 - PEN0)) / .02), 1)
orbit = np.sin(-math.pi / 2 + 2 * math.pi * (.5 - .5 * np.cos(math.pi * u))) * .8
place(charge, PEN0, .35, orbit, .3)

# ---------------------------------------------------------------- disc fills: ZWOOM + the beam hum "잉~"
d = 1.4
zwoom = laser(chirp(d, 240, 26, 4.0), lambda tc: 2600 * math.exp(-tc / .35) + 180, drive=3.5, fm=4.0)
place(zwoom * np.exp(-tt(d) / .55), PEN1, .55, 0, .35)
place(sub_hit(3.0, 90, 24, 1.3), PEN1, 1.0, 0, .05)

# the beam: a heavy buzzing hum from the disc to the end, charging before the finale
hx = t - PEN1
charge_k = np.clip((t - 4.6) / (FINAL - 4.6), 0, 1)
hum_f = 36.71 * (1 + .006 * np.sin(2 * np.pi * 5.3 * t) + .003 * np.sin(2 * np.pi * .7 * t)) * 2 ** (charge_k ** 2)
after = np.clip((t - FINAL) / 1.6, 0, 1)
hum_f = np.where(t > FINAL, 73.42 * 2 ** (-.25 * after) * (1 + .01 * np.sin(2 * np.pi * 6 * t)), hum_f)   # sags & wobbles
hum = laser(hum_f, lambda tc: 480 + 2600 * min(1, max(0, (tc - 4.6) / (FINAL - 4.6))) ** 2
            + 350 * (1 + math.sin(2 * math.pi * .45 * tc)), drive=3.0, fm=2.0, q=2.0)
hum_env = np.clip(hx / .35, 0, 1) * (hx > 0)
hum_env *= .4 + 1.1 * charge_k ** 1.5 + .2 * (.5 + .5 * np.sin(2 * np.pi * .4 * t))            # slow swells
hum_env *= np.where(t > FINAL, np.exp(-(t - FINAL) / 1.3), 1)
L += .42 * hum * hum_env
R += .42 * hum * hum_env                                              # centred: a delayed copy cancels in mono
SL += .08 * hum * hum_env; SR_ += .08 * hum * hum_env

# ---------------------------------------------------------------- ring lettering: whirling high sweep
d = RING1 - RING0 + .4
x = tt(d)
wf = 420 + 300 * np.sin(2 * np.pi * 2.2 * x) + 380 * x / d
whirl = laser(wf, 3500, drive=2.2, fm=3.0, q=.5)
whirl *= np.clip(x / .15, 0, 1) * np.exp(-np.clip(x - (RING1 - RING0), 0, None) / .15)
place(whirl, RING0, .08, np.sin(2 * np.pi * 1.25 * x) * .9, .5)

# ---------------------------------------------------------------- shield: two laser blasts
for k, at in enumerate((SH0, SH0 + .4)):
    d = .7
    blast = laser(chirp(d, 480 - 80 * k, 38, 5.0), lambda tc: 3000 * math.exp(-tc / .15) + 220, drive=3.2, fm=5.0)
    place(blast * np.exp(-tt(d) / .22), at, .45, (-.3, .3)[k], .35)
    place(sub_hit(1.4, 80, 30, .4), at, .55, 0, .05)

# ---------------------------------------------------------------- Korean syllables: laser "zing" each
steps = [0, 3, 5, 7, 5, 10, 8, 12]                                  # a little rising figure
for i, st in enumerate(steps):
    d = .45
    x = tt(d)
    zf = 110 * 2 ** (st / 12) * (1 + 1.2 * np.exp(-x / .05))          # snaps down into the note
    zing = laser(zf, lambda tc: 2400 * math.exp(-tc / .2) + 350, drive=2.6, fm=2.5, q=1.0)
    place(zing * np.exp(-x / .14), KR0 + i * KR_STEP, .22, -.45 + i * .13, .35)

# ---------------------------------------------------------------- English letters: tiny zaps
for j in range(20):
    d = .09
    zap = np.sin(2 * np.pi * np.cumsum(chirp(d, 1700, 380, 4)) / SR) * np.exp(-tt(d) / .025)
    place(zap, EN0 + j * EN_STEP, .06, -.7 + j * .07, .3)

# ---------------------------------------------------------------- finale: "ZWAAANG"
d = DUR - FINAL
x = tt(d)
bf = 27.5 * (1 + 2.5 * np.exp(-x / .07)) * 2 ** (-.8 * np.clip(x / 2, 0, 1) / 12)
big = np.zeros_like(x)
for mult, g in ((1, 1), (1.5, .55), (2, .7), (3.01, .3)):
    big += g * laser(bf * mult, lambda tc: 100 + 3400 * math.exp(-tc / .45), drive=3.8, fm=3.5, q=1.8)
big *= np.minimum(1, x / .01) * np.exp(-x / 1.5)
place(big, FINAL, .55, 0, .35)
place(sub_hit(d, 70, 20, 2.0), FINAL, 1.0, 0, .05)
crack = stft_filter(rng.standard_normal(len(x)) * np.exp(-x / .25),
                    lambda tc, f: 1 / np.sqrt(1 + (3000 / np.maximum(f, 1)) ** 4))
place(crack, FINAL, .12, 0, .5)

# ---------------------------------------------------------------- reverb (sub kept dry)
ir_n = int(SR * 3.5); ir_t = np.arange(ir_n) / SR
for send, out, s in ((SL, L, 7), (SR_, R, 8)):
    ir = np.random.default_rng(s).standard_normal(ir_n) * np.exp(-ir_t / 1.0)
    ir[: int(.025 * SR)] = 0
    ir = np.convolve(ir, np.ones(7) / 7, mode='same')
    ir /= np.sqrt(np.sum(ir ** 2))
    n = N + ir_n
    wet = np.fft.irfft(np.fft.rfft(send, n) * np.fft.rfft(ir, n), n)[:N]
    out += .8 * stft_filter(wet, lambda tc, f: 1 / np.sqrt(1 + (150 / np.maximum(f, 1)) ** 4))

# ---------------------------------------------------------------- master
mix = np.stack([L, R], 1) * np.clip((DUR - t) / .6, 0, 1)[:, None]
mix /= np.max(np.abs(mix))
mix = np.tanh(1.6 * mix) / np.tanh(1.6)
mix *= .89 / np.max(np.abs(mix))
with wave.open('signature.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('signature.wav', DUR, 's')
