from dataclasses import dataclass

from app.core.config import Settings
from app.services.adaptation import WeightAdapter
from app.services.document_processor import DocumentProcessor
from app.services.embeddings import Embedder, SentenceTransformerEmbedder
from app.services.evaluation import SelfEvaluator
from app.services.generation import AnswerGenerator
from app.services.indexer import Indexer
from app.services.llm import LLMClient, build_llm
from app.services.paper_retrieval import PaperRetriever
from app.services.query_pipeline import QueryPipeline
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.vector_store import VectorStore


@dataclass
class Services:
    paper_retriever: PaperRetriever
    document_processor: DocumentProcessor
    embedder: Embedder
    vector_store: VectorStore
    indexer: Indexer
    retrieval: RetrievalPipeline
    llm: LLMClient | None
    query_pipeline: QueryPipeline | None
    adapter: WeightAdapter


def build_services(
    settings: Settings,
    embedder: Embedder | None = None,
    llm: LLMClient | None = None,
    evaluator_llm: LLMClient | None = None,
) -> Services:
    embedder = embedder or SentenceTransformerEmbedder(settings)
    vector_store = VectorStore(settings, embedder)
    paper_retriever = PaperRetriever(settings)
    document_processor = DocumentProcessor(settings)
    indexer = Indexer(vector_store)
    retrieval = RetrievalPipeline(settings, paper_retriever, document_processor, indexer, vector_store, embedder)
    llm = llm or build_llm(settings)
    adapter = WeightAdapter(settings)
    query_pipeline = None
    if llm is not None:
        if evaluator_llm is not None:
            judge = evaluator_llm
        elif settings.separate_evaluator:
            judge = build_llm(settings, settings.evaluator_endpoint)
        else:
            judge = llm
        query_pipeline = QueryPipeline(settings, retrieval, AnswerGenerator(llm), SelfEvaluator(judge), adapter)
    return Services(
        paper_retriever=paper_retriever,
        document_processor=document_processor,
        embedder=embedder,
        vector_store=vector_store,
        indexer=indexer,
        retrieval=retrieval,
        llm=llm,
        query_pipeline=query_pipeline,
        adapter=adapter,
    )
