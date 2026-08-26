(function () {
  const PRESETS = {
    sino: { label: "Sino", type: "sine", notes: [880, 1174.66], gap: 0.09, filter: 4200, decay: 0.35 },
    ping: { label: "Ping", type: "triangle", notes: [1396.91], gap: 0.04, filter: 6000, decay: 0.22 },
    caixa: { label: "Caixa", type: "square", notes: [180], gap: 0.08, filter: 1800, decay: 0.18, noise: true },
    fornada: { label: "Fornada", type: "sine", notes: [392, 493.88, 587.33], gap: 0.11, filter: 2800, decay: 0.45 },
    alerta: { label: "Alerta", type: "sawtooth", notes: [740, 587.33, 740], gap: 0.12, filter: 2200, decay: 0.28 },
    suave: { label: "Suave", type: "triangle", notes: [523.25, 659.25, 783.99], gap: 0.14, filter: 2400, decay: 0.5 }
  };

  const state = {
    ctx: null,
    master: null,
    compressor: null,
    filter: null,
    analyser: null,
    convolver: null,
    wet: null,
    dry: null,
    reverbOn: false,
    filterHz: 4200,
    ready: false,
    buffers: {}
  };

  function supported() {
    return !!(window.AudioContext || window.webkitAudioContext);
  }

  async function unlock() {
    if (!supported()) return null;
    if (!state.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      state.ctx = new Ctx();
      buildGraph();
    }
    if (state.ctx.state === "suspended") {
      await state.ctx.resume();
    }
    state.ready = state.ctx.state === "running";
    return state.ctx;
  }

  function buildGraph() {
    const ctx = state.ctx;
    state.master = ctx.createGain();
    state.master.gain.value = 0.8;

    state.compressor = ctx.createDynamicsCompressor();
    state.compressor.threshold.value = -18;
    state.compressor.knee.value = 18;
    state.compressor.ratio.value = 4;
    state.compressor.attack.value = 0.003;
    state.compressor.release.value = 0.18;

    state.filter = ctx.createBiquadFilter();
    state.filter.type = "lowpass";
    state.filter.frequency.value = state.filterHz;
    state.filter.Q.value = 0.7;

    state.analyser = ctx.createAnalyser();
    state.analyser.fftSize = 256;

    state.dry = ctx.createGain();
    state.wet = ctx.createGain();
    state.dry.gain.value = 1;
    state.wet.gain.value = 0;

    state.convolver = ctx.createConvolver();
    state.convolver.buffer = makeImpulse(ctx, 1.1, 1.8);

    state.filter.connect(state.dry);
    state.filter.connect(state.convolver);
    state.convolver.connect(state.wet);
    state.dry.connect(state.compressor);
    state.wet.connect(state.compressor);
    state.compressor.connect(state.master);
    state.master.connect(state.analyser);
    state.analyser.connect(ctx.destination);
  }

  function makeImpulse(ctx, seconds, decay) {
    const rate = ctx.sampleRate;
    const length = Math.floor(rate * seconds);
    const impulse = ctx.createBuffer(2, length, rate);
    for (let ch = 0; ch < 2; ch += 1) {
      const data = impulse.getChannelData(ch);
      for (let i = 0; i < length; i += 1) {
        data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
      }
    }
    return impulse;
  }

  function setVolume(v) {
    if (!state.master) return;
    const now = state.ctx.currentTime;
    state.master.gain.cancelScheduledValues(now);
    state.master.gain.linearRampToValueAtTime(Math.max(0, Math.min(1, v)), now + 0.03);
  }

  function setFilter(hz) {
    state.filterHz = hz;
    if (!state.filter) return;
    state.filter.frequency.setTargetAtTime(hz, state.ctx.currentTime, 0.04);
  }

  function setReverb(on) {
    state.reverbOn = !!on;
    if (!state.wet || !state.dry) return;
    const now = state.ctx.currentTime;
    state.wet.gain.linearRampToValueAtTime(on ? 0.28 : 0, now + 0.05);
    state.dry.gain.linearRampToValueAtTime(on ? 0.85 : 1, now + 0.05);
  }

  function noiseBuffer(duration) {
    const ctx = state.ctx;
    const length = Math.floor(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) data[i] = Math.random() * 2 - 1;
    return buffer;
  }

  function envelope(gain, start, peak, attack, decay) {
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(peak, start + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + attack + decay);
  }

  async function playPreset(name, volume = 0.7) {
    await unlock();
    if (!state.ctx) return;
    setVolume(volume);
    const preset = PRESETS[name] || PRESETS.sino;
    const ctx = state.ctx;
    const now = ctx.currentTime;
    setFilter(preset.filter || state.filterHz);

    preset.notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = preset.type;
      osc.frequency.setValueAtTime(freq, now + i * preset.gap);
      if (preset.type === "sine") {
        osc.frequency.exponentialRampToValueAtTime(freq * 0.97, now + i * preset.gap + preset.decay);
      }
      envelope(gain, now + i * preset.gap, 0.22, 0.012, preset.decay);
      osc.connect(gain);
      gain.connect(state.filter);
      osc.start(now + i * preset.gap);
      osc.stop(now + i * preset.gap + preset.decay + 0.05);
    });

    if (preset.noise) {
      const src = ctx.createBufferSource();
      src.buffer = noiseBuffer(0.16);
      const ng = ctx.createGain();
      const nf = ctx.createBiquadFilter();
      nf.type = "highpass";
      nf.frequency.value = 900;
      envelope(ng, now, 0.18, 0.005, 0.12);
      src.connect(nf);
      nf.connect(ng);
      ng.connect(state.filter);
      src.start(now);
    }
  }

  async function loadDataUrl(key, dataUrl) {
    await unlock();
    const res = await fetch(dataUrl);
    const raw = await res.arrayBuffer();
    const buffer = await state.ctx.decodeAudioData(raw.slice(0));
    state.buffers[key] = buffer;
    return buffer;
  }

  async function playBuffer(key, dataUrl, volume = 0.7) {
    await unlock();
    if (!state.ctx) return;
    setVolume(volume);
    if (!state.buffers[key] && dataUrl) {
      try {
        await loadDataUrl(key, dataUrl);
      } catch {
        return playPreset("ping", volume);
      }
    }
    const buffer = state.buffers[key];
    if (!buffer) return playPreset("ping", volume);
    const src = state.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(state.filter);
    src.start();
  }

  function status() {
    if (!supported()) return { ok: false, text: "Web Audio API não disponível neste navegador" };
    if (!state.ctx) return { ok: true, text: "Contexto ainda não iniciado — clique em Ouvir" };
    return {
      ok: true,
      text: `${state.ctx.state} · ${Math.round(state.ctx.sampleRate / 1000)} kHz · ${state.reverbOn ? "reverb on" : "reverb off"}`
    };
  }

  function drawMeter(canvas) {
    if (!canvas || !state.analyser) return;
    const c = canvas.getContext("2d");
    const data = new Uint8Array(state.analyser.frequencyBinCount);
    state.analyser.getByteFrequencyData(data);
    c.clearRect(0, 0, canvas.width, canvas.height);
    const w = canvas.width / data.length;
    for (let i = 0; i < data.length; i += 1) {
      const h = (data[i] / 255) * canvas.height;
      c.fillStyle = `hsl(${28 + i / 2}, 70%, 48%)`;
      c.fillRect(i * w, canvas.height - h, w - 1, h);
    }
  }

  window.CoelhoAudio = {
    PRESETS,
    supported,
    unlock,
    playPreset,
    playBuffer,
    setVolume,
    setFilter,
    setReverb,
    status,
    drawMeter,
    getState: () => state
  };
})();
