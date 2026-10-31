/**
 * Audio for Muse Voice Transcribe (J4): the API takes RIFF/WAVE, mono 16-bit PCM at 16 or 24 kHz. Browsers record
 * webm/opus (or mp4), so a recording or a picked file is decoded, mixed to mono and resampled to 16 kHz offline, then
 * written as WAV. The WAV is what the backend hashes and keeps as the original.
 */
const RATE = 16000;

export async function toWav16k(blob: Blob): Promise<Blob> {
  const raw = await blob.arrayBuffer();
  const ctx = new AudioContext();
  let decoded: AudioBuffer;
  try { decoded = await ctx.decodeAudioData(raw); } finally { void ctx.close(); }
  const frames = Math.max(1, Math.ceil(decoded.duration * RATE));
  const off = new OfflineAudioContext(1, frames, RATE);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination); // channels are down-mixed to the mono destination
  src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const str = (o: number, s: string) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); out.setUint32(4, 36 + pcm.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true);
  out.setUint32(24, RATE, true); out.setUint32(28, RATE * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
  str(36, "data"); out.setUint32(40, pcm.length * 2, true);
  pcm.forEach((v, i) => out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true));
  return new Blob([out.buffer], { type: "audio/wav" });
}
