import os
import secrets
import sys
from pathlib import Path
from typing import Any

import httpx
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.constants.app_groups import APP_GROUPS, APP_NAMES  # noqa: E402
from app.models.schemas import ReviewSortOrder  # noqa: E402

JsonDict = dict[str, Any]

BASIC_AUTH_USER = os.environ["BASIC_AUTH_USER"]
BASIC_AUTH_PASS = os.environ["BASIC_AUTH_PASS"]


def escape_latex(text: str) -> str:
    """Escape dollar signs so Streamlit markdown doesn't trigger LaTeX."""
    return text.replace("$", r"\$")


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = f"{API_BASE_URL}/api/v1"


def display_app_name(app_id: str) -> str:
    name = APP_NAMES.get(app_id)
    return f"{name} ({app_id})" if name else app_id


def api_auth() -> httpx.BasicAuth:
    return httpx.BasicAuth(BASIC_AUTH_USER, BASIC_AUTH_PASS)


def _api_get_raw(path: str) -> JsonDict | None:
    try:
        resp = httpx.get(f"{API_PREFIX}{path}", timeout=300.0, auth=api_auth())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def api_get(path: str) -> JsonDict | None:
    return _api_get_raw(path)


def ensure_reviews_collected(app_id: str, country: str, max_pages: int, sort_by: str) -> bool:
    """Auto-collect reviews if none exist. Returns True if reviews are available."""
    collected_key = f"collected_{app_id}"
    if st.session_state.get(collected_key):
        return True
    check = api_get(f"/metrics/{app_id}")
    if check and check.get("total_reviews", 0) > 0:
        st.session_state[collected_key] = True
        return True
    with st.spinner(f"Collecting reviews for {display_app_name(app_id)}..."):
        result = api_post(
            "/reviews/collect",
            {
                "app_id": app_id,
                "country": country,
                "max_pages": max_pages,
                "sort_by": sort_by,
            },
        )
        if result and result.get("collected", 0) > 0:
            api_get.clear()
            st.session_state[collected_key] = True
            st.success(
                f"Auto-collected {result['collected']} reviews for {display_app_name(app_id)}"
            )
            return True
    st.warning(f"No reviews found for {display_app_name(app_id)}")
    return False


def api_post(path: str, json_data: dict[str, Any]) -> JsonDict | None:
    try:
        resp = httpx.post(f"{API_PREFIX}{path}", json=json_data, timeout=300.0, auth=api_auth())
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


st.set_page_config(page_title="App Review Analysis", page_icon="\U0001f4ca", layout="wide")

if not st.session_state.get("authenticated"):
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        username_ok = secrets.compare_digest(username, BASIC_AUTH_USER)
        password_ok = secrets.compare_digest(password, BASIC_AUTH_PASS)
        if username_ok and password_ok:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

st.title("Apple Store Review Analysis")

with st.sidebar:
    st.header("Configuration")

    input_mode = st.radio("Select app by", ["Predefined app", "Custom ID"], horizontal=True)

    if input_mode == "Predefined app":
        group_name = st.selectbox("App group", list(APP_GROUPS.keys()))
        apps_in_group = APP_GROUPS[group_name]
        app_options = {f"{name} ({app_id})": app_id for name, app_id in apps_in_group}
        selected_label = st.selectbox("App", list(app_options.keys()))
        app_id = app_options[selected_label]
    else:
        group_name = list(APP_GROUPS.keys())[0]
        app_id = st.text_input("App ID", value="389801252", help="Apple App Store numeric ID")

    country = st.selectbox("Country", ["us", "gb", "de", "fr", "jp", "au", "ca"])

    sort_labels = {
        ReviewSortOrder.MOST_RECENT: "Most Recent",
        ReviewSortOrder.MOST_HELPFUL: "Most Helpful",
    }
    selected_sort_label = st.selectbox(
        "Sort reviews by",
        list(sort_labels.values()),
        help="How Apple sorts the reviews before returning them",
    )
    sort_by = next(k for k, v in sort_labels.items() if v == selected_sort_label)

    max_pages = st.number_input(
        "Pages to collect",
        min_value=1,
        max_value=10,
        value=10,
        help="Each page contains ~50 reviews",
    )

    if st.button("Collect Reviews", type="primary"):
        with st.spinner("Collecting reviews..."):
            result = api_post(
                "/reviews/collect",
                {
                    "app_id": app_id,
                    "country": country,
                    "max_pages": max_pages,
                    "sort_by": sort_by,
                },
            )
            if result:
                api_get.clear()
                st.session_state.pop(f"collected_{app_id}", None)
                st.success(
                    f"Collected {result['collected']} reviews "
                    f"({result['new']} new, {result['duplicates']} duplicates)"
                )

    st.divider()
    st.caption(f"Selected: **{display_app_name(app_id)}**")

has_reviews = ensure_reviews_collected(app_id, country, max_pages, sort_by)

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
    if not metrics:
        st.info("No reviews collected yet. Use the sidebar to collect reviews.")
    if metrics:
        col1, col2 = st.columns(2)
        col1.metric("Total Reviews", metrics["total_reviews"])
        col2.metric("Average Rating", f"{metrics['average_rating']:.2f}/5")

        dist = metrics["rating_distribution"]
        fig = px.bar(
            dist,
            x="rating",
            y="count",
            title=f"Rating Distribution — {display_app_name(app_id)}",
            labels={"rating": "Stars", "count": "Count"},
            color="rating",
        )
        st.plotly_chart(fig, width="stretch")

with tab_sentiment:
    sentiment = api_get(f"/sentiment/{app_id}")
    if not sentiment:
        st.info("No sentiment data available. Collect reviews first.")
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
        st.plotly_chart(fig, width="stretch")

with tab_aspects:
    aspects = api_get(f"/aspects/{app_id}")
    if not aspects:
        st.info("No aspect data available. Collect reviews first.")
    if aspects and aspects["aspects"]:
        fig = px.bar(
            aspects["aspects"],
            x="category",
            y="sentiment_score",
            color="sentiment_label",
            title="Aspect-Based Sentiment",
            labels={"category": "Aspect", "sentiment_score": "Sentiment Score"},
        )
        st.plotly_chart(fig, width="stretch")

        for aspect in aspects["aspects"]:
            with st.expander(f"{aspect['category']} ({aspect['mention_count']} mentions)"):
                st.write(f"Score: {aspect['sentiment_score']:.3f} ({aspect['sentiment_label']})")
                st.write(escape_latex(f"Sample phrases: {', '.join(aspect['sample_phrases'])}"))

with tab_keywords:
    insights = api_get(f"/insights/{app_id}")
    if not insights:
        st.info("No keyword data available. Collect reviews first.")
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
                st.plotly_chart(fig, width="stretch")

        for insight in insights["insights"]:
            severity_color = {
                "high": "\U0001f534",
                "medium": "\U0001f7e1",
                "low": "\U0001f7e2",
            }.get(insight["severity"], "\u26aa")
            st.write(
                escape_latex(
                    f"{severity_color} **[{insight['severity'].upper()}]** {insight['message']}"
                )
            )

        st.divider()
        if st.button("Generate Actionable Insights", type="primary", key="gen_narrative"):
            with st.spinner("Generating narrative via LLM..."):
                narrative_result = api_post(f"/insights/{app_id}/narrative", {})
                if narrative_result and narrative_result.get("narrative"):
                    st.subheader("Actionable Recommendations")
                    st.write(escape_latex(narrative_result["narrative"]))
                else:
                    st.warning(
                        "Could not generate narrative. "
                        "Check that OPENROUTER_API_KEY is configured."
                    )

with tab_rag:
    st.subheader("Ask questions about reviews")

    if st.button("Auto-suggest questions", type="secondary", key="rag_suggest"):
        with st.spinner("Generating question suggestions..."):
            suggest_result = api_post(
                "/rag/suggest-questions",
                {"app_id": app_id, "num_questions": 5},
            )
            if suggest_result and suggest_result.get("questions"):
                st.session_state["rag_suggested_questions"] = suggest_result["questions"]
            else:
                st.warning(
                    "Could not generate suggestions. Check that OPENROUTER_API_KEY is configured."
                )

    if "rag_question" not in st.session_state:
        st.session_state["rag_question"] = ""

    if st.session_state.get("rag_suggested_questions"):
        st.caption("Suggested questions (click to select):")
        for i, q in enumerate(st.session_state["rag_suggested_questions"]):
            st.button(
                q,
                key=f"rag_suggestion_{i}",
                use_container_width=True,
                on_click=lambda selected=q: st.session_state.update(rag_question=selected),
            )

    question = st.text_input(
        "Your question",
        key="rag_question",
        placeholder="What do users complain about most?",
    )
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
                st.session_state["rag_last_result"] = result

    rag_result = st.session_state.get("rag_last_result")
    if rag_result:
        st.subheader("Answer")
        if rag_result["answer"]:
            st.write(escape_latex(rag_result["answer"]))
            st.caption(f"Generated by: {rag_result['model_used']} (mode: {rag_result['mode']})")
        else:
            st.warning("Could not generate an answer. Try rephrasing or click Regenerate.")
        if st.button("Regenerate", key="rag_regenerate"):
            with st.spinner("Regenerating..."):
                retry = api_post(
                    "/rag/query",
                    {
                        "app_id": rag_result["app_id"],
                        "question": rag_result["question"],
                        "top_k": len(rag_result["sources"]),
                    },
                )
                if retry:
                    st.session_state["rag_last_result"] = retry
                    st.rerun()

        st.subheader("Source Reviews")
        for source in rag_result["sources"]:
            with st.expander(
                f"Review {source['review_id']} "
                f"(Rating: {source['rating']}/5, "
                f"Similarity: {source['similarity_score']:.3f})"
            ):
                st.text(source["content"])

with tab_competitive:
    st.subheader("Compare multiple apps")

    compare_mode = st.radio(
        "Select apps by", ["Predefined group", "Custom IDs"], horizontal=True, key="compare_mode"
    )

    if compare_mode == "Predefined group":
        st.session_state["compare_group"] = group_name
        compare_apps = APP_GROUPS[group_name]
        compare_ids_list = [app_id_val for _, app_id_val in compare_apps]
        st.caption("Apps: " + ", ".join(f"{name} ({aid})" for name, aid in compare_apps))
    else:
        compare_ids_input = st.text_input(
            "App IDs (comma-separated)",
            placeholder="389801252,310633997",
        )
        compare_ids_list = (
            [x.strip() for x in compare_ids_input.split(",") if x.strip()]
            if compare_ids_input
            else []
        )

    if st.button("Compare") and compare_ids_list:
        if len(compare_ids_list) < 2:
            st.error("Need at least 2 apps to compare")
        else:
            with st.spinner("Comparing apps..."):
                result = api_post(
                    "/competitive/compare",
                    {"app_ids": compare_ids_list, "country": country},
                )
                if result:
                    cols = st.columns(len(result["apps"]))
                    for col, app_data in zip(cols, result["apps"], strict=True):
                        with col:
                            st.metric("App", display_app_name(app_data["app_id"]))
                            st.metric("Avg Rating", f"{app_data['average_rating']:.2f}")
                            st.metric("Avg Sentiment", f"{app_data['average_sentiment']:.3f}")
                            st.write(
                                escape_latex(
                                    "**Keywords:** " + ", ".join(app_data["top_keywords"][:5])
                                )
                            )

                    st.subheader("Insights")
                    for insight in result["insights"]:
                        st.write(escape_latex(f"- {insight}"))
