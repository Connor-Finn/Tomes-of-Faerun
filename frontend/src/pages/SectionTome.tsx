import type { ComponentType } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Breadcrumbs, Tome } from "../components/Tome";
import { MODE_LABELS, useEnterMode } from "../lib/mode";
import type { SectionDef, TomePageDef } from "../lib/sections";
import { CreateCharacter } from "./characters/CreateCharacter";
import { MyCharacters } from "./characters/MyCharacters";

/** Pages that are built, by "section key/page slug". Every other page shows its plans. */
const BUILT_PAGES: Record<string, ComponentType> = {
  "character-manager/my-characters": MyCharacters,
  "character-manager/create": CreateCharacter,
};

/** One section of the app (e.g. Character Manager), shown as a tome. */
export function SectionTome({ section }: { section: SectionDef }) {
  const { page: slug } = useParams();
  useEnterMode(section.mode);

  const basePath = `/${section.path}`;
  const first = section.pages[0];
  if (!section.sealed && !slug && first) return <Navigate to={`${basePath}/${first.slug}`} replace />;

  const page = section.pages.find((p) => p.slug === slug);
  const modeLabel = MODE_LABELS[section.mode];
  const Built = page ? BUILT_PAGES[`${section.key}/${page.slug}`] : undefined;

  return (
    <>
      <Breadcrumbs
        trail={[
          { label: "Guild Hall", to: "/guild-hall" },
          { label: modeLabel, to: "/guild-hall" },
          { label: section.title },
        ]}
      />
      <Tome
        eyebrow={modeLabel}
        title={section.title}
        subtitle={section.blurb}
        basePath={basePath}
        pages={section.pages}
        current={page?.slug}
        cover={section.cover}
      >
        {section.sealed ? (
          <SealedPage />
        ) : Built ? (
          <Built />
        ) : page ? (
          <DraftPage page={page} />
        ) : (
          <MissingPage basePath={basePath} />
        )}
      </Tome>
    </>
  );
}

/** A page whose feature isn't built yet: it shows what will be written on it. */
function DraftPage({ page }: { page: TomePageDef }) {
  return (
    <section aria-labelledby="page-title" data-testid="draft-page">
      <h2 id="page-title" className="page-title">
        {page.title}
      </h2>
      <p className="page-summary">{page.summary}</p>
      <div className="draft-note">
        <span className="badge">Being written</span>
        <h3>Planned for this page</h3>
        <ul className="plans">
          {page.plans.map((plan) => (
            <li key={plan}>{plan}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function SealedPage() {
  return (
    <section aria-labelledby="page-title" className="sealed-page" data-testid="sealed-page">
      <div className="wax-seal" aria-hidden="true" />
      <h2 id="page-title" className="page-title">
        This tome is still sealed
      </h2>
      <p className="muted">Its pages haven't been written yet. Check back after a few more adventures.</p>
      <Link to="/guild-hall" className="btn ghost small">
        Back to the guild hall
      </Link>
    </section>
  );
}

function MissingPage({ basePath }: { basePath: string }) {
  return (
    <section aria-labelledby="page-title" data-testid="missing-page">
      <h2 id="page-title" className="page-title">
        This page is missing
      </h2>
      <p className="muted">It may have been torn out. Pick a chapter from the contents instead.</p>
      <Link to={basePath} className="btn ghost small">
        Go to the first page
      </Link>
    </section>
  );
}
