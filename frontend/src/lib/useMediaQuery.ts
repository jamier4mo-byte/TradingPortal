import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => (typeof window !== "undefined" ? window.matchMedia(query).matches : false));
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setMatches(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

/** Device class from the breakpoints in @theme: phone <600, tablet 600–1023, laptop+ ≥1024. */
export function useDevice(): "phone" | "tablet" | "desktop" {
  const tablet = useMediaQuery("(min-width: 600px)");
  const laptop = useMediaQuery("(min-width: 1024px)");
  if (laptop) return "desktop";
  if (tablet) return "tablet";
  return "phone";
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator !== "undefined" ? navigator.onLine : true));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}
