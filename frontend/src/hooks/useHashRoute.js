import { useEffect, useState } from "react";

function parse(hash) {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { page: parts[0] || "research", params: parts.slice(1).map(decodeURIComponent) };
}

export function navigate(path) {
  window.location.hash = `#/${path}`;
}

export function useHashRoute() {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
