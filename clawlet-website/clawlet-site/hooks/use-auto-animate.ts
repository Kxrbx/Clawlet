"use client";

import { useEffect, useRef, useState } from "react";

// SSR-safe auto-animate hook
// Uses dynamic import to avoid SSR errors with @formkit/auto-animate
export function useAutoAnimate<T extends HTMLElement = HTMLElement>() {
  const [parent, setParent] = useState<T | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined" || !parent) return;

    let mounted = true;

    const initAutoAnimate = async () => {
      try {
        const autoAnimate = (await import("@formkit/auto-animate")).default;
        if (mounted && parent) {
          // @ts-ignore - autoAnimate return type differs from expected
          cleanupRef.current = autoAnimate(parent, {
            // Respect user's motion preferences
            disrespectUserMotionPreference: false,
            // Easing function
            easing: "cubic-bezier(0.4, 0, 0.2, 1)",
            // Duration in ms
            duration: 300,
          });
        }
      } catch (error) {
        console.warn("AutoAnimate failed to load:", error);
      }
    };

    initAutoAnimate();

    return () => {
      mounted = false;
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, [parent]);

  return [parent, setParent] as const;
}
