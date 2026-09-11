"""Unit-level test fixtures with agent module switching."""

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


def _clean_app_modules():
    for k in list(sys.modules):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]


def _ensure_shared():
    if "shared" not in sys.modules:
        shared_pkg = types.ModuleType("shared")
        shared_pkg.__path__ = [str(ROOT / "shared")]
        sys.modules["shared"] = shared_pkg


def _setup_agent(agent_name):
    _clean_app_modules()
    _ensure_shared()
    agent_app = str(ROOT / agent_name / "app")
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [agent_app]
    sys.modules["app"] = app_pkg


@pytest.fixture
def knowledge_modules():
    _setup_agent("knowledge-agent")
    from app.tools.chunk_document import Chunk, chunk_document
    from app.tools.embed_document import EmbeddingResult, embed_chunks, embed_single
    from app.tools.fetch_document import FetchResult, fetch_document
    from app.tools.parse_document import ParsedDocument, parse_document

    return types.SimpleNamespace(
        parse_document=parse_document,
        ParsedDocument=ParsedDocument,
        chunk_document=chunk_document,
        Chunk=Chunk,
        embed_chunks=embed_chunks,
        embed_single=embed_single,
        EmbeddingResult=EmbeddingResult,
        fetch_document=fetch_document,
        FetchResult=FetchResult,
    )


@pytest.fixture
def rag_modules():
    _setup_agent("rag-agent")
    from app.tools.query_rewriter import RewrittenQuery, rewrite_query
    from app.tools.reranker import RerankedResult, rerank

    return types.SimpleNamespace(
        rewrite_query=rewrite_query,
        RewrittenQuery=RewrittenQuery,
        rerank=rerank,
        RerankedResult=RerankedResult,
    )


@pytest.fixture
def quiz_modules():
    _setup_agent("quiz-agent")
    from app.tools.generate_questions import GeneratedQuestion, generate_questions
    from app.tools.grade_answer import GradeResult, grade_answer
    from app.tools.manage_wrong_book import add_wrong_question, get_wrong_questions

    return types.SimpleNamespace(
        generate_questions=generate_questions,
        GeneratedQuestion=GeneratedQuestion,
        grade_answer=grade_answer,
        GradeResult=GradeResult,
        add_wrong_question=add_wrong_question,
        get_wrong_questions=get_wrong_questions,
    )


@pytest.fixture
def review_modules():
    _setup_agent("review-agent")
    from app.tools.spaced_repetition import (
        SpacedRepetitionResult,
        calculate_mastery_score,
        calculate_next_review,
        get_initial_interval,
    )

    return types.SimpleNamespace(
        calculate_next_review=calculate_next_review,
        get_initial_interval=get_initial_interval,
        calculate_mastery_score=calculate_mastery_score,
        SpacedRepetitionResult=SpacedRepetitionResult,
    )


@pytest.fixture
def progress_modules():
    _setup_agent("progress-agent")
    from app.tools.calculate_mastery import calculate_mastery
    from app.tools.generate_statistics import get_dashboard_data

    return types.SimpleNamespace(
        calculate_mastery=calculate_mastery,
        get_dashboard_data=get_dashboard_data,
    )


@pytest.fixture
def feynman_modules():
    _setup_agent("feynman-agent")
    from app.state_machine import FeynmanState
    from app.tools import evaluate_explanation

    return types.SimpleNamespace(
        FeynmanState=FeynmanState,
        evaluate_explanation=evaluate_explanation,
    )


@pytest.fixture
def review_schedule_modules():
    _setup_agent("review-agent")
    from app.tools.schedule_manager import (
        create_review_schedule,
        get_pending_reviews,
        get_review_stats,
        submit_review_result,
    )

    return types.SimpleNamespace(
        get_pending_reviews=get_pending_reviews,
        create_review_schedule=create_review_schedule,
        submit_review_result=submit_review_result,
        get_review_stats=get_review_stats,
    )


@pytest.fixture
def quiz_wrong_book_modules():
    _setup_agent("quiz-agent")
    from app.tools.manage_wrong_book import (
        add_wrong_question,
        get_wrong_questions,
        increment_review_count,
        mark_mastered,
    )

    return types.SimpleNamespace(
        add_wrong_question=add_wrong_question,
        get_wrong_questions=get_wrong_questions,
        mark_mastered=mark_mastered,
        increment_review_count=increment_review_count,
    )


@pytest.fixture
def rag_search_modules():
    _setup_agent("rag-agent")
    from app.tools.hybrid_search import SearchResult, extract_keywords, hybrid_search
    from app.tools.reranker import RerankedResult, rerank
    from app.tools.vector_store import search_by_keywords, search_similar

    return types.SimpleNamespace(
        hybrid_search=hybrid_search,
        extract_keywords=extract_keywords,
        SearchResult=SearchResult,
        search_similar=search_similar,
        search_by_keywords=search_by_keywords,
        rerank=rerank,
        RerankedResult=RerankedResult,
    )


@pytest.fixture
def knowledge_service_modules():
    _setup_agent("knowledge-agent")
    from app.services.document_service import (
        batch_import,
        check_duplicate,
        process_document,
    )

    return types.SimpleNamespace(
        check_duplicate=check_duplicate,
        process_document=process_document,
        batch_import=batch_import,
    )


@pytest.fixture
def quiz_service_modules():
    _setup_agent("quiz-agent")
    from app.services.quiz_service import (
        _calculate_mastery_change,
        _get_knowledge_context,
        generate_quiz,
        submit_answer,
    )

    return types.SimpleNamespace(
        generate_quiz=generate_quiz,
        submit_answer=submit_answer,
        _get_knowledge_context=_get_knowledge_context,
        _calculate_mastery_change=_calculate_mastery_change,
    )


@pytest.fixture
def rag_service_modules():
    _setup_agent("rag-agent")
    from app.services.search_service import (
        SearchServiceResponse,
        get_knowledge_context,
        search_knowledge,
    )

    return types.SimpleNamespace(
        search_knowledge=search_knowledge,
        get_knowledge_context=get_knowledge_context,
        SearchServiceResponse=SearchServiceResponse,
    )


@pytest.fixture
def knowledge_api_modules():
    _setup_agent("knowledge-agent")
    from app.api.documents import router as documents_router

    return types.SimpleNamespace(documents_router=documents_router)


@pytest.fixture
def rag_api_modules():
    _setup_agent("rag-agent")
    from app.api.search import router as search_router

    return types.SimpleNamespace(search_router=search_router)
