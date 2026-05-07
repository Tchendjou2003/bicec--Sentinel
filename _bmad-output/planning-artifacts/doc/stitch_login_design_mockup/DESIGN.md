# Design System Specification: Editorial Security & Tonal Depth

## 1. Overview & Creative North Star
**Creative North Star: "The Luminous Guardian"**

This design system moves away from the sterile, cold aesthetics typical of security and audit software. Instead, it embraces an "Editorial Security" approach—combining the authoritative weight of a premium publication with the warmth of atmospheric light. 

The system breaks the traditional "dashboard" grid by utilizing **intentional asymmetry** and **atmospheric focal points**. We use soft, out-of-focus light shapes (blobs) in the background to create depth, ensuring the central interface feels like a physical object resting in a curated space rather than a flat digital layer.

---

## 2. Colors: Atmospheric Tones
Our palette is rooted in a high-contrast relationship between deep charred grays and vibrant, glowing oranges, bridged by warm, paper-like neutrals.

*   **Primary Ember (`primary` & `primary_container`):** Used for critical actions and brand identity. Transitions from `#a23f00` to `#f76b1c` should be used as linear gradients (135°) to simulate light hitting a surface.
*   **The "No-Line" Rule:** Sectioning is strictly prohibited from using 1px solid borders. Boundaries must be defined by shifts in surface tiers (e.g., a `surface_container_low` sidebar against a `surface` background).
*   **Surface Hierarchy & Nesting:** 
    *   **Layer 0 (Background):** `surface` (#fcf9f8) with ambient gradients.
    *   **Layer 1 (Cards):** `surface_container_lowest` (#ffffff) to provide maximum "pop."
    *   **Layer 2 (In-card elements):** `surface_container` (#f0eded) for input wells or status bars.
*   **The "Glass & Gradient" Rule:** Use `surface_container_low` at 80% opacity with a `24px` backdrop-blur for floating navigation or modals. This ensures the ambient background "glow" bleeds through the interface, softening the user experience.

---

## 3. Typography: The Modern Editorial
The type scale prioritizes legibility and brand authority by pairing a geometric, modern sans-serif for impact with a highly functional sans-serif for data.

*   **Display & Headline (Plus Jakarta Sans):** These are our "Editorial" voices. Use `display-md` for welcome states. The tracking should be slightly tightened (-2%) for a premium, custom-fitted feel.
*   **Title & Body (Inter):** Inter provides a neutral, high-utility balance. Use `title-md` for form labels to ensure they feel grounded and professional.
*   **Signature Styling:** Headlines should utilize "Tonal Highlighting"—pairing `on_surface` text with a single high-impact word in `primary` to guide the eye immediately to the brand's presence.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are too "digital." We utilize **Ambient Shadows** and **Tonal Stacking** to create a high-end physical presence.

*   **The Layering Principle:** Rather than using borders to separate the login card from the background, we rely on the contrast between the pure white `surface_container_lowest` and the warm `surface` background.
*   **Ambient Shadows:** For the main central card, use a multi-layered shadow:
    *   *Layer 1:* 0px 4px 20px rgba(141, 113, 101, 0.08) (A tinted shadow using `outline`).
    *   *Layer 2:* 0px 15px 50px rgba(0, 0, 0, 0.04).
*   **The "Ghost Border" Fallback:** If a container requires further definition (e.g., in high-glare environments), use a `1px` stroke of `outline_variant` at **15% opacity**. Never use a 100% opaque border.

---

## 5. Components

### Buttons
*   **Primary:** A vibrant gradient from `primary_container` to `primary`. Shape is `md` (0.75rem). Text is `label-md` uppercase with 0.05em letter spacing.
*   **Secondary/Ghost:** No background fill. Use `on_surface` text with a `Ghost Border` that only appears on hover.

### Input Fields
*   **The "Well" Style:** Inputs should use `surface_container_lowest` with a subtle `outline_variant` (20% opacity) border. 
*   **Focus State:** Transition the border to `primary` (100% opacity) and add a soft 4px outer glow of `primary_fixed` to simulate the field "lighting up."

### Cards & Containers
*   **Central Card:** Utilize `xl` (1.5rem) corner radius. The header of the card should be separated by vertical whitespace, never a divider line.
*   **Status Badges (Chips):** Use `surface_container_high` with `on_surface_variant` text. For "Audit" contexts, use `tertiary_container` for a professional blue accent that distinguishes metadata from primary actions.

### The "Sentinel" Brand Block
*   **Iconography:** The horse icon must be housed in a circular `primary` container or a high-contrast `on_surface` circle to act as a "seal of quality."

---

## 6. Do's and Don'ts

### Do:
*   **Use Whitespace as Structure:** Use the Spacing Scale to separate form groups. If it feels too loose, increase the tonal shift of the background rather than adding a line.
*   **Embrace the Glow:** Use large, soft radial gradients of `primary_fixed` (at 10-20% opacity) in the corners of the viewport to frame the content.
*   **Maintain Type Contrast:** Ensure `body-sm` is used sparingly for legal/footer text, keeping the main interface "airy" with `body-md`.

### Don't:
*   **No "Flat" Grays:** Never use pure #000 or neutral #888. Always use the tinted neutrals (`surface_variant`, `outline`) to keep the design feeling warm and bespoke.
*   **No Sharp Corners:** Avoid the `none` or `sm` roundedness tokens for main containers. The interface should feel approachable and organic.
*   **Avoid Industrial Shadows:** Never use high-opacity, blurry black shadows. If the shadow is visible as "black," it is too heavy. It should feel like a soft glow or a natural occlusion.