let running = false;
let imageOverlays = [];
let videoOverlays = [];
let processedImages = new WeakSet();
let processedVideos = new WeakSet();

function askBackground(payload) {
  return new Promise(resolve => chrome.runtime.sendMessage(payload, resolve));
}

function removeAll() {
  running = false;
  imageOverlays.forEach(o => o.overlay.remove());
  imageOverlays = [];
  videoOverlays.forEach(item => {
    const {original, overlay, handlers} = item;
    try {
      original.removeEventListener("play", handlers.sync);
      original.removeEventListener("pause", handlers.sync);
      original.removeEventListener("seeking", handlers.sync);
      original.removeEventListener("ratechange", handlers.sync);
      original.removeEventListener("volumechange", handlers.sync);
    } catch (_) {}
    overlay.remove();
  });
  videoOverlays = [];
  processedImages = new WeakSet();
  processedVideos = new WeakSet();
  window.removeEventListener("scroll", updatePositions, true);
  window.removeEventListener("resize", updatePositions, true);
}

function placeOver(element, overlay) {
  const r = element.getBoundingClientRect();
  const cs = getComputedStyle(element);
  overlay.style.left = (window.scrollX + r.left) + "px";
  overlay.style.top = (window.scrollY + r.top) + "px";
  overlay.style.width = r.width + "px";
  overlay.style.height = r.height + "px";
  overlay.style.borderRadius = cs.borderRadius;
  overlay.style.objectFit = cs.objectFit || "cover";
  overlay.style.objectPosition = cs.objectPosition || "50% 50%";
}

function updatePositions() {
  for (const item of imageOverlays) {
    if (item.img.isConnected && item.overlay.isConnected) placeOver(item.img, item.overlay);
  }
  for (const item of videoOverlays) {
    if (item.original.isConnected && item.overlay.isConnected) placeOver(item.original, item.overlay);
  }
}

function commonOverlayStyle(el) {
  Object.assign(el.style, {
    position:"absolute", margin:"0", padding:"0", border:"0",
    pointerEvents:"none", zIndex:"2147483646", display:"block", opacity:"1"
  });
}

function addImageOverlay(img, dataUrl) {
  const overlay = document.createElement("img");
  overlay.src = dataUrl;
  overlay.dataset.iaeOverlay = "image";
  commonOverlayStyle(overlay);
  placeOver(img, overlay);
  document.documentElement.appendChild(overlay);
  imageOverlays.push({img, overlay});
  return true;
}

function syncVideo(original, overlay) {
  if (Math.abs((overlay.currentTime || 0) - (original.currentTime || 0)) > 0.35) {
    try { overlay.currentTime = original.currentTime; } catch (_) {}
  }
  overlay.playbackRate = original.playbackRate || 1;
  overlay.muted = true;
  if (original.paused) overlay.pause();
  else overlay.play().catch(()=>{});
}

function addVideoOverlay(original, mediaUrl) {
  const overlay = document.createElement("video");
  overlay.src = mediaUrl;
  overlay.dataset.iaeOverlay = "video";
  overlay.muted = true;
  overlay.playsInline = true;
  overlay.preload = "auto";
  overlay.loop = original.loop;
  commonOverlayStyle(overlay);
  placeOver(original, overlay);
  const handlers = {sync: () => syncVideo(original, overlay)};
  ["play","pause","seeking","ratechange","volumechange"].forEach(ev => original.addEventListener(ev, handlers.sync));
  overlay.addEventListener("loadedmetadata", () => syncVideo(original, overlay));
  document.documentElement.appendChild(overlay);
  videoOverlays.push({original, overlay, handlers});
  return true;
}

async function processImage(img) {
  if (!running || processedImages.has(img)) return false;
  const r = img.getBoundingClientRect();
  if (r.width < 140 || r.height < 100) return false;
  const url = img.currentSrc || img.src;
  if (!url || url.startsWith("data:") || url.startsWith("blob:")) return false;
  processedImages.add(img);
  const res = await askBackground({action:"SWAP_URL", url});
  if (!running) return false;
  if (res?.ok && res.data_url) return addImageOverlay(img, res.data_url);
  processedImages.delete(img);
  throw new Error(res?.error || "Image FaceFusion error");
}

function getVideoUrl(video) {
  if (video.currentSrc) return video.currentSrc;
  if (video.src) return video.src;
  const source = [...video.querySelectorAll("source")].find(s => s.src);
  return source?.src || "";
}

async function processVideo(video) {
  if (!running || processedVideos.has(video)) return false;
  const r = video.getBoundingClientRect();
  if (r.width < 180 || r.height < 100) return false;
  const url = getVideoUrl(video);
  if (!url) return false;
  processedVideos.add(video);
  const res = await askBackground({action:"SWAP_VIDEO_URL", url});
  if (!running) return false;
  if (res?.ok && res.media_url) return addVideoOverlay(video, res.media_url);
  processedVideos.delete(video);
  throw new Error(res?.error || "Video FaceFusion error");
}

async function everywhere() {
  removeAll();
  running = true;
  window.addEventListener("scroll", updatePositions, true);
  window.addEventListener("resize", updatePositions, true);
  let imageDone = 0, videoDone = 0, failed = 0;
  let lastError = "";
  const videos = [...document.querySelectorAll("video")]
    .filter(v => {
      const r = v.getBoundingClientRect();
      return r.width >= 180 && r.height >= 100 && r.bottom > 0 && r.top < innerHeight * 1.5;
    })
    .slice(0, 3);
  for (const video of videos) {
    if (!running) break;
    try { if (await processVideo(video)) videoDone++; }
    catch(e) { failed++; lastError = String(e); }
  }
  const images = [...document.images]
    .filter(img => {
      const r = img.getBoundingClientRect();
      return img.complete && r.width >= 140 && r.height >= 100 && r.bottom > 0 && r.top < innerHeight * 2;
    })
    .sort((a,b) => {
      const ar=a.getBoundingClientRect(), br=b.getBoundingClientRect();
      return br.width*br.height - ar.width*ar.height;
    })
    .slice(0, 18);
  for (const img of images) {
    if (!running) break;
    try { if (await processImage(img)) imageDone++; }
    catch(e) { failed++; lastError = String(e); }
  }
  updatePositions();
  let message = `${imageDone} image${imageDone===1?"":"s"} + ${videoDone} video${videoDone===1?"":"s"} deepfaked.`;
  if (failed) message += ` ${failed} failed/skipped.`;
  if (lastError) message += "\n\nLAST ERROR:\n" + lastError;
  return {message};
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "GONE") {
    removeAll();
    sendResponse({message:"I AM GONE AWAY."});
    return;
  }
  if (msg.action === "EVERYWHERE") {
    everywhere().then(sendResponse);
    return true;
  }
});
