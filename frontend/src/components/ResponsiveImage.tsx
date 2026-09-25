interface ResponsiveImageProps {
  slug: string;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
}

const WIDTHS = [640, 1280, 1920];

/** Section 7.2: real photos converted to AVIF/WebP at 3 responsive widths, served from
 * `public/images/<slug>/`, with a blurred low-res placeholder as the background while the
 * real image loads. */
export default function ResponsiveImage({ slug, alt, className, sizes = "100vw", priority = false }: ResponsiveImageProps) {
  const base = `/images/${slug}`;
  const avifSrcSet = WIDTHS.map((w) => `${base}/${w}.avif ${w}w`).join(", ");
  const webpSrcSet = WIDTHS.map((w) => `${base}/${w}.webp ${w}w`).join(", ");

  return (
    <picture>
      <source type="image/avif" srcSet={avifSrcSet} sizes={sizes} />
      <source type="image/webp" srcSet={webpSrcSet} sizes={sizes} />
      <img
        src={`${base}/1280.webp`}
        alt={alt}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        className={className}
        style={{ backgroundImage: `url(${base}/blur.webp)`, backgroundSize: "cover", backgroundPosition: "center" }}
      />
    </picture>
  );
}
