import { useEffect } from "react";

interface HeadOptions {
  title: string;
  description: string;
  path?: string;
}

function setMeta(name: string, content: string, attr: "name" | "property" = "name") {
  let el = document.querySelector<HTMLMetaElement>(`meta[${attr}="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

/** Section 7.6: "SEO meta and Open Graph per page" -- set at navigation time since this is a
 * client-rendered SPA with route-level code splitting, not a per-page SSR build. */
export function useDocumentHead({ title, description, path }: HeadOptions) {
  useEffect(() => {
    const fullTitle = `${title} | Meridian Auto Group`;
    document.title = fullTitle;
    setMeta("description", description);
    setMeta("og:title", fullTitle, "property");
    setMeta("og:description", description, "property");
    setMeta("og:type", "website", "property");
    if (path) setMeta("og:url", `https://meridianauto.example${path}`, "property");
    setMeta("twitter:card", "summary_large_image");
    setMeta("twitter:title", fullTitle);
    setMeta("twitter:description", description);
  }, [title, description, path]);
}
