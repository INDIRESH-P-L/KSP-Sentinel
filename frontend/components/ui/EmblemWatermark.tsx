import React from "react";

/**
 * The Karnataka State Emblem, fixed behind every screen.
 *
 * This used to be a procedural SVG: hand-coded feather teardrops fanned by trigonometry
 * into an approximation of the Gandaberunda. It was a stand-in, and it read as one — a
 * stylised bird rather than the state crest, missing the lion capital, the shield, the
 * elephant supporters and the सत्यमेव जयते scroll that make the emblem what it is.
 *
 * The real crest was already in the repository. `public/karnataka_emblem_feathered.png`
 * had been prepared for exactly this use — rendered in champagne gold, edge-feathered
 * for watermark blending by scripts/feather_edges.py — and was referenced by nothing.
 * It is now what renders.
 *
 * Compositing
 * -----------
 * The source carries a genuine alpha channel (transparent corners feathering into an
 * opaque centre), so it needs no `mix-blend-mode` compensation — the earlier SVG used
 * `screen`/`multiply` to knock out a background this asset simply does not have.
 * Straight alpha compositing is both simpler and more faithful: the metal keeps its
 * modelled relief instead of being flattened by a blend.
 *
 * Weight
 * ------
 * The source is 1.32 MB, which is far more than a watermark can justify. It is served
 * from a 1200px-wide WebP (110 KB) with a PNG fallback, decoded asynchronously and
 * marked low priority so it never competes with the sign-in form for bandwidth.
 *
 * Purely decorative: pointer-events:none and aria-hidden, set by the `.emblem-watermark`
 * class in app/globals.css, which also owns every size, opacity and position rule —
 * including the login-hero swell driven by `data-authed="false"` on <html>.
 */
export default function EmblemWatermark({ className = "" }: { className?: string }) {
  return (
    <div className={`emblem-watermark ${className}`} aria-hidden="true">
      <picture>
        <source srcSet="/emblem-watermark.webp" type="image/webp" />
        {/* A plain <img>, not next/image: this is a static export
            (images.unoptimized), so next/image would add a client component and a
            wrapper for no benefit. The asset is pre-optimised at build time instead. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/emblem-watermark.png"
          alt=""
          decoding="async"
          loading="lazy"
          fetchPriority="low"
          draggable={false}
        />
      </picture>
    </div>
  );
}
