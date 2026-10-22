import type { Directive } from "vue";

type RevealOptions = { delay?: number; y?: number } | undefined;

let observer: IntersectionObserver | null = null;

function getObserver(): IntersectionObserver {
  if (!observer) {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // Replay on every entry: toggle instead of one-shot.
          entry.target.classList.toggle("is-visible", entry.isIntersecting);
        }
      },
      { threshold: [0, 0.15], rootMargin: "0px 0px -8% 0px" },
    );
  }
  return observer;
}

/**
 * v-reveal — fade/slide an element in when it enters the viewport,
 * and reset when it leaves, so scrolling up or back down replays it.
 * Usage: v-reveal / v-reveal="{ delay: 80, y: 24 }"
 */
export const reveal: Directive<HTMLElement, RevealOptions> = {
  mounted(el, binding) {
    if (typeof window === "undefined") return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("reveal", "is-visible");
      return;
    }

    el.classList.add("reveal");
    const { delay, y } = binding.value ?? {};
    if (delay) el.style.setProperty("--reveal-delay", `${delay}ms`);
    if (y !== undefined) el.style.setProperty("--reveal-y", `${y}px`);

    getObserver().observe(el);
  },
  unmounted(el) {
    observer?.unobserve(el);
  },
};
