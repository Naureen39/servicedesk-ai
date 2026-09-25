/** VAD's onSpeechEnd already hands us Float32Array samples at 16 kHz mono; the backend's
 * faster-whisper wrapper expects raw little-endian 16-bit PCM at the same rate (Phase 6 item
 * 2: "send 16 kHz mono PCM ... over WS /voice/session"). */
export function float32ToPcm16(samples: Float32Array): ArrayBuffer {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return out.buffer;
}
