function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i=0; i<bytes.length; i+=chunk) binary += String.fromCharCode(...bytes.subarray(i,i+chunk));
  return btoa(binary);
}
chrome.runtime.onMessage.addListener((msg,sender,sendResponse)=>{
  if(msg.action!=="SWAP_URL") return;
  (async()=>{
    try {
      const r=await fetch(msg.url,{credentials:"omit",cache:"force-cache"});
      if(!r.ok) throw new Error("Image fetch failed: "+r.status);
      const mime=r.headers.get("content-type")||"application/octet-stream";
      const buffer=await r.arrayBuffer();
      const swap=await fetch("http://127.0.0.1:8765/swap",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({image_b64:arrayBufferToBase64(buffer),mime})});
      if(!swap.ok){const raw=await swap.text();let detail=raw;try{detail=JSON.parse(raw).error||raw}catch(_){}throw new Error(detail)}
      sendResponse(await swap.json());
    } catch(e){sendResponse({ok:false,error:String(e)})}
  })();
  return true;
});
