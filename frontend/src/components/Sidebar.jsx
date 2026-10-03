const LINKS = [
  { page: "research", label: "Research" },
  { page: "improvement", label: "Improvement history" },
  { page: "experiments", label: "Experiments" },
  { page: "system", label: "System" },
];

export default function Sidebar({ active }) {
  const current = active === "query" ? "research" : active;
  return (
    <aside className="sidebar">
      <div className="brand">Self-Improving RAG</div>
      <nav>
        {LINKS.map((link) => (
          <a
            key={link.page}
            href={`#/${link.page}`}
            className={link.page === current ? "active" : undefined}
            aria-current={link.page === current ? "page" : undefined}
          >
            {link.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
