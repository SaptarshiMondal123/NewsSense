import streamlit as st
import requests
import time
import re
import os
import json
from config import *
from langchain_community.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage

st.set_page_config(page_title="NewsSense", page_icon="📰")

# Step 1: Setup LangChain LLM
llm = AzureChatOpenAI(
    openai_api_base=AZURE_OPENAI_ENDPOINT,
    openai_api_version=AZURE_OPENAI_API_VERSION,
    deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
    openai_api_key=AZURE_OPENAI_API_KEY,
    openai_api_type="azure",
    temperature=0.3,
)

# Step 2: UI Input
st.title("📰 NewsSense: Your Autonomous News Agent")
user_interest = st.text_input("Enter your interests (comma-separated):")

# Step 3: File-based Cache
CACHE_FILE = "news_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

# Step 4: Fetch News
def fetch_news():
    query = user_interest.replace(",", " OR ")
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=30&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    return response.json().get("articles", [])

# Step 5: GPT Summarize + Score
def summarize_and_score(article, interest):
    title = article.get("title", "")
    description = article.get("description", "")
    url = article.get("url", "")

    prompt = f"""You are a helpful assistant.

Here's a news article:

Title: {title}
Description: {description}

Summarize it in 2–3 lines. Then rate how relevant it is to the user's interest: "{interest}" on a scale from 0 to 10.

Return this format:
Summary: <summary>
Relevance Score: <number only, 0 to 10>
"""
    response = llm([HumanMessage(content=prompt)])
    output = response.content.strip()

    summary = "Summary not found"
    score = 0
    summary_match = re.search(r"Summary:\s*(.*)", output)
    score_match = re.search(r"Relevance Score:\s*(\d+)", output)

    if summary_match:
        summary = summary_match.group(1).strip()
    if score_match:
        score = int(score_match.group(1).strip())

    return {
        "title": title,
        "summary": summary,
        "score": score,
        "url": url
    }

# Step 6: Display Results
def display_results(results):
    for i, res in enumerate(results, 1):
        st.markdown("---")
        st.subheader(f"{i}. {res['title']}")
        st.write(f"**Summary:** {res['summary']}")
        st.write(f"**Relevance Score:** {res['score']}/10")
        st.markdown(f"[Read More]({res['url']})")

# Step 7: Main Logic
if st.button("Fetch & Analyze News"):
    cache = load_cache()
    key = user_interest.lower().strip()

    if key in cache and len(cache[key]) >= 12:
        display_results(cache[key])
    else:
        st.info("🔄 Fetching fresh articles and generating summaries...")
        articles = fetch_news()
        seen_titles = set()
        relevant_results = []
        max_to_process = 30

        if not articles:
            st.warning("No news articles found.")
        else:
            with st.spinner("Analyzing articles..."):
                for idx, article in enumerate(articles):
                    if len(relevant_results) >= 12 or idx >= max_to_process:
                        break

                    title = article.get("title", "").strip()
                    if not title or title in seen_titles:
                        continue

                    try:
                        result = summarize_and_score(article, user_interest)

                        if result["score"] >= 5:
                            seen_titles.add(title)
                            relevant_results.append(result)
                            st.markdown("---")
                            st.subheader(f"{len(relevant_results)}. {result['title']}")
                            st.write(f"**Summary:** {result['summary']}")
                            st.write(f"**Relevance Score:** {result['score']}/10")
                            st.markdown(f"[Read More]({result['url']})")

                        time.sleep(6)

                    except Exception as e:
                        st.error(f"Error: {e}")

            # Save to cache
            if relevant_results:
                cache[key] = relevant_results
                save_cache(cache)
                st.success("✅ Results cached for future use.")
