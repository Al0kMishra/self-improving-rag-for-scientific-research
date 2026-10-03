import { authorsShort, year } from "../services/format.js";

export default function PapersList({ retrieved }) {
  const papers = new Map();
  retrieved.forEach((item) => {
    const entry = papers.get(item.paper.id) || { paper: item.paper, chunks: 0, cited: 0 };
    entry.chunks += 1;
    entry.cited += item.cited ? 1 : 0;
    papers.set(item.paper.id, entry);
  });

  return (
    <section className="card">
      <h2 className="headline-sm">Retrieved papers</h2>
      <ul className="paper-list">
        {[...papers.values()].map(({ paper, chunks, cited }) => (
          <li key={paper.id}>
            <a href={paper.abs_url} target="_blank" rel="noreferrer">
              {paper.title}
            </a>
            <div className="body-sm muted">
              {authorsShort(paper.authors)} · {year(paper.published_at)} · {paper.primary_category}
            </div>
            <div className="body-sm muted">
              {chunks} excerpt{chunks === 1 ? "" : "s"} retrieved, {cited} cited
              {paper.pdf_url && (
                <>
                  {" · "}
                  <a href={paper.pdf_url} target="_blank" rel="noreferrer">
                    PDF
                  </a>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
