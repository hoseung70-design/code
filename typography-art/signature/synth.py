"""Heavy streaming-style sting for "The Signature" — an original composition.

Streaming-service-style structure (two heavy tonal booms → wide swell → bloom),
but its own notes and sound design; it does not copy any existing sound logo.
Timings must match the timeline in index.html.

    python3 synth.py  ->  intro.wav (48 kHz, 16-bit, stereo)
"""
import wave
import numpy as np

SR = 48000
DUR = 8.0
H1, H2 = 1.25, 1.70            # the two booms (2nd lands as the disc fills)
SW0, PEAK = 1.80, 5.60          # swell start / bloom on the final shine
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(2024)


# ---------------------------------------------------------------- helpers
def env(start, attack, decay, hold=0.0):
    x = t - start
    e = np.where(x < 0, 0.0, np.where(x < attack, x / attack, 1.0))
    return e * np.exp(-np.clip(x - attack - hold, 0, None) / decay)


def stft_filter(x, gain_fn, n=2048, hop=512):
    """Time-varying EQ: gain_fn(time_s, freqs_hz) -> per-bin gain."""
    w = np.hanning(n)
    pad = np.concatenate([np.zeros(n), x, np.zeros(n)])
    out = np.zeros_like(pad)
    f = np.fft.rfftfreq(n, 1 / SR)
    for i in range(0, len(pad) - n, hop):
        tc = (i + n / 2 - n) / SR
        X = np.fft.rfft(pad[i:i + n] * w)
        out[i:i + n] += np.fft.irfft(X * gain_fn(tc, f), n) * w
    return out[n:n + len(x)] / 1.5          # hann² overlap at hop=n/4


def lowpass(cut, q=0.0):
    def g(tc, f):
        c = cut(tc) if callable(cut) else cut
        res = 1 + q * np.exp(-((f - c) / (0.25 * c + 1)) ** 2)      # resonant bump
        return res / np.sqrt(1 + (f / c) ** 8)
    return g


def band(lo, hi):
    def g(tc, f):
        a = lo(tc) if callable(lo) else lo
        b = hi(tc) if callable(hi) else hi
        return 1 / np.sqrt(1 + (a / np.maximum(f, 1)) ** 6) / np.sqrt(1 + (f / b) ** 6)
    return g


def saw(freq, phase0=0.0):
    return 2 * ((freq * t + phase0) % 1.0) - 1


def noise():
    return rng.standard_normal(N)


L = np.zeros(N)
R = np.zeros(N)
send = np.zeros((2, N))          # reverb send bus


def add(sig, gain=1.0, pan=0.0, verb=0.25):
    global L, R
    l, r = gain * sig * np.sqrt(0.5 * (1 - pan)), gain * sig * np.sqrt(0.5 * (1 + pan))
    L += l
    R += r
    send[0] += verb * l
    send[1] += verb * r


# ---------------------------------------------------------------- booms
def boom(start, pitch, decay, weight):
    x = np.clip(t - start, 0, None)
    f = pitch * (1 + 1.6 * np.exp(-x / 0.045))                       # pitch-drop into the note
    ph = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(ph) * env(start, 0.003, decay)
    tone = (0.8 * np.sin(2 * ph) * env(start, 0.003, decay * 0.55)
            + 0.4 * np.sin(3 * ph) * env(start, 0.003, decay * 0.3))
    knock = stft_filter(noise() * env(start, 0.001, 0.07), band(120, 900))
    click = stft_filter(noise() * env(start, 0.0005, 0.006), band(2500, 12000))
    s = np.tanh(1.9 * (sub + tone)) / np.tanh(1.9)
    return weight * (s + 0.9 * knock + 0.3 * click)


add(boom(H1, 49.0, 0.50, 1.5), verb=0.22)                         # first boom  – G1
add(boom(H2, 36.7, 0.85, 1.8), verb=0.28)                         # second boom – D1, longer
add(boom(H2, 18.35, 1.2, 0.6), verb=0.0)                           # sub-octave weight

# low brass-like body under the second boom
brass = sum(saw(73.42 * d, k * .13) for k, d in enumerate((1, 1.003, 0.997)))
brass = stft_filter(brass * env(H2, 0.03, 1.3, hold=0.2), lowpass(380, q=1.3))
add(brass, 0.4, verb=0.3)

# ---------------------------------------------------------------- swell
chord = [36.71, 73.42, 110.00, 146.83, 185.00, 220.00, 329.63, 440.00, 587.33]   # D add9, wide
rise = np.clip((t - SW0) / (PEAK - SW0), 0, 1)
amp = np.where(t < SW0, 0, rise ** 1.7) * np.where(t > PEAK, np.exp(-(t - PEAK) / 0.6), 1)
for side, sgn in ((0, -1), (1, 1)):
    pad = np.zeros(N)
    for i, f in enumerate(chord):
        for v, cents in enumerate((-14, -7, 0, 7, 14)):
            pad += saw(f * 2 ** (sgn * cents / 1200), (i * 7 + v) * 0.071) / (1 + 0.15 * i)
    pad = stft_filter(pad * amp, lowpass(lambda tc: 160 + 8800 * np.clip((tc - SW0) / (PEAK - SW0), 0, 1) ** 2.6, q=0.8))
    (L if side == 0 else R)[:] += 0.13 * pad
    send[side] += 0.06 * pad

# riser: band of noise sweeping up + a pitched whistle
k = lambda tc: np.clip((tc - 3.3) / (PEAK - 3.3), 0, 1)
riser = stft_filter(noise() * np.clip((t - 3.3) / (PEAK - 3.3), 0, 1) ** 2.5 * (t < PEAK),
                    band(lambda tc: 300 + 5000 * k(tc) ** 2, lambda tc: 900 + 9000 * k(tc) ** 2))
add(riser, 0.12, verb=0.3)
x = np.clip((t - 3.7) / (PEAK - 3.7), 0, 1)
whistle = np.sin(2 * np.pi * np.cumsum(330 * 2 ** (2.5 * x)) / SR) * x ** 3 * (t < PEAK)
add(whistle, 0.035, pan=0.3, verb=0.6)

# reverse cymbal into the bloom
rev = stft_filter(noise() * np.clip((t - 4.1) / (PEAK - 4.1), 0, 1) ** 4 * (t < PEAK), band(4000, 16000))
add(rev, 0.10, verb=0.2)

# ---------------------------------------------------------------- bloom at the peak
add(boom(PEAK, 36.7, 0.9, 0.8), verb=0.35)
crash = stft_filter(noise() * env(PEAK, 0.002, 0.8), band(3500, 16000))
add(crash, 0.13, verb=0.35)
for side, sgn in ((0, -1), (1, 1)):
    stab = np.zeros(N)
    for i, f in enumerate(chord[2:] + [880.00, 1174.66]):
        for cents in (-9, 0, 9):
            stab += saw(f * 2 ** (sgn * cents / 1200), i * .11) / (1 + 0.2 * i)
    stab = stft_filter(stab * env(PEAK, 0.01, 1.0), lowpass(lambda tc: 7000 * np.exp(-max(tc - PEAK, 0) / 1.2) + 600))
    (L if side == 0 else R)[:] += 0.1 * stab
    send[side] += 0.025 * stab


# ---------------------------------------------------------------- picture-synced extras
# anticipation: a low rising hum while the pen circles, cut dead at the first boom
x = np.clip((t - 0.4) / (H1 - 0.4), 0, 1)
ant = np.sin(2 * np.pi * np.cumsum(30 + 40 * x ** 2) / SR) * x ** 2 * (t < H1)
ant += stft_filter(noise() * x ** 3 * (t < H1), band(150, 1200)) * .6
add(ant, .35, verb=.2)
# shield + each Korean syllable: soft low taps that ride inside the swell
for at in (2.2, 2.6):
    add(boom(at, 60.0, .25, .25), verb=.2)
for i in range(8):
    add(boom(2.9 + i * .28, 73.4, .18, .12), pan=-.4 + i * .11, verb=.25)

# ---------------------------------------------------------------- reverb (stereo hall)
ir_len = int(SR * 2.8)
ir_t = np.arange(ir_len) / SR
for side, s in ((0, 11), (1, 12)):
    ir = np.random.default_rng(s).standard_normal(ir_len) * np.exp(-ir_t / 0.8)
    ir[: int(0.012 * SR)] = 0                                          # pre-delay
    ir = stft_filter(np.concatenate([ir, np.zeros(N - ir_len)]) if ir_len < N else ir, lowpass(5500))[:ir_len]
    ir /= np.sqrt(np.sum(ir ** 2))                                     # unit energy
    n = N + ir_len
    wet = np.fft.irfft(np.fft.rfft(send[side], n) * np.fft.rfft(ir, n), n)[:N]
    (L if side == 0 else R)[:] += 0.9 * wet

# ---------------------------------------------------------------- master
fade = np.clip((DUR - t) / 0.7, 0, 1)
mix = np.stack([L, R], axis=1) * fade[:, None]
mix /= np.max(np.abs(mix))
mix = np.tanh(1.6 * mix) / np.tanh(1.6)                              # glue / soft clip
mix *= 0.89 / np.max(np.abs(mix))                                    # ≈ -1 dBFS
with wave.open("signature.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("signature.wav", DUR, "s")
