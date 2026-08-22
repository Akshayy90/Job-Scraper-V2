from datetime import datetime

import pandas as pd
import streamlit as st

from scraper.config import get_settings
from scraper.pipeline import run_pipeline
from scraper.sheets import GoogleSheetsClient

st.set_page_config(page_title="Job Scraper", page_icon="💼", layout="wide")
st.title("💼 Multi-Site Job Scraper")
st.caption("Playwright → Site Adapter → Normalize → Preview → Google Sheets")

settings = get_settings()

with st.sidebar:
    st.header("Configuration")
    st.write(f"**Targets:** {len(settings.target_urls)}")
    st.write(f"**Headless:** `{settings.headless}`")
    st.write(f"**Max pages/site:** `{settings.max_pages_per_target}`")
    st.write(f"**Max jobs/site:** `{settings.max_jobs_per_target}`")
    st.write(f"**Debug:** `{settings.debug}`")
    st.divider()
    for i, url in enumerate(settings.target_urls, start=1):
        st.caption(f"{i}. {url}")
    st.info("Edit `.env` to change target URLs and Google Sheets settings.")

if not settings.target_urls:
    st.error("No TARGET_URLS configured in .env.")
    st.stop()

if "jobs" not in st.session_state:
    st.session_state.jobs = []

col1, col2 = st.columns(2)
with col1:
    scrape_clicked = st.button("🚀 Run Scraper", type="primary", use_container_width=True)
with col2:
    sync_clicked = st.button("📤 Run Scraper + Sync Sheets", use_container_width=True)

if scrape_clicked or sync_clicked:
    with st.spinner("Launching Playwright and scraping real source data..."):
        try:
            jobs = run_pipeline(settings)
            st.session_state.jobs = jobs
            st.success(f"Scraped {len(jobs)} normalized job records.")
        except Exception as exc:
            st.exception(exc)
            st.stop()

    if sync_clicked:
        try:
            client = GoogleSheetsClient(settings)
            result = client.upsert_jobs(st.session_state.jobs)
            st.success(
                f"Google Sheets updated: {result['added']} added, "
                f"{result['updated']} updated, {result['total']} total."
            )
        except Exception as exc:
            st.error("Scraping succeeded, but Google Sheets sync failed.")
            st.exception(exc)

jobs = st.session_state.jobs

if jobs:
    df = pd.DataFrame([job.to_dict() for job in jobs])
    st.subheader("Scraped Output")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jobs", len(df))
    m2.metric("Sites", df["Source"].nunique() if "Source" in df else 0)
    m3.metric("Companies", df["Company Name"].nunique())
    m4.metric("Checked", datetime.now().strftime("%Y-%m-%d %H:%M"))

    display_columns = [
        "Company Name", "Role", "Link", "Location",
        "Date Added", "Deadline", "Status", "Last Checked",
    ]
    visible = [c for c in display_columns if c in df.columns]
    st.dataframe(
        df[visible],
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link")},
    )

    csv = df[visible].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="jobs.csv",
        mime="text/csv",
    )
else:
    st.info("Click **Run Scraper** to display live scraped jobs here.")

st.divider()
st.caption("CLI: python cli.py run --sync")
