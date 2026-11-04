import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

/**
 * An open book: the table of contents on the left leaf, the current page on the right.
 *
 * Every section of the app (and later each character, campaign and catalogue) is a tome. The tome
 * doesn't know what's on its pages; it only lays them out, links them and turns them.
 * On narrow screens the two leaves stack, contents first.
 */
export interface TomeContentsEntry {
  slug: string;
  title: string;
}

interface TomeProps {
  /** Small line above the title, e.g. the mode. */
  eyebrow?: string;
  title: string;
  subtitle?: string;
  /** Absolute path the page slugs hang off, e.g. "/play/characters". */
  basePath: string;
  pages: TomeContentsEntry[];
  /** Slug of the open page; anything not in `pages` shows no "current" entry or page turner. */
  current?: string;
  cover?: string;
  children: ReactNode;
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
export const roman = (n: number) => ROMAN[n - 1] ?? String(n);

export function Tome({ eyebrow, title, subtitle, basePath, pages, current, cover = "oxblood", children }: TomeProps) {
  const index = pages.findIndex((p) => p.slug === current);
  const prev = index > 0 ? pages[index - 1] : undefined;
  const next = index >= 0 && index < pages.length - 1 ? pages[index + 1] : undefined;
  const href = (slug: string) => `${basePath}/${slug}`;

  return (
    <article className={`tome cover-${cover}`} aria-labelledby="tome-title" data-testid="tome">
      <div className="tome-leaf tome-contents">
        {eyebrow && <p className="tome-eyebrow">{eyebrow}</p>}
        <h1 id="tome-title">{title}</h1>
        {subtitle && <p className="tome-subtitle">{subtitle}</p>}
        {pages.length > 0 && (
          <nav aria-label="Table of contents" data-testid="tome-contents">
            <h2 className="toc-heading">Contents</h2>
            <ol className="toc">
              {pages.map((p, i) => (
                <li key={p.slug}>
                  <NavLink to={href(p.slug)}>
                    <span className="toc-num" aria-hidden="true">
                      {roman(i + 1)}.
                    </span>
                    <span className="toc-title">{p.title}</span>
                  </NavLink>
                </li>
              ))}
            </ol>
          </nav>
        )}
      </div>

      <div className="tome-leaf tome-page" data-testid="tome-page">
        {children}
        {index >= 0 && pages.length > 1 && (
          <nav className="page-turner" aria-label="Turn the page">
            {prev ? (
              <Link to={href(prev.slug)} rel="prev">
                <span aria-hidden="true">←</span> {prev.title}
              </Link>
            ) : (
              <span />
            )}
            <span className="folio" data-testid="folio">
              Page {index + 1} of {pages.length}
            </span>
            {next ? (
              <Link to={href(next.slug)} rel="next">
                {next.title} <span aria-hidden="true">→</span>
              </Link>
            ) : (
              <span />
            )}
          </nav>
        )}
      </div>
    </article>
  );
}

/** "Tavern › Player Mode › Character Manager" */
export function Breadcrumbs({ trail }: { trail: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="breadcrumbs">
      <ol>
        {trail.map((crumb, i) => (
          <li key={i}>
            {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
