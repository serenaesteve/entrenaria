const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const strictBtn = document.getElementById("strictBtn");
const examplesBtn = document.getElementById("examplesBtn");
const copyBtn = document.getElementById("copyBtn");
const downloadBtn = document.getElementById("downloadBtn");
const healthEl = document.getElementById("health");

let strictMode = false;
let history = []; 
let lastUserQuestion = ""; 
let lastAssistantAnswer = ""; 

function el(tag, cls) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  return n;
}

function addMessage(role, text, meta) {
  const hint = chat.querySelector(".hint");
  if (hint) hint.remove();

  const row = el("div", `msg ${role}`);
  const avatar = el("div", "avatar");
  avatar.textContent = role === "user" ? "USR" : "AI";

  const bubble = el("div", "bubble");
  bubble.textContent = text;


  if (meta && meta.source) {
    const badge = el("span", "badgeMini");
    badge.textContent = String(meta.source).toUpperCase();
    bubble.appendChild(document.createElement("br"));
    bubble.appendChild(badge);
  }

  if (role === "assistant" && meta && meta.allowAddToKB) {
    const actions = el("div", "kbActions");
    const btnAdd = el("button", "btn tiny");
    btnAdd.textContent = "Añadir a KB";
    btnAdd.addEventListener("click", async () => {
      await addToKB(lastUserQuestion, lastAssistantAnswer, btnAdd);
    });

    const note = el("span", "noteMini");
    note.textContent = "Guarda esta Q/A en kb_extra.jsonl";

    actions.appendChild(btnAdd);
    actions.appendChild(note);
    bubble.appendChild(actions);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;

  return { row, bubble };
}

function setTyping(on) {
  if (on) {
    const m = addMessage("assistant", "…");
    m.bubble.classList.add("typing");
    m.row.dataset.typing = "1";
  } else {
    const t = chat.querySelector('[data-typing="1"]');
    if (t) t.remove();
  }
}

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
}

function pushHistory(role, content) {
  history.push({ role, content });
  if (history.length > 8) history = history.slice(history.length - 8);
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    const data = await res.json();
    if (data.ok) {
      healthEl.textContent = `Estado: OK | KB: sí (${data.kb_items})`;
    } else {
      healthEl.textContent = "Estado: error";
    }
  } catch {
    healthEl.textContent = "Estado: offline";
  }
}

async function addToKB(question, answer, btn) {
  if (!question || !answer) return;

  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "Guardando…";

  try {
    const res = await fetch("/api/kb/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      btn.textContent = "Error";
      setTimeout(() => {
        btn.textContent = old;
        btn.disabled = false;
      }, 900);
      return;
    }
    btn.textContent = "Guardado ✓";
    await refreshHealth();
  } catch {
    btn.textContent = "Error";
  }
}

async function send() {
  const msg = (input.value || "").trim();
  if (!msg) return;

  lastUserQuestion = msg;

  addMessage("user", msg);
  pushHistory("user", msg);

  input.value = "";
  autosize();

  setTyping(true);
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, strict: strictMode, history })
    });

    const data = await res.json().catch(() => ({}));
    setTyping(false);

    if (!res.ok || !data.ok) {
      addMessage("assistant", `Error: ${data.error || res.statusText || "unknown"}`);
      return;
    }

    lastAssistantAnswer = data.answer || "";

    addMessage("assistant", lastAssistantAnswer, {
      source: data.source || "?",
      allowAddToKB: true
    });

    pushHistory("assistant", lastAssistantAnswer);
  } catch (e) {
    setTyping(false);
    addMessage("assistant", `Error: ${String(e)}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function lastAssistantText() {
  const bubbles = Array.from(chat.querySelectorAll(".msg.assistant .bubble"));
  if (!bubbles.length) return "";
  return bubbles[bubbles.length - 1].textContent || "";
}

function downloadChatTxt() {
  const rows = Array.from(chat.querySelectorAll(".msg"));
  const lines = [];
  for (const r of rows) {
    const role = r.classList.contains("user") ? "USR" : "AI";
    const bubble = r.querySelector(".bubble");
    const txt = (bubble ? bubble.textContent : "").trim();
    lines.push(`[${role}] ${txt}`);
    lines.push("");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "chat.txt";
  document.body.appendChild(a);
  a.click();
  a.remove();

  URL.revokeObjectURL(url);
}


sendBtn.addEventListener("click", send);

clearBtn.addEventListener("click", () => {
  chat.innerHTML = `
    <div class="hint">
      Escribe una pregunta y pulsa <b>Enviar</b>. Usa <b>Shift+Enter</b> para salto de línea.
      <div class="hintRow">
        <button id="examplesBtn" class="btn small">Ejemplos</button>
        <span id="health" class="health">Estado: —</span>
      </div>
    </div>`;
  history = [];
  lastUserQuestion = "";
  lastAssistantAnswer = "";
  window.location.reload();
});

strictBtn.addEventListener("click", () => {
  strictMode = !strictMode;
  strictBtn.textContent = `Estricto: ${strictMode ? "ON" : "OFF"}`;
});

examplesBtn.addEventListener("click", () => {
  const examples = [
    "¿Quién es Jose Vicente Carratalá Sanchis?",
    "¿A qué se dedica Jose Vicente Carratalá Sanchis profesionalmente?",
    "¿Qué lenguajes de programación utiliza habitualmente?",
    "¿Qué es Jocarsa para Jose Vicente Carratalá Sanchis?"
  ];
  input.value = examples[Math.floor(Math.random() * examples.length)];
  autosize();
  input.focus();
});

copyBtn.addEventListener("click", async () => {
  const txt = lastAssistantText();
  if (!txt) return;
  try {
    await navigator.clipboard.writeText(txt);
    copyBtn.textContent = "Copiado ✓";
    setTimeout(() => (copyBtn.textContent = "Copiar"), 900);
  } catch {
    input.value = txt;
    autosize();
    input.focus();
  }
});

downloadBtn.addEventListener("click", downloadChatTxt);

input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

autosize();
input.focus();
refreshHealth();



