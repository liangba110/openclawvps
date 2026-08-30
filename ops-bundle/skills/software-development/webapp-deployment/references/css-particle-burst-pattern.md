# CSS Particle Burst Animation (Center-Origin 3D Spread)

A technique for creating particles that burst outward from the center of the screen
in random directions using CSS custom properties set via Vue inline styles.

## Pattern

**Vue template** — generate N particles with random direction via `--x` / `--y`:
```html
<div class="space-dots">
  <div v-for="n in 80" :key="n" class="dot"
    :style="{
      '--x': (Math.random() * 400 - 200) + 'px',
      '--y': (Math.random() * 400 - 200) + 'px',
      animationDuration: (3 + Math.random() * 5) + 's',
      animationDelay: (Math.random() * 3) + 's',
      width: (2 + Math.random() * 4) + 'px',
      height: (2 + Math.random() * 4) + 'px',
    }">
  </div>
</div>
```

**CSS** — center origin, burst outward using CSS variables:
```css
.space-dots { position: fixed; inset: 0; z-index: -1; pointer-events: none; }
.dot {
  position: absolute; left: 50%; top: 50%;
  margin-left: -2px; margin-top: -2px;
  background: #3B82F6; border-radius: 50%;
  animation: burst linear infinite;
  box-shadow: 0 0 6px rgba(59,130,246,0.3);
}
@keyframes burst {
  0%   { transform: translate(0, 0) scale(0); opacity: 0; }
  15%  { transform: translate(calc(var(--x) * 0.2), calc(var(--y) * 0.2)) scale(1); opacity: 0.8; }
  50%  { transform: translate(calc(var(--x) * 0.6), calc(var(--y) * 0.6)) scale(0.8); opacity: 0.5; }
  100% { transform: translate(var(--x), var(--y)) scale(0); opacity: 0; }
}
```

## Critical Pitfall: `var()` in keyframes

**Problem**: If any keyframe omits `translate(...)`, CSS resets to `translate(0,0)` at that
step, so the particle never visibly moves:

```css
/* BROKEN — stays at center until 100% */
@keyframes burst {
  0%   { transform: translate(0, 0) scale(0); opacity: 0; }
  10%  { opacity: 0.8; transform: scale(1); }             /* reset to translate(0,0)! */
  90%  { opacity: 0.3; }                                   /* still at center */
  100% { transform: translate(var(--x), var(--y)) scale(0); opacity: 0; }
}
```

**Fix**: Include `translate()` in EVERY keyframe, using `calc()` for intermediate steps:

```css
/* WORKS — smooth travel from center to destination */
@keyframes burst {
  0%   { transform: translate(0, 0) scale(0); opacity: 0; }
  15%  { transform: translate(calc(var(--x) * 0.2), calc(var(--y) * 0.2)) scale(1); opacity: 0.8; }
  50%  { transform: translate(calc(var(--x) * 0.6), calc(var(--y) * 0.6)) scale(0.8); opacity: 0.5; }
  100% { transform: translate(var(--x), var(--y)) scale(0); opacity: 0; }
}
```

The same principle applies to any CSS property that uses `var()` in animations —
once you introduce `var()` in one frame, it must appear in every frame or the
property will snap back to its initial value.

## Alternative: Fixed-direction float-up

For particles rising from bottom to top:
```css
.dot { position: absolute; top: 100%; }
@keyframes floatUp {
  0%   { transform: translateY(0) scale(0); opacity: 0; }
  5%   { opacity: 0.7; transform: scale(0.5); }
  90%  { opacity: 0.4; }
  100% { transform: translateY(-120vh) scale(1.5); opacity: 0; }
}
```
