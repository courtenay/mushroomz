#!/usr/bin/env python3
"""
Audio to OSC - Listens to microphone and sends audio analysis as OSC messages.

OSC Messages sent:
  /audio/level      - Overall volume (0.0-1.0)
  /audio/bass       - Low frequency energy (0.0-1.0)
  /audio/mid        - Mid frequency energy (0.0-1.0)
  /audio/high       - High frequency energy (0.0-1.0)
  /audio/beat       - Beat detected (1 on beat, 0 otherwise)

Usage:
  python audio_to_osc.py [--osc-ip 127.0.0.1] [--osc-port 8000] [--device ID]
"""

import argparse
import numpy as np
import sounddevice as sd
from pythonosc import udp_client
import time
import sys

# Audio settings
SAMPLE_RATE = 44100
BLOCK_SIZE = 2048  # ~46ms at 44.1kHz

# Frequency band ranges (Hz)
BASS_RANGE = (20, 250)
MID_RANGE = (250, 4000)
HIGH_RANGE = (4000, 16000)

# Beat detection
BEAT_THRESHOLD = 1.5  # Energy must be this many times above average
BEAT_COOLDOWN = 0.1   # Minimum seconds between beats


class AudioAnalyzer:
    def __init__(self, osc_client, sample_rate=SAMPLE_RATE):
        self.osc = osc_client
        self.sample_rate = sample_rate

        # Smoothing (exponential moving average)
        self.smooth_level = 0.0
        self.smooth_bass = 0.0
        self.smooth_mid = 0.0
        self.smooth_high = 0.0
        self.smoothing = 0.3  # 0 = no smoothing, 1 = max smoothing

        # Beat detection state
        self.energy_history = []
        self.last_beat_time = 0

        # Auto-gain
        self.max_level = 0.001  # Avoid division by zero

    def get_band_energy(self, fft_magnitudes, freqs, low_freq, high_freq):
        """Get energy in a frequency band."""
        mask = (freqs >= low_freq) & (freqs <= high_freq)
        if not np.any(mask):
            return 0.0
        return np.mean(fft_magnitudes[mask])

    def detect_beat(self, energy):
        """Simple beat detection based on energy spikes."""
        self.energy_history.append(energy)
        if len(self.energy_history) > 43:  # ~1 second of history
            self.energy_history.pop(0)

        if len(self.energy_history) < 10:
            return False

        avg_energy = np.mean(self.energy_history[:-1])
        current_time = time.time()

        if (energy > avg_energy * BEAT_THRESHOLD and
            current_time - self.last_beat_time > BEAT_COOLDOWN):
            self.last_beat_time = current_time
            return True
        return False

    def process_audio(self, indata, frames, time_info, status):
        """Callback for audio stream."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)

        # Convert to mono if stereo
        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()

        # Calculate RMS level
        rms = np.sqrt(np.mean(audio**2))

        # Auto-gain: track maximum and normalize
        self.max_level = max(self.max_level * 0.9995, rms)  # Slow decay
        level = min(rms / (self.max_level + 0.0001), 1.0)

        # FFT for frequency analysis
        fft = np.fft.rfft(audio)
        fft_magnitudes = np.abs(fft) / len(audio)
        freqs = np.fft.rfftfreq(len(audio), 1.0 / self.sample_rate)

        # Get band energies
        bass = self.get_band_energy(fft_magnitudes, freqs, *BASS_RANGE)
        mid = self.get_band_energy(fft_magnitudes, freqs, *MID_RANGE)
        high = self.get_band_energy(fft_magnitudes, freqs, *HIGH_RANGE)

        # Normalize bands (auto-gain per band would be better, but this is simpler)
        max_band = max(bass, mid, high, 0.0001)
        bass = min(bass / max_band, 1.0)
        mid = min(mid / max_band, 1.0)
        high = min(high / max_band, 1.0)

        # Apply smoothing
        self.smooth_level = self.smooth_level * self.smoothing + level * (1 - self.smoothing)
        self.smooth_bass = self.smooth_bass * self.smoothing + bass * (1 - self.smoothing)
        self.smooth_mid = self.smooth_mid * self.smoothing + mid * (1 - self.smoothing)
        self.smooth_high = self.smooth_high * self.smoothing + high * (1 - self.smoothing)

        # Beat detection
        beat = 1 if self.detect_beat(rms) else 0

        # Send OSC messages - 0.0-1.0 range (LightKey, etc.)
        self.osc.send_message("/audio/level", float(self.smooth_level))
        self.osc.send_message("/audio/bass", float(self.smooth_bass))
        self.osc.send_message("/audio/mid", float(self.smooth_mid))
        self.osc.send_message("/audio/high", float(self.smooth_high))
        self.osc.send_message("/audio/beat", int(beat))

        # Send OSC messages - 0-255 range (QLC+, etc.)
        self.osc.send_message("/qlc/level", int(self.smooth_level * 255))
        self.osc.send_message("/qlc/bass", int(self.smooth_bass * 255))
        self.osc.send_message("/qlc/mid", int(self.smooth_mid * 255))
        self.osc.send_message("/qlc/high", int(self.smooth_high * 255))
        self.osc.send_message("/qlc/beat", int(beat * 255))

        # LightKey specific
        self.osc.send_message("/live/Control_Panel/cue/osc_maybe/intensity", float(self.smooth_level))

        # Print visualization
        bar_len = 30
        level_bar = "█" * int(self.smooth_level * bar_len)
        bass_bar = "█" * int(self.smooth_bass * bar_len)
        beat_indicator = " ●" if beat else "  "
        print(f"\rLevel: [{level_bar:<{bar_len}}] Bass: [{bass_bar:<{bar_len}}]{beat_indicator}  ", end="")


def list_devices():
    """List available audio input devices."""
    print("\nAvailable audio input devices:")
    print("-" * 50)
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            default = " (default)" if i == sd.default.device[0] else ""
            print(f"  [{i}] {dev['name']}{default}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Audio to OSC converter")
    parser.add_argument("--osc-ip", default="127.0.0.1", help="OSC target IP (default: 127.0.0.1)")
    parser.add_argument("--osc-port", type=int, default=8000, help="OSC target port (default: 8000)")
    parser.add_argument("--device", type=int, default=None, help="Audio input device ID")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    # Create OSC client
    osc_client = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)
    print(f"Sending OSC to {args.osc_ip}:{args.osc_port}")

    # Create analyzer
    analyzer = AudioAnalyzer(osc_client, SAMPLE_RATE)

    # Show selected device
    device_info = sd.query_devices(args.device, 'input')
    print(f"Using input: {device_info['name']}")
    print("\nOSC addresses: /audio/level, /audio/bass, /audio/mid, /audio/high, /audio/beat")
    print("Press Ctrl+C to stop\n")

    try:
        with sd.InputStream(
            device=args.device,
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            callback=analyzer.process_audio
        ):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopped.")
    except Exception as e:
        print(f"\nError: {e}")
        list_devices()


if __name__ == "__main__":
    main()
