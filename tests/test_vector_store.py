from tests.factories import make_paper


def test_index_and_search(services, db):
    first = make_paper(db, "2501.00001", ("Speculative decoding drafts tokens.", "Graph neural networks."))
    second = make_paper(db, "2501.00002", ("Speculative decoding verification speedup.",))
    assert services.indexer.index_papers(db, [first, second]) == ["2501.00001", "2501.00002"]
    assert services.vector_store.count() == 3
    assert first.indexed_model == "test-hash-embedder"

    hits = services.vector_store.search("speculative decoding", k=3)
    assert {h.chunk_id for h in hits[:2]} == {"2501.00001#0", "2501.00002#0"}
    assert hits[0].similarity >= hits[-1].similarity
    assert all(0 <= h.similarity <= 1 for h in hits)


def test_search_restricted_to_papers(services, db):
    first = make_paper(db, "2501.00001", ("Speculative decoding drafts tokens.",))
    second = make_paper(db, "2501.00002", ("Speculative decoding verification.",))
    services.indexer.index_papers(db, [first, second])
    hits = services.vector_store.search("speculative decoding", k=5, paper_ids=["2501.00002"])
    assert [h.paper_id for h in hits] == ["2501.00002"]
    assert services.vector_store.search("anything", k=5, paper_ids=[]) == []


def test_reindex_replaces_old_vectors(services, db):
    paper = make_paper(db, "2501.00001", ("One.", "Two.", "Three."))
    services.indexer.index_papers(db, [paper])
    assert services.indexer.index_papers(db, [paper]) == []
    paper.chunks = paper.chunks[:1]
    paper.indexed_model = None
    db.commit()
    services.indexer.index_papers(db, [paper])
    assert services.vector_store.count() == 1


def test_pending_papers_are_not_indexed(services, db):
    paper = make_paper(db)
    paper.text_status = "pending"
    db.commit()
    assert services.indexer.index_papers(db, [paper]) == []


def test_status_reports_vectors(client, db, services):
    services.indexer.index_papers(db, [make_paper(db)])
    body = client.get("/api/system/status").json()
    assert body["counts"]["vectors"] == 2
    assert body["components"]["vector_store"]["status"] == "ok"
    assert "test-hash-embedder" in body["components"]["embeddings"]["detail"]
