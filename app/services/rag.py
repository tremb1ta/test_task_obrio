import logging

import chromadb
import httpx
from sentence_transformers import SentenceTransformer

from app.config import Settings

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, embedding_model: SentenceTransformer, settings: Settings):
        self._embedding_model = embedding_model
        self._settings = settings
        self._chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    def _get_collection(self, app_id: str):
        return self._chroma_client.get_or_create_collection(
            name=f"reviews_{app_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def index_reviews(self, app_id: str, reviews: list[dict]) -> int:
        if not reviews:
            return 0

        collection = self._get_collection(app_id)
        texts = [r.get("content", "") for r in reviews]
        ids = [str(r.get("review_id", i)) for i, r in enumerate(reviews)]
        metadatas = [
            {
                "rating": r.get("rating", 0),
                "review_id": str(r.get("review_id", "")),
                "app_id": app_id,
                "vader_label": r.get("vader_label", ""),
            }
            for r in reviews
        ]

        embeddings = self._embedding_model.encode(texts, batch_size=64).tolist()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,  # type: ignore[arg-type]
        )
        logger.info("Indexed %d reviews for app_id=%s", len(reviews), app_id)
        return len(reviews)

    def retrieve(
        self,
        app_id: str,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        collection = self._get_collection(app_id)
        query_embedding = self._embedding_model.encode([query]).tolist()

        kwargs: dict = {
            "query_embeddings": query_embedding,
            "n_results": min(top_k, collection.count() or 1),
        }
        if filters:
            kwargs["where"] = filters

        try:
            results = collection.query(**kwargs)
        except Exception:
            logger.exception("ChromaDB query failed for app_id=%s", app_id)
            return []

        retrieved = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                retrieved.append(
                    {
                        "review_id": meta.get("review_id", ""),
                        "content": doc,
                        "rating": meta.get("rating", 0),
                        "similarity_score": round(1.0 - distance, 4),
                    }
                )
        return retrieved

    async def generate_answer(self, query: str, retrieved_reviews: list[dict]) -> dict:
        if not self._settings.openrouter_api_key:
            return {
                "answer": None,
                "model_used": None,
                "mode": "retrieval_only",
            }

        context = "\n".join(
            f'Review {i + 1} (Rating: {r["rating"]}/5): "{r["content"]}"'
            for i, r in enumerate(retrieved_reviews)
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an app review analyst. Answer questions based strictly on "
                    "the provided user reviews. Cite specific reviews when possible. "
                    "Be concise and factual."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Based on these user reviews:\n\n{context}\n\n"
                    f"Question: {query}\n\nProvide a concise, evidence-based answer."
                ),
            },
        ]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._settings.openrouter_model,
                        "messages": messages,
                        "max_tokens": self._settings.openrouter_max_tokens,
                        "temperature": self._settings.openrouter_temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                return {
                    "answer": answer,
                    "model_used": self._settings.openrouter_model,
                    "mode": "rag",
                }
        except Exception:
            logger.exception("OpenRouter call failed, returning retrieval-only")
            return {
                "answer": None,
                "model_used": None,
                "mode": "retrieval_only",
            }

    async def query(self, app_id: str, question: str, top_k: int = 5) -> dict:
        retrieved = self.retrieve(app_id, question, top_k)
        generation = await self.generate_answer(question, retrieved)
        return {
            "app_id": app_id,
            "question": question,
            "answer": generation["answer"],
            "model_used": generation["model_used"],
            "mode": generation["mode"],
            "sources": retrieved,
        }
