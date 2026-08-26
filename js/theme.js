(function () {
  const THEME_KEY = "coelho_theme";
  const SOUND_KEY = "coelho_sound";
  const SOUND_CFG = "coelho_sound_cfg";
  const VALID = ["normal", "claro", "escuro"];

  const DEFAULT_CFG = {
    on: true,
    volume: 0.7,
    cart: "sino",
    order: "fornada",
    customCart: "",
    customOrder: "",
    reverb: false,
    filter: 4200
  };

  function presets() {
    return (window.CoelhoAudio && CoelhoAudio.PRESETS) || {
      sino: { label: "Sino" },
      ping: { label: "Ping" },
      caixa: { label: "Caixa" },
      fornada: { label: "Fornada" },
      alerta: { label: "Alerta" },
      suave: { label: "Suave" }
    };
  }

  function currentTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    return VALID.includes(saved) ? saved : "normal";
  }

  function loadCfg() {
    try {
      return { ...DEFAULT_CFG, ...JSON.parse(localStorage.getItem(SOUND_CFG) || "{}") };
    } catch {
      return { ...DEFAULT_CFG };
    }
  }

  function saveCfg(cfg) {
    localStorage.setItem(SOUND_CFG, JSON.stringify(cfg));
    localStorage.setItem(SOUND_KEY, cfg.on ? "on" : "off");
  }

  function soundOn() {
    return loadCfg().on && localStorage.getItem(SOUND_KEY) !== "off";
  }

  function applyTheme(name) {
    const theme = VALID.includes(name) ? name : "normal";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-theme-btn") === theme);
    });
  }

  function applySoundUi() {
    const cfg = loadCfg();
    const btn = document.getElementById("soundToggle");
    if (btn) {
      btn.textContent = cfg.on ? "Som lig." : "Som desl.";
      btn.setAttribute("aria-pressed", String(cfg.on));
    }
    const vol = document.getElementById("soundVolume");
    if (vol) vol.value = String(Math.round(cfg.volume * 100));
    const volLbl = document.getElementById("soundVolumeLbl");
    if (volLbl) volLbl.textContent = Math.round(cfg.volume * 100) + "%";
    const filt = document.getElementById("soundFilter");
    if (filt) filt.value = String(cfg.filter);
    const filtLbl = document.getElementById("soundFilterLbl");
    if (filtLbl) filtLbl.textContent = cfg.filter + " Hz";
    const rev = document.getElementById("soundReverb");
    if (rev) rev.checked = !!cfg.reverb;
    document.querySelectorAll("[data-sound-for]").forEach((sel) => {
      sel.value = cfg[sel.getAttribute("data-sound-for")] || "sino";
    });
    const st = document.getElementById("audioStatus");
    if (st && window.CoelhoAudio) st.textContent = CoelhoAudio.status().text;
  }

  async function playNotify(kind) {
    const cfg = loadCfg();
    if (!cfg.on || !window.CoelhoAudio) return;
    await CoelhoAudio.unlock();
    CoelhoAudio.setReverb(cfg.reverb);
    CoelhoAudio.setFilter(cfg.filter);
    const slot = kind === "pedido" ? "order" : "cart";
    const custom = slot === "order" ? cfg.customOrder : cfg.customCart;
    if (cfg[slot] === "custom" && custom) {
      await CoelhoAudio.playBuffer(slot, custom, cfg.volume);
      return;
    }
    await CoelhoAudio.playPreset(cfg[slot] || "sino", cfg.volume);
  }

  let meterTimer;
  function startMeter() {
    const canvas = document.getElementById("audioMeter");
    if (!canvas || !window.CoelhoAudio) return;
    cancelAnimationFrame(meterTimer);
    const loop = () => {
      CoelhoAudio.drawMeter(canvas);
      meterTimer = requestAnimationFrame(loop);
    };
    loop();
  }

  function ensurePanel() {
    if (document.getElementById("soundPanel")) return;
    const wrap = document.createElement("div");
    wrap.id = "soundPanel";
    wrap.className = "sound-panel";
    wrap.hidden = true;
    const opts = Object.entries(presets()).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("") +
      `<option value="custom">Meu áudio (Web Audio buffer)</option>`;
    wrap.innerHTML = `
      <div class="sound-card">
        <header>
          <strong>Laboratório Web Audio</strong>
          <button type="button" class="mini" id="soundPanelClose">Fechar</button>
        </header>
        <p class="muted" id="audioStatus" style="font-size:.82rem">Contexto ainda não iniciado</p>
        <canvas id="audioMeter" width="360" height="56" aria-hidden="true"></canvas>
        <label>Volume master <span id="soundVolumeLbl">70%</span></label>
        <input id="soundVolume" type="range" min="0" max="100" value="70" />
        <label>Filtro low-pass <span id="soundFilterLbl">4200 Hz</span></label>
        <input id="soundFilter" type="range" min="400" max="8000" value="4200" />
        <label class="sound-row" style="grid-template-columns:auto 1fr;align-items:center">
          <input id="soundReverb" type="checkbox" />
          <span>Reverb (ConvolverNode)</span>
        </label>
        <label>Som ao adicionar no cesto</label>
        <div class="sound-row">
          <select data-sound-for="cart">${opts}</select>
          <button type="button" class="mini" data-preview="cart">Ouvir</button>
        </div>
        <input type="file" accept="audio/*" data-upload="customCart" />
        <label>Som de pedido novo / confirmado</label>
        <div class="sound-row">
          <select data-sound-for="order">${opts}</select>
          <button type="button" class="mini" data-preview="order">Ouvir</button>
        </div>
        <input type="file" accept="audio/*" data-upload="customOrder" />
        <p class="muted" style="font-size:.82rem">Grafo: Oscillator/Buffer → Filtro → Dry/Wet + Convolver → Compressor → Analyser → Saída. O navegador só libera o AudioContext depois de um clique.</p>
      </div>`;
    document.body.appendChild(wrap);
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      if (!file) return reject(new Error("arquivo"));
      if (file.size > 400 * 1024) return reject(new Error("Arquivo grande demais (máx. 400 KB)"));
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function bindPanel() {
    ensurePanel();
    applySoundUi();
    document.getElementById("soundPanelClose")?.addEventListener("click", () => {
      document.getElementById("soundPanel").hidden = true;
    });
    document.getElementById("soundVolume")?.addEventListener("input", (e) => {
      const cfg = loadCfg();
      cfg.volume = Number(e.target.value) / 100;
      saveCfg(cfg);
      if (window.CoelhoAudio) CoelhoAudio.setVolume(cfg.volume);
      applySoundUi();
    });
    document.getElementById("soundFilter")?.addEventListener("input", (e) => {
      const cfg = loadCfg();
      cfg.filter = Number(e.target.value);
      saveCfg(cfg);
      if (window.CoelhoAudio) CoelhoAudio.setFilter(cfg.filter);
      applySoundUi();
    });
    document.getElementById("soundReverb")?.addEventListener("change", (e) => {
      const cfg = loadCfg();
      cfg.reverb = e.target.checked;
      saveCfg(cfg);
      if (window.CoelhoAudio) CoelhoAudio.setReverb(cfg.reverb);
      applySoundUi();
    });
    document.querySelectorAll("[data-sound-for]").forEach((sel) => {
      sel.addEventListener("change", () => {
        const cfg = loadCfg();
        cfg[sel.getAttribute("data-sound-for")] = sel.value;
        saveCfg(cfg);
      });
    });
    document.querySelectorAll("[data-preview]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const slot = btn.getAttribute("data-preview");
        await playNotify(slot === "order" ? "pedido" : "ok");
        applySoundUi();
        startMeter();
      });
    });
    document.querySelectorAll("[data-upload]").forEach((input) => {
      input.addEventListener("change", async () => {
        try {
          const key = input.getAttribute("data-upload");
          const data = await readFile(input.files[0]);
          const cfg = loadCfg();
          cfg[key] = data;
          cfg[key === "customOrder" ? "order" : "cart"] = "custom";
          saveCfg(cfg);
          applySoundUi();
          await playNotify(key === "customOrder" ? "pedido" : "ok");
          startMeter();
        } catch (err) {
          alert(err.message || "Não foi possível decodificar o áudio");
        }
      });
    });
  }

  function togglePanel() {
    ensurePanel();
    applySoundUi();
    const panel = document.getElementById("soundPanel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      window.CoelhoAudio && CoelhoAudio.unlock().then(() => {
        applySoundUi();
        startMeter();
      });
    }
  }

  function bind() {
    applyTheme(currentTheme());
    applySoundUi();
    document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
      btn.addEventListener("click", () => applyTheme(btn.getAttribute("data-theme-btn")));
    });
    document.getElementById("soundToggle")?.addEventListener("click", async () => {
      const cfg = loadCfg();
      cfg.on = !cfg.on;
      saveCfg(cfg);
      applySoundUi();
      if (cfg.on) await playNotify("ok");
    });
    document.getElementById("soundSettings")?.addEventListener("click", togglePanel);
    document.body.addEventListener("pointerdown", () => {
      window.CoelhoAudio && CoelhoAudio.unlock();
    }, { once: true });
    bindPanel();
  }

  window.CoelhoUI = { applyTheme, playNotify, soundOn, currentTheme };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
