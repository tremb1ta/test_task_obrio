import os
from typing import Any

import httpx
import plotly.express as px
import streamlit as st

JsonDict = dict[str, Any]

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = f"{API_BASE_URL}/api/v1"


def api_get(path: str) -> JsonDict | None:
    try:
        resp = httpx.get(f"{API_PREFIX}{path}", timeout=60.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json_data: dict[str, Any]) -> JsonDict | None:
    try:
        resp = httpx.post(f"{API_PREFIX}{path}", json=json_data, timeout=120.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


st.set_page_config(page_title="App Review Analysis", page_icon="📊", layout="wide")
st.title("Apple Store Review Analysis")

with st.sidebar:
    st.header("Configuration")
    app_id = st.text_input("App ID", value="389801252", help="Apple App Store numeric ID")
    country = st.selectbox("Country", ["us", "gb", "de", "fr", "jp", "au", "ca"])

    if st.button("Collect Reviews", type="primary"):
        with st.spinner("Collecting reviews..."):
            result = api_post("/reviews/collect", {"app_id": app_id, "country": country})
            if result:
                st.success(
                    f"Collected {result['collected']} reviews "
                    f"({result['new']} new, {result['duplicates']} duplicates)"
                )

tab_overview, tab_sentiment, tab_aspects, tab_keywords, tab_rag, tab_competitive = st.tabs(
    [
        "Overview",
        "Sentiment",
        "Aspects",
        "Keywords",
        "RAG Q&A",
        "Competitive",
    ]
)

with tab_overview:
    metrics = api_get(f"/metrics/{app_id}")
    if metrics:
        col1, col2 = st.columns(2)
        col1.metric("Total Reviews", metrics["total_reviews"])
        col2.metric("Average Rating", f"{metrics['average_rating']:.2f}/5")

        dist = metrics["rating_distribution"]
        fig = px.bar(
            dist,
            x="rating",
            y="count",
            title="Rating Distribution",
            labels={"rating": "Stars", "count": "Count"},
            color="rating",
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_sentiment:
    sentiment = api_get(f"/sentiment/{app_id}")
    if sentiment:
        st.subheader(f"Analyzed {sentiment['total_analyzed']} reviews")

        for method, summary in sentiment["summaries"].items():
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(f"{method.upper()} Positive", summary["positive"])
            col2.metric(f"{method.upper()} Negative", summary["negative"])
            col3.metric(f"{method.upper()} Neutral", summary["neutral"])
            col4.metric(f"{method.upper()} Avg Score", f"{summary['average_score']:.3f}")

        fig = px.pie(
            values=[
                sentiment["summaries"]["vader"]["positive"],
                sentiment["summaries"]["vader"]["negative"],
                sentiment["summaries"]["vader"]["neutral"],
            ],
            names=["Positive", "Negative", "Neutral"],
            title="VADER Sentiment Distribution",
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_aspects:
    aspects = api_get(f"/aspects/{app_id}")
    if aspects and aspects["aspects"]:
        fig = px.bar(
            aspects["aspects"],
            x="category",
            y="sentiment_score",
            color="sentiment_label",
            title="Aspect-Based Sentiment",
            labels={"category": "Aspect", "sentiment_score": "Sentiment Score"},
        )
        st.plotly_chart(fig, use_container_width=True)

        for aspect in aspects["aspects"]:
            with st.expander(f"{aspect['category']} ({aspect['mention_count']} mentions)"):
                st.write(f"Score: {aspect['sentiment_score']:.3f} ({aspect['sentiment_label']})")
                st.write(f"Sample phrases: {', '.join(aspect['sample_phrases'])}")

with tab_keywords:
    insights = api_get(f"/insights/{app_id}")
    if insights:
        keyword_insights = [
            i for i in insights["insights"] if i["category"] == "negative_keywords"
        ]
        if keyword_insights:
            keywords_data = [
                {
                    "keyword": i["affected_aspect"],
                    "relevance": float(i["message"].split("relevance: ")[1].rstrip(").")),
                }
                for i in keyword_insights
                if "relevance:" in i["message"]
            ]
            if keywords_data:
                fig = px.bar(
                    keywords_data,
                    x="relevance",
                    y="keyword",
                    orientation="h",
                    title="Top Negative Keywords",
                )
                st.plotly_chart(fig, use_container_width=True)

        for insight in insights["insights"]:
            severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                insight["severity"], "⚪"
            )
            st.write(f"{severity_color} **[{insight['severity'].upper()}]** {insight['message']}")

with tab_rag:
    st.subheader("Ask questions about reviews")
    question = st.text_input("Your question", placeholder="What do users complain about most?")
    top_k = st.slider("Number of source reviews", 1, 20, 5)

    if st.button("Ask") and question:
        with st.spinner("Querying..."):
            result = api_post(
                "/rag/query",
                {
                    "app_id": app_id,
                    "question": question,
                    "top_k": top_k,
                },
            )
            if result:
                st.subheader("Answer")
                if result["answer"]:
                    st.write(result["answer"])
                    st.caption(f"Generated by: {result['model_used']} (mode: {result['mode']})")
                else:
                    st.info("No generated answer (retrieval-only mode)")

                st.subheader("Source Reviews")
                for source in result["sources"]:
                    with st.expander(
                        f"Review {source['review_id']} "
                        f"(Rating: {source['rating']}/5, "
                        f"Similarity: {source['similarity_score']:.3f})"
                    ):
                        st.write(source["content"])

with tab_competitive:
    st.subheader("Compare multiple apps")
    compare_ids = st.text_input(
        "App IDs (comma-separated)",
        placeholder="389801252,310633997",
    )

    if st.button("Compare") and compare_ids:
        ids = [x.strip() for x in compare_ids.split(",") if x.strip()]
        if len(ids) < 2:
            st.error("Enter at least 2 app IDs")
        else:
            with st.spinner("Comparing apps..."):
                result = api_post("/competitive/compare", {"app_ids": ids, "country": country})
                if result:
                    cols = st.columns(len(result["apps"]))
                    for col, app_data in zip(cols, result["apps"], strict=True):
                        with col:
                            st.metric("App ID", app_data["app_id"])
                            st.metric("Avg Rating", f"{app_data['average_rating']:.2f}")
                            st.metric("Avg Sentiment", f"{app_data['average_sentiment']:.3f}")
                            st.write("**Keywords:**", ", ".join(app_data["top_keywords"][:5]))

                    st.subheader("Insights")
                    for insight in result["insights"]:
                        st.write(f"- {insight}")
