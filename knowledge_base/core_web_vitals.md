---
title: Core Web Vitals Guidance
category: tech
source: internal
---

# Core Web Vitals Guidance

Core Web Vitals are Google's user-experience metrics that directly affect search rankings (since 2021). They measure loading performance, interactivity, and visual stability.

## LCP — Largest Contentful Paint

**Target:** ≤ 2.5 seconds
**What it measures:** Time until the largest visible element (hero image, heading) is rendered.

Common causes of poor LCP:
- Unoptimised hero images (use WebP, compress, lazy-load below-the-fold only)
- No CDN — slow origin server response
- Render-blocking JavaScript or CSS in `<head>`

## INP — Interaction to Next Paint

**Target:** ≤ 200ms (replaced FID in March 2024)
**What it measures:** Time from user input to the browser's next visual response.

Common causes of poor INP:
- Heavy JavaScript executing on the main thread
- Long tasks (>50ms) blocking input processing
- Third-party scripts (chat widgets, analytics) not loaded asynchronously

## CLS — Cumulative Layout Shift

**Target:** ≤ 0.1
**What it measures:** How much page content shifts unexpectedly during load.

Common causes of poor CLS:
- Images without explicit `width` and `height` attributes
- Ads or iframes without reserved space
- Fonts causing flash of unstyled text — use `font-display: swap`

## HTTPS

HTTPS is a confirmed ranking signal. Pages on HTTP are flagged "Not Secure" by browsers, reduce visitor trust, and rank lower. All internal links should enforce HTTPS.

## Mobile Viewport

The `<meta name="viewport" content="width=device-width, initial-scale=1">` tag is required for responsive rendering. Without it, Google's mobile-first indexer cannot properly evaluate the page.

## Scoring Signal

High score: LCP < 2.5s, no render-blocking resources, HTTPS enforced, viewport meta present, images have explicit dimensions. Low score: LCP > 4s, render-blocking scripts in head, HTTP only, no viewport meta.
