/* ── MYA frontend ─────────────────────────────────────────────────────────── */

const API = "";  // même origine

// ── État ──────────────────────────────────────────────────────────────────────
let history = [];      // [{role, content}]  (contenu brut, sans contexte injecté)
let isStreaming = false;

// ── DOM ───────────────────────────────────────────────────────────────────────
const messagesContainer = document.getElementById("messagesContainer");
const messageInput      = document.getElementById("messageInput");
const sendBtn           = document.getElementById("sendBtn");
const newChatBtn        = document.getElementById("newChatBtn");
const reloadBtn         = document.getElementById("reloadBtn");
const modelBadge        = document.getElementById("modelBadge");
const dataStatus        = document.getElementById("dataStatus");
const dataText          = document.getElementById("dataText");
const scrapeBtn         = document.getElementById("scrapeBtn");
const scrapeStatus      = document.getElementById("scrapeStatus");
const scrapeText        = document.getElementById("scrapeText");
const menuToggle        = document.getElementById("menuToggle");
const sidebar           = document.querySelector(".sidebar");
const overlay           = document.getElementById("sidebarOverlay");
const welcomeScreen     = document.getElementById("welcomeScreen");

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  await loadStats();
  setupInputListeners();
  setupMobileMenu();
  setupHints();
  setupScrape();
})();

// ── Stats API ─────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res = await fetch(`${API}/api/stats`);
    const data = await res.json();

    modelBadge.textContent = data.model;

    if (data.destinations_count > 0) {
      setDataStatus("ok", `${data.destinations_count} destinations`);
    } else {
      setDataStatus("warn", "Aucune donnée — lance le scraper");
    }
  } catch {
    setDataStatus("warn", "Serveur inaccessible");
  }
}

function setDataStatus(type, text) {
  const dot = dataStatus.querySelector(".dot");
  dot.className = `dot dot-${type}`;
  dataText.textContent = text;
}

reloadBtn.addEventListener("click", async () => {
  reloadBtn.disabled = true;
  setDataStatus("loading", "Rechargement…");
  try {
    const res = await fetch(`${API}/api/reload`, { method: "POST" });
    const data = await res.json();
    setDataStatus("ok", `${data.destinations_count} destinations`);
  } catch {
    setDataStatus("warn", "Erreur lors du rechargement");
  } finally {
    reloadBtn.disabled = false;
  }
});

// ── Scraping ──────────────────────────────────────────────────────────────────
function setScrapeStatus(type, text) {
  scrapeStatus.querySelector(".dot").className = `dot dot-${type}`;
  scrapeText.textContent = text;
}

function setupScrape() {
  scrapeBtn.addEventListener("click", async () => {
    scrapeBtn.disabled = true;
    setScrapeStatus("loading", "Démarrage…");

    try {
      const res = await fetch(`${API}/api/scrape`, { method: "POST" });
      const data = await res.json();
      if (data.status === "already_running") {
        setScrapeStatus("loading", "Déjà en cours…");
        pollScrapeStatus();
        return;
      }
      setScrapeStatus("loading", "Scraping en cours…");
      pollScrapeStatus();
    } catch {
      setScrapeStatus("warn", "Erreur au lancement");
      scrapeBtn.disabled = false;
    }
  });
}

function pollScrapeStatus() {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`${API}/api/scrape/status`);
      const data = await res.json();
      if (!data.running) {
        clearInterval(interval);
        scrapeBtn.disabled = false;
        if (data.error) {
          setScrapeStatus("warn", `Erreur : ${data.error.slice(0, 60)}`);
        } else {
          setScrapeStatus("ok", `${data.last_count} destinations`);
          setDataStatus("ok", `${data.last_count} destinations`);
        }
      }
    } catch {
      clearInterval(interval);
      setScrapeStatus("warn", "Connexion perdue");
      scrapeBtn.disabled = false;
    }
  }, 2000);
}

// ── Chat ──────────────────────────────────────────────────────────────────────
async function sendMessage(userText) {
  if (!userText.trim() || isStreaming) return;

  hideWelcome();
  isStreaming = true;
  updateSendBtn();

  // Ajoute le message utilisateur
  history.push({ role: "user", content: userText });
  appendMessage("user", userText);

  // Ajoute le conteneur de la réponse IA
  const { row, contentEl } = appendMessage("assistant", "");
  const cursor = document.createElement("span");
  cursor.className = "streaming-cursor";
  contentEl.appendChild(cursor);

  scrollBottom();

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") continue;

        try {
          const obj = JSON.parse(payload);
          if (obj.error) {
            fullText += `\n\n⚠ Erreur : ${obj.error}`;
          } else if (obj.token) {
            fullText += obj.token;
          }
          // Rendu markdown incrémental
          contentEl.innerHTML = renderMarkdown(fullText);
          contentEl.appendChild(cursor);
          scrollBottom();
        } catch { /* ignore parse errors */ }
      }
    }

    cursor.remove();
    contentEl.innerHTML = renderMarkdown(fullText || "*(pas de réponse)*");
    history.push({ role: "assistant", content: fullText });

  } catch (err) {
    cursor.remove();
    contentEl.innerHTML = renderMarkdown(`⚠ **Erreur de connexion** : ${err.message}`);
  } finally {
    isStreaming = false;
    updateSendBtn();
    scrollBottom();
  }
}

// ── Affichage messages ────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const inner = document.createElement("div");
  inner.className = "message-inner";

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.textContent = role === "user" ? "T" : "✦";

  const content = document.createElement("div");
  content.className = "message-content";
  if (text) content.innerHTML = renderMarkdown(text);

  inner.appendChild(avatar);
  inner.appendChild(content);
  row.appendChild(inner);
  messagesContainer.appendChild(row);

  return { row, contentEl: content };
}

function renderMarkdown(text) {
  return marked.parse(text, {
    breaks: true,
    gfm: true,
  });
}

function scrollBottom() {
  messagesContainer.scrollTo({
    top: messagesContainer.scrollHeight,
    behavior: "smooth",
  });
}

function hideWelcome() {
  if (welcomeScreen) {
    welcomeScreen.style.display = "none";
  }
}

// ── Input ─────────────────────────────────────────────────────────────────────
function setupInputListeners() {
  messageInput.addEventListener("input", () => {
    // Auto-resize
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + "px";
    // Active le bouton
    sendBtn.disabled = !messageInput.value.trim() || isStreaming;
  });

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitInput();
    }
  });

  sendBtn.addEventListener("click", submitInput);
}

function submitInput() {
  const text = messageInput.value.trim();
  if (!text || isStreaming) return;
  messageInput.value = "";
  messageInput.style.height = "auto";
  sendBtn.disabled = true;
  sendMessage(text);
}

function updateSendBtn() {
  sendBtn.disabled = isStreaming || !messageInput.value.trim();
  sendBtn.innerHTML = isStreaming
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;
}

// ── Nouvelle conversation ─────────────────────────────────────────────────────
newChatBtn.addEventListener("click", () => {
  history = [];
  messagesContainer.innerHTML = "";
  const welcome = document.createElement("div");
  welcome.id = "welcomeScreen";
  welcome.className = "welcome";
  welcome.innerHTML = `
    <div class="welcome-logo"><span class="logo-icon large">✦</span></div>
    <h1>Bonjour, je suis MYA</h1>
    <p>Ton assistant pour explorer les programmes d'échange internationaux d'Epitech. Pose-moi des questions sur les destinations, les universités partenaires, ou les démarches à suivre.</p>
  `;
  messagesContainer.appendChild(welcome);
  messageInput.focus();
  closeMobileMenu();
});

// ── Suggestions ───────────────────────────────────────────────────────────────
function setupHints() {
  document.querySelectorAll(".hint-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const msg = btn.dataset.msg;
      messageInput.value = msg;
      messageInput.dispatchEvent(new Event("input"));
      submitInput();
      closeMobileMenu();
    });
  });
}

// ── Menu mobile ───────────────────────────────────────────────────────────────
function setupMobileMenu() {
  menuToggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("open");
  });
  overlay.addEventListener("click", closeMobileMenu);
}
function closeMobileMenu() {
  sidebar.classList.remove("open");
  overlay.classList.remove("open");
}
