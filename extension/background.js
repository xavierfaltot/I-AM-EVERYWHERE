function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i=0; i<bytes.length; i+=chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i+chunk));
  }
  return btoa(binary);
}

async function fetchBinary(url) {
  const r = await fetch(url, {credentials:"omit", cache:"force-cache"});
  if (!r.ok) throw new Error("Fetch failed: " + r.status);
  const mime = r.headers.get("content-type") || "application/octet-stream";
  const buffer = await r.arrayBuffer();
  return {mime, buffer};
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "SWAP_URL") {
    (async () => {
      try {
        const {mime, buffer} = await fetchBinary(msg.url);
        const base64 = arrayBufferToBase64(buffer);
        const swapResponse = await fetch("http://127.0.0.1:8765/swap", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({image_b64:base64, mime})
        });
        if (!swapResponse.ok) {
          const raw = await swapResponse.text();
          let detail = raw;
          try { detail = JSON.parse(raw).error || raw; } catch (_) {}
          throw new Error(detail);
        }
        sendResponse(await swapResponse.json());
      } catch(e) {
        sendResponse({ok:false, error:String(e)});
      }
    })();
    return true;
  }

  if (msg.action === "SWAP_VIDEO_URL") {
    (async () => {
      try {
        if (!msg.url || msg.url.startsWith("blob:")) {
          throw new Error("This video uses a blob/MediaSource stream. V4 direct-video mode cannot fetch it yet.");
        }
        const {mime, buffer} = await fetchBinary(msg.url);
        const maxBytes = 120 * 1024 * 1024;
        if (buffer.byteLength > maxBytes) throw new Error("Video is larger than 120 MB. V4 prototype skips it.");
        const base64 = arrayBufferToBase64(buffer);
        const r = await fetch("http://127.0.0.1:8765/swap-video", {
          method:"POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({video_b64:base64, mime})
        });
        if (!r.ok) {
          const raw = await r.text();
          let detail = raw;
          try { detail = JSON.parse(raw).error || raw; } catch (_) {}
          throw new Error(detail);
        }
        sendResponse(await r.json());
      } catch(e) {
        sendResponse({ok:false, error:String(e)});
      }
    })();
    return true;
  }
});
