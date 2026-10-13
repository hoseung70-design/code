"""Original intro sting for the INHA sound-intro (not a sample of any existing logo).

Structure: two low hits, then a rising chord swell that opens up to a peak.
Timings must match TIMELINE in index.html.
    python3 synth.py  ->  intro.wav (48 kHz, stereo)
"""
import wave
import numpy as np

SR = 48000
DUR = 6.5
H1, H2 = 0.50, 0.95          # hits
SW0, PEAK = 1.00, 4.50        # swell start / peak
rng = np.random.default_rng(3)
t = np.arange(int(SR * DUR)) / SR
L = np.zeros_like(t)
R = np.zeros_like(t)


def env_at(start, attack, decay):
    x = t - start
    e = np.where(x < 0, 0, np.where(x < attack, x / attack, np.exp(-(x - attack) / decay)))
    return e


def thud(start, f0, f1, decay, gain):
    """Pitch-dropping sine kick + a short filtered click."""
    x = np.clip(t - start, 0, None)
    f = f1 + (f0 - f1) * np.exp(-x / 0.06)
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * env_at(start, 0.004, decay)
    body = np.tanh(body * 1.8) / np.tanh(1.8)                     # warm saturation
    click = rng.standard_normal(len(t)) * env_at(start, 0.001, 0.012)
    click = np.convolve(click, np.ones(24) / 24, mode="same")     # soften
    return gain * (body + 0.35 * click)


kick1 = thud(H1, 140, 48, 0.28, 0.75)
kick2 = thud(H2, 120, 41, 0.5, 1.0) + thud(H2, 240, 82, 0.35, 0.25)
L += kick1 + kick2
R += kick1 + kick2

# --- swell: detuned saw-like chord, brightness opens with a cutoff sweep ---
notes = [36.71, 73.42, 110.0, 146.83, 220.0, 293.66, 369.99, 440.0, 587.33]   # D major add9 spread
x = np.clip((t - SW0) / (PEAK - SW0), 0, 1)
amp = np.where(t < SW0, 0, x ** 1.5)                                           # rise
amp *= np.where(t > PEAK, np.exp(-(t - PEAK) / 0.55), 1)                        # release after peak
cutoff = 180 + 5200 * x ** 2.5                                                  # Hz
for i, f in enumerate(notes):
    for side, detune in ((L, -0.004), (R, 0.004)):
        ff = f * (1 + detune * (1 + i % 3))
        v = np.zeros_like(t)
        for k in range(1, 28):
            fk = ff * k
            if fk > 9000:
                break
            g = 1 / k / (1 + (fk / cutoff) ** 4)                                  # 4-pole-ish low-pass
            v += g * np.sin(2 * np.pi * fk * t + i * k)
        side += 0.13 * amp * v

# shimmer: high sparkle that blooms right before the peak
sh = rng.standard_normal(len(t))
sh = sh - np.convolve(sh, np.ones(6) / 6, mode="same")                         # high-pass-ish
sh_env = np.where((t > 3.2) & (t < PEAK + 1.2),
                  np.clip((t - 3.2) / (PEAK - 3.2), 0, 1) ** 3 * np.exp(-np.clip(t - PEAK, 0, None) / 0.4), 0)
L += 0.05 * sh * sh_env
R += 0.05 * np.roll(sh, 37) * sh_env

# peak accent: a soft sub boom under the climax
boom = thud(PEAK, 90, 38, 0.9, 0.55)
L += boom
R += boom

# --- simple stereo reverb (decaying noise impulse) ---
ir_len = int(SR * 1.6)
ir_t = np.arange(ir_len) / SR
for side, s in ((L, 11), (R, 12)):
    ir = np.random.default_rng(s).standard_normal(ir_len) * np.exp(-ir_t / 0.45)
    ir[0] = 0
    n = len(t) + ir_len
    wet = np.fft.irfft(np.fft.rfft(side, n) * np.fft.rfft(ir, n), n)[: len(t)]
    side += 0.018 * wet

# fade out and normalise
fade = np.clip((DUR - t) / 0.6, 0, 1)
mix = np.stack([L * fade, R * fade], axis=1)
mix /= np.max(np.abs(mix)) * 1.12
pcm = (mix * 32767).astype("<i2")
with wave.open("intro.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("intro.wav", DUR, "s")
