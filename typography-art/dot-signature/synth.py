"""Soundtrack for "Stardust Signature" — an original piece.

Granular stardust over a low, heavy "지~잉" that charges up as the dots gather,
landing in a deep impact with a bell bloom. Timeline shared with index.html.

    python3 synth.py  ->  stardust.wav (48 kHz, 16-bit, stereo, 9 s)

    0.0–1.0   starfield: sparse high twinkles fade in
    1.0–4.4   galaxy swirl: a grain cloud thickens and circles the stereo field;
              a low buzzing drone (D1) climbs toward D2
    1.6–4.4   landings: crystalline "tinks" follow the dots
              (emblem 1.6–2.6, Korean 2.4–3.6, English 3.4–4.4)
    4.4–5.0   the cloud is sucked in (reverse swell)
    5.0       lock: deep sub impact, driven low brass, bell chord, sparkle burst
    5.3–6.4   shine: a shimmer sweeps left → right
    → 9.0     the hum sinks and dies in a long space reverb
"""
import math
import wave
import numpy as np

SR, DUR = 48000, 9.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(8250)
LOCK = 5.0

L = np.zeros(N); R = np.zeros(N)
SL = np.zeros(N); SR_ = np.zeros(N)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(sig, start, gain=1., pan=0., verb=.35):
    i0 = int(start * SR)
    if i0 >= N or i0 < 0:
        return
    seg = sig[: N - i0] * gain
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


def hz(note):
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3,
             'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    return 440 * 2 ** ((names[note[:-1]] + 12 * (int(note[-1]) - 4)) / 12)


# D major pentatonic, high octaves — every grain is in key
PENTA = [hz(n + o) for o in '5678' for n in ('D', 'E', 'F#', 'A', 'B')]


def grain(f, d):
    x = tt(d)
    return np.sin(2 * np.pi * f * x) * np.sin(np.pi * np.clip(x / d, 0, 1)) ** 2


def tink(f, d=.35):
    x = tt(d)
    return (np.sin(2 * np.pi * f * x) + .3 * np.sin(2 * np.pi * f * 2.76 * x)) * np.exp(-x / .07) * np.minimum(1, x / .001)


# ---------------------------------------------------------------- starfield twinkles + galaxy grain cloud
def density(x):                                                    # grains per second over time
    return np.where(x < 1.0, 25 * x, 25 + 140 * np.clip((x - 1) / 3.4, 0, 1) ** 1.5) * (x < LOCK)


tg = 0.0
while tg < LOCK:
    tg += rng.exponential(1 / max(density(tg), 1))
    if tg >= LOCK:
        break
    f = PENTA[rng.integers(0, len(PENTA) - (5 if tg < 1 else 0))]
    swirl = math.sin(2 * math.pi * (.15 * tg + .03 * tg * tg))     # the cloud circles with the galaxy
    pan = float(np.clip(.8 * swirl + rng.normal(0, .25), -1, 1))
    place(grain(f, rng.uniform(.02, .07)), tg, rng.uniform(.015, .04) * (.5 + .5 * min(1, tg)), pan, .6)

# ---------------------------------------------------------------- landings: tinks following the dots
def land_rate(x):
    em = np.where((x > 1.6) & (x < 2.6), 60, 0)
    kr = np.where((x > 2.4) & (x < 3.6), 55, 0)
    en = np.where((x > 3.4) & (x < 4.4), 50, 0)
    return em + kr + en


tl = 1.6
while tl < 4.4:
    tl += rng.exponential(1 / max(land_rate(tl), 1))
    if tl >= 4.4:
        break
    region = 0 if tl < 2.5 else (1 if tl < 3.5 else 2)
    f = [hz('A4'), hz('D5'), hz('F#5'), hz('A5'), hz('B5'), hz('D6')][rng.integers(0, 6)] * (1, 1.0, 1.5)[region]
    pan = float(np.clip((-.7, -.1, .3)[region] + rng.normal(0, .3), -1, 1))
    place(tink(f), tl, .03, pan, .45)

# soft low pulses when each part completes
for at, f in ((2.6, hz('D2')), (3.6, hz('A1')), (4.4, hz('D2'))):
    x = tt(1.2)
    place(np.sin(2 * np.pi * f * x) * np.exp(-x / .35) * np.minimum(1, x / .01), at, .35, 0, .3)

# ---------------------------------------------------------------- low "지~잉" drone that charges with the gathering
k = np.clip((t - .8) / (LOCK - .8), 0, 1)
f_dr = hz('D1') * 2 ** (k ** 2.2) * (1 + .005 * np.sin(2 * np.pi * 4.8 * t))
f_dr = np.where(t > LOCK, hz('D1') * 2 ** (1 - .35 * np.clip((t - LOCK) / 2.5, 0, 1)) * (1 + .008 * np.sin(2 * np.pi * 5.5 * t)), f_dr)
ph = np.cumsum(f_dr) / SR
core = .6 * (2 * (ph % 1) - 1) + .35 * np.sign(np.sin(2 * np.pi * ph * 1.003)) + .5 * np.sin(2 * np.pi * ph + 2.2 * np.sin(4.02 * np.pi * ph))
core = stft_filter(core, lp(lambda tc: 260 + 2400 * min(1, max(0, (tc - .8) / (LOCK - .8))) ** 2.5, q=1.8))
core = np.tanh(2.8 * core / np.max(np.abs(core)))
env_dr = np.clip((t - .8) / 1.2, 0, 1) * (.35 + .65 * k ** 1.5)
env_dr *= np.where(t > LOCK, .8 * np.exp(-(t - LOCK) / 1.6), 1)
L += .30 * core * env_dr; R += .30 * core * env_dr                  # centred (mono-safe)
SL += .06 * core * env_dr; SR_ += .06 * core * env_dr

# ---------------------------------------------------------------- suck-in before the lock
d = LOCK - 4.4
x = tt(d); u = x / d
suck = stft_filter(rng.standard_normal(len(x)), lambda tc, f: 1 / np.sqrt(1 + ((300 + 6000 * (tc / d) ** 2) / np.maximum(f, 1)) ** 4))
place(suck * u ** 3.5, 4.4, .16, 0, .3)

# ---------------------------------------------------------------- the lock
def sub_hit(d=3.0, f0=95, f1=26, dec=1.4):
    x = tt(d)
    f = f1 + (f0 - f1) * np.exp(-x / .09)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / dec)
    return np.tanh(2.2 * s) / np.tanh(2.2) * np.minimum(1, x / .003)


place(sub_hit(3.5), LOCK, 1.0, 0, .05)
d = 3.0
x = tt(d)
brass = np.zeros_like(x)
for nte, g in (('D1', 1), ('D2', .8), ('A2', .6), ('D3', .4)):
    for dt in (-.006, -.002, .002, .006):
        brass += g * (2 * ((hz(nte) * (1 + dt) * x + rng.random()) % 1) - 1)
brass = stft_filter(brass * np.minimum(1, x / .03) * np.exp(-x / 1.2), lp(lambda tc: 90 + 1500 * math.exp(-max(tc, 0) / .45)))
place(np.tanh(2.2 * brass / np.max(np.abs(brass))), LOCK, .45, 0, .45)


def bell(f, d=4.0):
    x = tt(d); s = np.zeros_like(x)
    for ratio, amp, dec in ((1, 1, 2.6), (2.0, .5, 1.7), (2.76, .35, 1.1), (5.4, .2, .5)):
        s += amp * np.sin(2 * np.pi * f * ratio * x) * np.exp(-x / dec)
    return s * np.minimum(1, x / .003)


for i, nte in enumerate(['D4', 'A4', 'D5', 'E5', 'F#5', 'A5', 'D6']):
    place(bell(hz(nte)), LOCK + i * .015, .07, (i / 6 - .5) * 1.4, .7)
for _ in range(260):                                              # sparkle burst
    at = LOCK + rng.exponential(.25)
    place(grain(PENTA[rng.integers(5, len(PENTA))], rng.uniform(.02, .05)), at, .03, float(rng.uniform(-1, 1)), .7)

# ---------------------------------------------------------------- shine shimmer sweeping L → R
d = 1.1
x = tt(d); u = x / d
sh = sum(np.sin(2 * np.pi * f * x + rng.random() * 6) for f in (hz('A6'), hz('D7'), hz('F#7'))) * np.sin(np.pi * u) ** 2
for i in range(len(sh) // 480):                                   # pan in 10 ms steps
    sl = slice(i * 480, (i + 1) * 480)
    pan = -.9 + 1.8 * (i * 480 / len(sh))
    place(sh[sl], LOCK + .3 + i * .01, .035, pan, .6)

# ---------------------------------------------------------------- long space reverb (sub kept dry)
ir_n = int(SR * 5.0); ir_t = np.arange(ir_n) / SR
for send, out, s in ((SL, L, 31), (SR_, R, 32)):
    ir = np.random.default_rng(s).standard_normal(ir_n) * np.exp(-ir_t / 1.5)
    ir[: int(.03 * SR)] = 0
    ir = np.convolve(ir, np.ones(7) / 7, mode='same')
    ir /= np.sqrt(np.sum(ir ** 2))
    n = N + ir_n
    wet = np.fft.irfft(np.fft.rfft(send, n) * np.fft.rfft(ir, n), n)[:N]
    out += .85 * stft_filter(wet, lambda tc, f: 1 / np.sqrt(1 + (140 / np.maximum(f, 1)) ** 4))

# ---------------------------------------------------------------- master
mix = np.stack([L, R], 1) * np.clip((DUR - t) / .6, 0, 1)[:, None]
mix /= np.max(np.abs(mix))
mix = np.tanh(1.5 * mix) / np.tanh(1.5)
mix *= .89 / np.max(np.abs(mix))
with wave.open('stardust.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('stardust.wav', DUR, 's')
