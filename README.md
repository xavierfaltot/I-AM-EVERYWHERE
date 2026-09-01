# I AM EVERYWHERE

**Put your face everywhere on the Internet.**

I AM EVERYWHERE is a Chrome/Chromium browser extension that transforms the web into a personal deepfake using a local FaceFusion engine.

Load one or several source faces, browse any website, and hit **I AM EVERYWHERE**. The extension processes visible images — and direct HTML5 videos in the current prototype — through FaceFusion, then overlays the transformed media back onto the page without modifying the original website.

Hit **I AM GONE AWAY** and the original web instantly returns.

## The idea

This is not a single-image deepfake generator. **The browser becomes the deepfake machine.**

News, fashion, advertising, politics, culture, e-commerce: as you browse, other identities progressively disappear and the Internet becomes populated by versions of you.

`WEB → FACEFUSION → YOU → WEB`

## Current version

### V4.1 — Multi-Face Carousel

The extension now includes a persistent source-face library:

- Add one or several portraits at once
- Browse your source faces with a carousel
- Select the active identity before processing the page
- Remove portraits from the library
- Keep the library stored locally in Chrome
- Automatically migrate a previously stored single source face

The current face in the carousel is the active FaceFusion source.

### Images

Visible webpage images are fetched locally, normalized to standard JPEG when needed, processed by FaceFusion using `face_swapper` with `face-selector-mode many`, and displayed as overlays above the original images.

Using overlays avoids React, lazy-loading and `srcset` replacing the transformed images with the originals.

### Video prototype

V4 also includes an experimental direct-video pipeline for standard HTML5 video files:

`VIDEO → FACEFUSION → PROCESSED MP4 → SYNCHRONIZED OVERLAY`

The transformed video follows play, pause, seek and playback-rate changes while the original page keeps its own audio.

Current video support is intended for directly fetchable MP4/WebM/MOV files. Blob/MediaSource, HLS/DASH, YouTube, TikTok, Instagram and live-stream processing require a different streaming architecture and are not yet handled by this prototype.

## Local-first

Face processing happens through your local FaceFusion installation. Source websites are not modified.

Current development setup: Chrome/Chromium + FaceFusion 3.6.1, including Pinokio installations.

## Controls

**+ ADD A FACE** — add source portraits to the local carousel  
**‹ / ›** — select your active identity  
**I AM EVERYWHERE** — transform visible media  
**I AM GONE AWAY** — remove overlays and restore the original web  
**TEST FACEFUSION BRIDGE** — check the local FaceFusion connection

## Status

Experimental prototype / work in progress.

The long-term goal is simple: make identity replacement a property of browsing itself, rather than a separate deepfake workflow.
