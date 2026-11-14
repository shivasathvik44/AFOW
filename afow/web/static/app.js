const pathInput = document.getElementById("path");
const resultBox = document.getElementById("result");
const resultTitle = document.getElementById("result-title");
const resultMeta = document.getElementById("result-meta");
const resultBody = document.querySelector("#result-table tbody");
const resultHint = document.getElementById("result-hint");
const errorBox = document.getElementById("error");
const buttons = document.querySelectorAll(".btn");
const quickFoldersBox = document.getElementById("quick-folders");

async function initSystemInfo() {
  try {
    const res = await fetch("/api/system-info");
    if (!res.ok) return;
    const data = await res.json();
    if (data.placeholder) {
      pathInput.placeholder = data.placeholder;
    }
    if (data.default_path && !pathInput.value) {
      pathInput.value = data.default_path;
    }
    if (data.common_folders && data.common_folders.length > 0 && quickFoldersBox) {
      quickFoldersBox.innerHTML = "";
      data.common_folders.forEach((folder) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = folder.label;
        chip.title = folder.path;
        chip.addEventListener("click", () => {
          pathInput.value = folder.path;
        });
        quickFoldersBox.appendChild(chip);
      });
      quickFoldersBox.classList.remove("hidden");
    }
  } catch (err) {
    // Graceful degradation
  }
}

initSystemInfo();

function setBusy(busy) {
  buttons.forEach((b) => (b.disabled = busy));
}

function showError(msg) {
  resultBox.classList.add("hidden");
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function renderSummary(action, data, elapsedMs) {
  errorBox.classList.add("hidden");
  resultBox.classList.remove("hidden");

  const verb =
    action === "preview" ? "Would move" : action === "undo" ? "Restored" : "Moved";
  resultTitle.textContent = `${verb} ${data.moved} file(s)`;
  resultMeta.textContent = `${data.root} — ${elapsedMs.toFixed(0)} ms`;

  resultBody.innerHTML = "";
  const cats = data.by_category || {};
  const rows = Object.entries(cats).sort((a, b) => b[1] - a[1]);
  for (const [cat, count] of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${cat}</td><td>${count}</td>`;
    resultBody.appendChild(tr);
  }

  if (action === "organize" && data.moved > 0) {
    resultHint.textContent = "Click Undo to reverse this operation.";
  } else if (action === "preview") {
    resultHint.textContent = "Preview only — no files were moved.";
  } else {
    resultHint.textContent = "";
  }
}

async function call(action) {
  const path = pathInput.value.trim();
  if (!path) {
    showError("Enter a folder path first.");
    return;
  }
  setBusy(true);
  const start = performance.now();
  try {
    const res = await fetch(`/api/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.error || `HTTP ${res.status}`);
      return;
    }
    renderSummary(action, data, performance.now() - start);
  } catch (err) {
    showError(err.message || String(err));
  } finally {
    setBusy(false);
  }
}

document.getElementById("preview").addEventListener("click", () => call("preview"));
document.getElementById("organize").addEventListener("click", () => call("organize"));
document.getElementById("undo").addEventListener("click", () => call("undo"));

pathInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") call("preview");
});
