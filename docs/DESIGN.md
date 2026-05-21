---
name: Luminous Warmth
colors:
  surface: '#fcf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fcf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0eded'
  surface-container-high: '#eae7e7'
  surface-container-highest: '#e5e2e1'
  on-surface: '#1c1b1b'
  on-surface-variant: '#524434'
  inverse-surface: '#313030'
  inverse-on-surface: '#f3f0ef'
  outline: '#857462'
  outline-variant: '#d7c3ae'
  surface-tint: '#835400'
  primary: '#835400'
  on-primary: '#ffffff'
  primary-container: '#f9a826'
  on-primary-container: '#674100'
  inverse-primary: '#ffb957'
  secondary: '#7d5354'
  on-secondary: '#ffffff'
  secondary-container: '#fec7c7'
  on-secondary-container: '#7a5051'
  tertiary: '#585f66'
  on-tertiary: '#ffffff'
  tertiary-container: '#b3bac2'
  on-tertiary-container: '#434a51'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffddb5'
  primary-fixed-dim: '#ffb957'
  on-primary-fixed: '#2a1800'
  on-primary-fixed-variant: '#643f00'
  secondary-fixed: '#ffdad9'
  secondary-fixed-dim: '#efb9b9'
  on-secondary-fixed: '#301214'
  on-secondary-fixed-variant: '#633c3d'
  tertiary-fixed: '#dce3eb'
  tertiary-fixed-dim: '#c0c7cf'
  on-tertiary-fixed: '#151c22'
  on-tertiary-fixed-variant: '#40484e'
  background: '#fcf9f8'
  on-background: '#1c1b1b'
  surface-variant: '#e5e2e1'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '500'
    lineHeight: '1.6'
  body-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.2'
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-padding-mobile: 20px
  container-padding-desktop: 48px
  gutter: 16px
  card-gap: 24px
---

# Luminous Warmth Design System

## Brand & Style

The design system is centered around a sophisticated **Glassmorphism** aesthetic, optimized for premium fintech or lifestyle applications. The brand personality is serene, high-end, and inviting, moving away from cold corporate whites toward a warmer, more human "Vanilla Cream" foundation.

The emotional response should be one of "calm clarity." By using high-transparency layers and a soft, low-saturation palette, the UI feels lightweight and ethereal. The visual style relies on heavy backdrop blurs, subtle inner glows to simulate glass edges, and a "warm-light" environment where elements appear to float over a soft, glowing canvas.

## Colors

The palette is rooted in a warm, off-white background (`#FCF9F2`) which provides a much softer contrast for the glass elements than pure white.

- **Primary:** A soft, golden orange-yellow used for key highlights and "active" states.
- **Support Tones:** Pale pink, soft lavender, and muted blue are used for categorical distinction (e.g., different currency cards). These colors are kept at very low saturation (10-15%) to maintain a premium, airy feel.
- **Glass Fill:** Surfaces use a white fill at 40-60% opacity with a high-density backdrop blur (20px - 40px).
- **Typography:** Deep charcoal rather than pure black is used to maintain the softness of the warm palette.

## Typography

The system utilizes **Plus Jakarta Sans** for headlines to provide a modern, slightly rounded, and friendly geometric feel. This is paired with **Manrope** for body text and labels to ensure high legibility and a refined, professional finish.

Large numeric displays (like balances) should use the `display-lg` token with tight letter-spacing to emphasize the "Modern Wealth" aesthetic. Labels often use uppercase styling with increased tracking to create a clear hierarchy against the softer glass backgrounds.

## Layout & Spacing

The design system follows a **fluid grid** model with generous safe areas.

- **Grid:** A 12-column grid for desktop and a 2-column/1-column flow for mobile.
- **Rhythm:** An 8px linear scale drives all spacing.
- **Margins:** Screens should maintain large outer margins (at least 20px on mobile) to allow the background warmth and abstract decorative elements (like the subtle gold mesh lines) to breathe.
- **Card Layout:** Information within glass cards should use "inset" padding of 24px to ensure content doesn't feel cramped against the rounded corners.

## Elevation & Depth

Depth is achieved through **Backdrop Blurs** and **Stacked Transparency** rather than traditional drop shadows.

1. **Base Layer:** The warm `#FCF9F2` background, often featuring soft, large-scale organic gradients (blobs) in primary/secondary colors at 5% opacity.
2. **Surface Layer:** Glass cards with `backdrop-filter: blur(30px)` and a 1px solid white border at 20% opacity to define the "edge" of the glass.
3. **Active State:** When an element is focused, use a very soft, diffused ambient shadow with a tint of the primary color (e.g., `rgba(249, 168, 38, 0.1)`) to suggest a gentle glow.

## Shapes

The shape language is highly organic and approachable.

- **Standard Cards:** Use a 1rem (16px) radius to maintain a modern, friendly feel.
- **Interaction Elements:** Buttons and small tags should use a more pronounced rounding (up to 2rem) to create a "pill" effect that contrasts against the larger rectangular cards.
- **Decorative Elements:** Use perfectly circular icons or abstract fluid shapes in the background to reinforce the "soft" brand identity.

## Components

- **Glass Cards:** The signature component. Must include a semi-transparent background, a backdrop blur, and a thin "inner glow" border. Content inside should be grouped with horizontal dividers using `border-style: dotted` or low-opacity lines.
- **Action Buttons:** Primary buttons are solid (using the Primary Gold color), while secondary buttons are "Ghost Glass" (transparent with a visible border).
- **Currency Chips:** Tiny, high-contrast badges that sit in the top-right of cards to denote the asset type, using the `label-sm` typography.
- **Input Fields:** Minimalist design with only a bottom border or a very faint glass-fill background. Focus states should trigger a subtle color shift in the border to the primary gold.
- **Iconography:** Use "Thin" or "Light" weight strokes to match the airy typography. Avoid heavy, filled icons unless they are used as primary focal points (like the golden moon/sun icons).
