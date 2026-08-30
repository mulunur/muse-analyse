const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectBtn = document.getElementById("selectBtn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const llmSettingsForm = document.getElementById("llmSettingsForm");
const llmProvider = document.getElementById("llmProvider");
const llmApiKey = document.getElementById("llmApiKey");
const llmKeyStatus = document.getElementById("llmKeyStatus");
const llmSettingsStatus = document.getElementById("llmSettingsStatus");

const FEATURE_LABELS = {
  bpm: "Темп (BPM)",
  key: "Тональность",
  scale: "Лад",
  energy: "Энергия",
  danceability: "Танцевальность",
  loudness_ebu128_lufs: "Громкость (LUFS)",
  dynamic_complexity: "Динамика",
  spectral_brightness: "Яркость",
  spectral_centroid_hz: "Спектр. центр (Гц)",
  duration_sec: "Длительность (с)",
  beat_confidence: "Уверенность ритма",
  key_strength: "Сила тональности",
};

const growthState = {
  threadId: null,
};

const providerKeyNames = {
  openai: "openai_key_set",
  claude: "claude_key_set",
  nemotron: "nemotron_key_set",
};

function updateLlmKeyStatus(settings) {
  const provider = llmProvider.value;
  const hasKey = provider === "ollama" || settings[providerKeyNames[provider]];
  llmApiKey.disabled = provider === "ollama";
  llmApiKey.required = provider !== "ollama";
  llmApiKey.placeholder = provider === "ollama" ? "Для Ollama ключ не нужен" : "Введите новый ключ провайдера";
  llmKeyStatus.textContent = provider === "ollama"
    ? "Используется локальный сервер Ollama."
    : hasKey ? "Ключ сохранён. Оставьте поле пустым, чтобы не менять его."
      : "Ключ ещё не настроен.";
}

async function loadLlmSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) throw new Error("Не удалось загрузить настройки");
    const settings = await response.json();
    llmProvider.value = settings.provider;
    updateLlmKeyStatus(settings);
    llmSettingsForm.dataset.settings = JSON.stringify(settings);
  } catch (err) {
    llmSettingsStatus.textContent = err.message;
    llmSettingsStatus.className = "settings-status error";
  }
}

async function saveLlmSettings(event) {
  event.preventDefault();
  const settings = JSON.parse(llmSettingsForm.dataset.settings || "{}");
  const provider = llmProvider.value;
  const apiKey = llmApiKey.value.trim();
  if (provider !== "ollama" && !apiKey && !settings[providerKeyNames[provider]]) {
    llmSettingsStatus.textContent = "Введите API ключ.";
    llmSettingsStatus.className = "settings-status error";
    return;
  }

  llmSettingsStatus.textContent = "Сохраняю…";
  llmSettingsStatus.className = "settings-status";
  try {
    const response = await fetch("/api/settings/llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось сохранить настройки");
    llmSettingsStatus.textContent = "Настройки сохранены.";
    llmSettingsStatus.className = "settings-status success";
    llmApiKey.value = "";
    await loadLlmSettings();
  } catch (err) {
    llmSettingsStatus.textContent = err.message;
    llmSettingsStatus.className = "settings-status error";
  }
}

function switchWorkspace(name) {
  document.querySelectorAll(".workspace-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === name);
  });
  document.querySelectorAll(".workspace-view").forEach((view) => {
    view.classList.toggle("active", view.id === `${name}-view`);
  });
}

function showStatus(message, type = "loading", target = statusEl) {
  target.className = `status ${type}`;
  target.innerHTML = type === "loading"
    ? `<span class="spinner"></span>${message}`
    : message;
  target.classList.remove("hidden");
}

function hideStatus(target = statusEl) {
  target.classList.add("hidden");
}

function formatValue(key, value) {
  if (value === null || value === undefined) return "—";
  if (key === "key" && typeof value === "string") return value;
  if (key === "scale") return value === "major" ? "мажор" : value === "minor" ? "минор" : value;
  if (typeof value === "number") {
    if (key.includes("confidence") || key.includes("strength") || key === "energy" || key === "danceability" || key === "spectral_brightness") {
      return (value * (value <= 1 ? 100 : 1)).toFixed(value <= 1 ? 0 : 1) + (value <= 1 ? "%" : "");
    }
    return Number.isInteger(value) ? value : value.toFixed(2);
  }
  return String(value);
}

function renderFeatures(features) {
  const grid = document.getElementById("featuresGrid");
  if (!grid) return;
  grid.innerHTML = "";

  const cards = [
    { label: FEATURE_LABELS.bpm, value: features.rhythm?.bpm },
    { label: FEATURE_LABELS.key, value: `${features.tonal?.key || "?"} ${features.tonal?.scale || ""}` },
    { label: FEATURE_LABELS.energy, value: features.energy },
    { label: FEATURE_LABELS.danceability, value: features.tonal?.danceability },
    { label: FEATURE_LABELS.loudness_ebu128_lufs, value: features.dynamics?.loudness_ebu128_lufs },
    { label: FEATURE_LABELS.dynamic_complexity, value: features.dynamics?.dynamic_complexity },
    { label: FEATURE_LABELS.spectral_brightness, value: features.spectral?.spectral_brightness },
    { label: FEATURE_LABELS.spectral_centroid_hz, value: features.spectral?.spectral_centroid_hz },
    { label: FEATURE_LABELS.duration_sec, value: features.duration_sec },
    { label: FEATURE_LABELS.beat_confidence, value: features.rhythm?.beat_confidence },
    { label: FEATURE_LABELS.key_strength, value: features.tonal?.key_strength },
  ];

  cards.forEach(({ label, value }) => {
    const card = document.createElement("div");
    card.className = "feature-card";
    const key = Object.entries(FEATURE_LABELS).find(([, v]) => v === label)?.[0] || "";
    card.innerHTML = `
      <div class="label">${label}</div>
      <div class="value">${formatValue(key, value)}</div>
    `;
    grid.appendChild(card);
  });

  document.getElementById("rawJson").textContent = JSON.stringify(features, null, 2);
}

function renderReview(review) {
  document.getElementById("scoreValue").textContent = review.score ?? "—";

  const sourceMap = {
    openai: `AI-обзор (${review.model || "OpenAI"})`,
    template: "Шаблонный обзор (без API)",
  };
  document.getElementById("reviewSource").textContent = sourceMap[review.source] || review.source;

  const text = review.full_text
    || (review.sections ? Object.values(review.sections).join("\n\n") : "Обзор недоступен");
  document.getElementById("reviewText").textContent = text;
}

async function analyzeFile(file) {
  if (!file) return;

  resultsEl.classList.add("hidden");
  showStatus(`Анализ «${file.name}»… Это может занять до минуты.`);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      const detail = typeof data.detail === "object"
        ? JSON.stringify(data.detail, null, 2)
        : (data.detail || "Ошибка анализа");
      throw new Error(detail);
    }

    hideStatus();
    renderFeatures(data.features);
    renderReview(data.review);
    resultsEl.classList.remove("hidden");
  } catch (err) {
    showStatus(`Ошибка: ${err.message}`, "error");
  }
}

function renderGrowthIdeas(ideas) {
  const ideasGrid = document.getElementById("ideasGrid");
  const ideasPanel = document.getElementById("ideasPanel");

  if (!Array.isArray(ideas) || ideas.length === 0) {
    ideasGrid.innerHTML = "<div class=\"empty-state\">Идеи ещё не сформированы.</div>";
    ideasPanel.classList.remove("hidden");
    return;
  }

  ideasGrid.innerHTML = ideas.map((idea) => `
    <label class="idea-card">
      <input type="checkbox" value="${idea.id || idea.title}" class="idea-checkbox">
      <div class="idea-content">
        <div class="idea-title">${idea.title || "Новая идея"}</div>
        <div class="idea-hook">${idea.hook || idea.summary || "Описание идеи"}</div>
      </div>
    </label>
  `).join("");

  ideasPanel.classList.remove("hidden");
}

function renderGrowthDrafts(drafts) {
  const draftsGrid = document.getElementById("draftsGrid");
  const draftsPanel = document.getElementById("draftsPanel");
  const entries = Object.entries(drafts || {});

  if (!entries.length) {
    draftsGrid.innerHTML = "<div class=\"empty-state\">Черновики пока не созданы.</div>";
    draftsPanel.classList.remove("hidden");
    return;
  }

  draftsGrid.innerHTML = entries.map(([id, text]) => `
    <article class="draft-card">
      <div class="draft-id">Идея ${id.slice(0, 6)}</div>
      <div class="draft-text">${text}</div>
    </article>
  `).join("");

  draftsPanel.classList.remove("hidden");
}

async function startGrowthWorkflow() {
  const file = document.getElementById("growthFileInput").files[0];
  const text = document.getElementById("artistMaterials").value.trim();
  const growthStatus = document.getElementById("growthStatus");

  if (!file) {
    showStatus("Сначала выберите аудиофайл для Growth Copilot.", "error", growthStatus);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  const materials = text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);

  materials.forEach((entry) => formData.append("artist_materials", entry));

  showStatus("Готовлю идеи и стратегию роста для трека…", "loading", growthStatus);

  try {
    const response = await fetch("/api/growth/start", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      const detail = typeof data.detail === "object"
        ? JSON.stringify(data.detail, null, 2)
        : (data.detail || "Не удалось запустить Growth Copilot");
      throw new Error(detail);
    }

    hideStatus(growthStatus);
    growthState.threadId = data.thread_id;
    renderGrowthIdeas(data.content_ideas || []);
    showStatus("Идеи сформированы. Выберите самые сильные и сгенерируйте черновики.", "loading", growthStatus);
    setTimeout(() => hideStatus(growthStatus), 2000);
  } catch (err) {
    showStatus(`Ошибка: ${err.message}`, "error", growthStatus);
  }
}

async function generateGrowthDrafts() {
  if (!growthState.threadId) {
    showStatus("Сначала запустите Growth Copilot для трека.", "error", document.getElementById("growthStatus"));
    return;
  }

  const selected = [...document.querySelectorAll(".idea-checkbox:checked")].map((input) => input.value);
  if (!selected.length) {
    showStatus("Выберите хотя бы одну идею для генерации черновиков.", "error", document.getElementById("growthStatus"));
    return;
  }

  showStatus("Генерирую черновики для выбранных идей…", "loading", document.getElementById("growthStatus"));

  try {
    const response = await fetch("/api/growth/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: growthState.threadId,
        selected_idea_ids: selected,
      }),
    });
    const data = await response.json();

    if (!response.ok) {
      const detail = typeof data.detail === "object"
        ? JSON.stringify(data.detail, null, 2)
        : (data.detail || "Не удалось сгенерировать черновики");
      throw new Error(detail);
    }

    hideStatus(document.getElementById("growthStatus"));
    renderGrowthDrafts(data.drafts || {});
  } catch (err) {
    showStatus(`Ошибка: ${err.message}`, "error", document.getElementById("growthStatus"));
  }
}

// Drag & drop
if (dropZone) {
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    analyzeFile(file);
  });

  dropZone.addEventListener("click", (e) => {
    if (e.target !== selectBtn) fileInput.click();
  });
}

if (selectBtn) {
  selectBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });
}

if (fileInput) {
  fileInput.addEventListener("change", () => {
    analyzeFile(fileInput.files[0]);
    fileInput.value = "";
  });
}

if (document.getElementById("startGrowthBtn")) {
  document.getElementById("startGrowthBtn").addEventListener("click", startGrowthWorkflow);
}

if (document.getElementById("generateDraftsBtn")) {
  document.getElementById("generateDraftsBtn").addEventListener("click", generateGrowthDrafts);
}

document.querySelectorAll(".workspace-tab").forEach((tab) => {
  tab.addEventListener("click", () => switchWorkspace(tab.dataset.view));
});

llmProvider.addEventListener("change", () => {
  const settings = JSON.parse(llmSettingsForm.dataset.settings || "{}");
  updateLlmKeyStatus(settings);
});
llmSettingsForm.addEventListener("submit", saveLlmSettings);
loadLlmSettings();

// Tabs
if (document.querySelectorAll(".tab").length) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab${tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1)}`).classList.add("active");
    });
  });
}

fetch("/api/health")
  .then((r) => r.json())
  .then((data) => {
    if (!data.essentia_available) {
      if (statusEl) {
        showStatus(
          "⚠ Essentia не установлена. Анализ недоступен — см. README для установки.",
          "error"
        );
      }
    }
  })
  .catch(() => {});
