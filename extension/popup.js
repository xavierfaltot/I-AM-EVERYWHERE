const $ = s => document.querySelector(s);
const status = $("#status");
const preview = $("#preview");
const empty = $("#empty");
const count = $("#count");
const prev = $("#prev");
const next = $("#next");
const remove = $("#remove");
let faces = [];
let activeIndex = 0;
const say = t => status.textContent = t;

async function bridge(path, options={}) {
  const r = await fetch("http://127.0.0.1:8765" + path, options);
  if (!r.ok) {
    const raw = await r.text();
    try { const parsed = JSON.parse(raw); throw new Error(parsed.error || raw); }
    catch(e) { if (e instanceof SyntaxError) throw new Error(raw); throw e; }
  }
  return r.json();
}

async function saveLibrary() {
  await chrome.storage.local.set({sourceFaces: faces, activeFaceIndex: activeIndex});
}

function render() {
  const hasFaces = faces.length > 0;
  if (!hasFaces) {
    preview.style.display = "none";
    preview.removeAttribute("src");
    empty.style.display = "flex";
    count.textContent = "0 FACES";
    prev.disabled = true;
    next.disabled = true;
    remove.disabled = true;
    return;
  }
  if (activeIndex < 0) activeIndex = 0;
  if (activeIndex >= faces.length) activeIndex = faces.length - 1;
  preview.src = faces[activeIndex];
  preview.style.display = "block";
  empty.style.display = "none";
  count.textContent = `${activeIndex + 1} / ${faces.length} FACE${faces.length === 1 ? "" : "S"}`;
  prev.disabled = faces.length < 2;
  next.disabled = faces.length < 2;
  remove.disabled = false;
}

async function activateCurrentFace(showMessage=true) {
  if (!faces.length) throw new Error("ADD A FACE first.");
  const res = await bridge("/source", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({data_url: faces[activeIndex]})
  });
  await saveLibrary();
  if (showMessage) say(`FACE ${activeIndex + 1}/${faces.length} ACTIVE\n${res.message || ""}`);
  return res;
}

async function selectIndex(index) {
  if (!faces.length) return;
  activeIndex = (index + faces.length) % faces.length;
  render();
  await saveLibrary();
  try { await activateCurrentFace(false); say(`FACE ${activeIndex + 1}/${faces.length} ACTIVE`); }
  catch(e) { say("Face selected. Bridge offline — it will activate when you press I AM EVERYWHERE."); }
}

chrome.storage.local.get(["sourceFaces", "activeFaceIndex", "sourceFace"], async data => {
  if (Array.isArray(data.sourceFaces) && data.sourceFaces.length) {
    faces = data.sourceFaces;
    activeIndex = Number.isInteger(data.activeFaceIndex) ? data.activeFaceIndex : 0;
  } else if (data.sourceFace) {
    faces = [data.sourceFace];
    activeIndex = 0;
    await saveLibrary();
  }
  render();
  if (faces.length) say(`${faces.length} stored face${faces.length===1?"":"s"}. Select one and go.`);
});

$("#face").addEventListener("change", async () => {
  const files = [...($("#face").files || [])];
  if (!files.length) return;
  say(`Loading ${files.length} face${files.length===1?"":"s"}…`);
  const loaded = await Promise.all(files.map(file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  })));
  faces.push(...loaded);
  activeIndex = faces.length - loaded.length;
  await saveLibrary();
  render();
  try {
    await activateCurrentFace(false);
    say(`${loaded.length} face${loaded.length===1?"":"s"} added.\nFACE ${activeIndex+1}/${faces.length} ACTIVE`);
  } catch(e) {
    say(`${loaded.length} face${loaded.length===1?"":"s"} added.\nBridge offline.`);
  }
  $("#face").value = "";
});

prev.addEventListener("click", () => selectIndex(activeIndex - 1));
next.addEventListener("click", () => selectIndex(activeIndex + 1));
remove.addEventListener("click", async () => {
  if (!faces.length) return;
  faces.splice(activeIndex, 1);
  if (activeIndex >= faces.length) activeIndex = Math.max(0, faces.length - 1);
  await saveLibrary();
  render();
  if (!faces.length) { say("Face library empty."); return; }
  try { await activateCurrentFace(false); say(`Face removed.\nFACE ${activeIndex+1}/${faces.length} ACTIVE`); }
  catch(e) { say("Face removed. Bridge offline."); }
});

async function sendToPage(action) {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  if (!tab?.id) return;
  try { const res = await chrome.tabs.sendMessage(tab.id, {action}); if (res?.message) say(res.message); }
  catch(e) { say("Reload the webpage once, then retry."); }
}

$("#go").onclick = async () => {
  if (!faces.length) { say("ADD A FACE first."); return; }
  try {
    const h = await bridge("/health");
    if (!h.ok) throw new Error("not ready");
    await activateCurrentFace(false);
  } catch(e) {
    say("FaceFusion bridge is OFFLINE or the active face could not be loaded.\nStart START_I_AM_EVERYWHERE.command.");
    return;
  }
  say(`FACE ${activeIndex+1}/${faces.length} → deepfaking webpage…`);
  sendToPage("EVERYWHERE");
};

$("#gone").onclick = () => sendToPage("GONE");
$("#test").onclick = async () => {
  say("Testing…");
  try {
    const h = await bridge("/health");
    say("BRIDGE ONLINE\n" +
      "FaceFusion: " + (h.facefusion_found ? "FOUND" : "NOT FOUND") + "\n" +
      (h.facefusion_path || "") + "\n\n" +
      "PYTHON:\n" + (h.facefusion_python || "NOT FOUND") + "\n" +
      "Python exists: " + (h.python_exists ? "YES" : "NO") + "\n" +
      "Bridge: " + (h.bridge_version || "?") + "\n" +
      `Faces stored: ${faces.length}`);
  } catch(e) { say("BRIDGE OFFLINE\nStart START_I_AM_EVERYWHERE.command"); }
};
