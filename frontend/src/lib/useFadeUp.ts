import { useEffect, useRef } from "react";

/** Section 7.1 motion: "fade-up on scroll (150 to 300 ms), no heavy parallax". Pairs with the
 * `.fade-up` / `.is-visible` classes in index.css, which themselves collapse to no-op under
 * `prefers-reduced-motion`. */
export function useFadeUp<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("is-visible");
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return ref;
}
