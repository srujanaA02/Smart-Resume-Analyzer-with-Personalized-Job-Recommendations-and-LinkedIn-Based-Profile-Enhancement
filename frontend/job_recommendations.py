import streamlit as st
import pandas as pd
from backend.auth import get_logged_in_user_id
from backend.scraper import LinkedInJobScraper
from utils.database import get_job_recommendations
import time

def recommendations_page():
    st.markdown("""
        <style>
        .job-card {
            background-color: #1e1e1e;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 1px solid #333;
            position: relative;
        }
        .job-title {
            color: #00ADB5;
            font-size: 1.2rem;
            font-weight: bold;
            text-decoration: none;
        }
        .company-name {
            color: #EEEEEE;
            font-size: 1rem;
            margin-top: 5px;
        }
        .job-location {
            color: #AAAAAA;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }
        .match-score {
            background-color: #00ADB5;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            float: right;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("Job Recommendations")
    
    user_id = get_logged_in_user_id()
    if not user_id:
        st.error("Please log in to view recommendations.")
        return

    # Search Preferences
    st.subheader("Search Preferences")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        keywords = st.text_input("Keywords (e.g., Python Developer)", value="")
    with col2:
        location = st.text_input("Location (e.g., Remote)", value="")
    with col3:
        limit = st.number_input("Max Jobs", min_value=1, max_value=50, value=5, step=1)
    
    # st.subheader("Filters (Coming Soon)")
    # st.checkbox("Date Posted (Last 24h)", disabled=True)
    # st.checkbox("Remote Only", value=True, disabled=True)

    if st.button("Search & Scrape Jobs", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total, eta):
            progress = min(current / total, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Scraped {current}/{total} jobs. Estimated time remaining: {eta}")

        try:
            status_text.text("Initializing scraper...")
            scraper = LinkedInJobScraper(user_id=user_id, headless=False) # Headless=False for debugging/safety
            
            # Login logic handling (assuming env vars set)
            import os
            email = os.getenv("LINKEDIN_EMAIL")
            password = os.getenv("LINKEDIN_PASSWORD")
            
            if scraper.login(email, password):
                status_text.text("Logged in. Starting search...")
                search_term = keywords if keywords else "Software Engineer"
                scraper.search_jobs(search_term, location, limit=limit, progress_callback=update_progress)
                status_text.text("Scraping completed!")
                progress_bar.progress(1.0)
                st.success("Scraping completed!")
                time.sleep(1) 
                st.rerun()
            else:
                st.error("Failed to login to LinkedIn scraper.")
        except Exception as e:
            st.error(f"Scraping failed: {e}")
        finally:
            if 'scraper' in locals():
                scraper.close()

    # Display Jobs
    st.subheader("Recommended Opportunities")
    
    jobs = get_job_recommendations(user_id, limit=None)
    
    if not jobs:
        st.info("No jobs found. Try running a scrape!")
    else:
        for i, job in enumerate(jobs, 1):
            st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
                    <div style="min-width: 40px; font-size: 1.8rem; font-weight: bold; color: #00ADB5; text-align: right;">{i}</div>
                    <div class="job-card" style="flex: 1; margin-bottom: 0;">
                        <span class="match-score">Match: {int(job.get('match_percentage', 0))}%</span>
                        <a href="{job['job_url']}" target="_blank" class="job-title">{job['job_title']}</a>
                    <div class="company-name">{job['company_name']}</div>
                    <div class="job-location">📍 {job['location']}</div>
                    <div class="job-location" style="font-size: 0.8rem; color: #888;">📅 Posted: {job.get('posted_date', 'Unknown') or 'Unknown'}</div>
                    <hr style="border-color: #333; margin: 10px 0;">
                    <div style="color: #CCCCCC; font-size: 0.9rem;">
                        {job['job_description'][:200]}...
                    </div>
                </div>
            """, unsafe_allow_html=True)
