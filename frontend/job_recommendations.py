import streamlit as st
import pandas as pd
from backend.auth import get_logged_in_user_id
from backend.scraper import LinkedInJobScraper
from utils.database import get_job_recommendations
from backend.recommendations import JobRecommender
import time
import textwrap
import math

def recommendations_page():
    st.markdown("""
        <style>
        .job-card {
            background-color: #1e1e1e;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            border: 1px solid #333;
            position: relative;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .job-card:hover {
            transform: translateY(-5px);
            border-color: #00ADB5;
            box-shadow: 0 8px 15px rgba(0,173,181,0.1);
        }
        .job-title {
            color: #00ADB5;
            font-size: 1.4rem;
            font-weight: bold;
            text-decoration: none;
            line-height: 1.2;
        }
        .job-title:hover {
            text-decoration: underline;
        }
        .company-name {
            color: #EEEEEE;
            font-size: 1.1rem;
            margin-top: 8px;
            font-weight: 500;
        }
        .job-location {
            color: #AAAAAA;
            font-size: 0.95rem;
            margin-top: 5px;
        }
        .match-score {
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: bold;
            border: 1.5px solid transparent;
            background:
                linear-gradient(#1e1e1e, #1e1e1e) padding-box,
                linear-gradient(90deg, #00ADB5, #00c853) border-box;
        }
        .job-container {
            max-width: 900px;
            margin: 0 auto;
        }

        </style>
    """, unsafe_allow_html=True)
    
    st.title("Job Recommendations")
    
    user_id = get_logged_in_user_id()
    if not user_id:
        st.warning("Please log in to view recommendations.")
        return

    # Initialize Recommender
    try:
        recommender = JobRecommender()
    except ImportError:
        st.error("Backend module error.")
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

    # --- STATS SUMMARY (Placeholders) ---
    raw_jobs = get_job_recommendations(user_id, limit=None)
    
    st.markdown("### 📊 Overview")
    k1, k2, k3 = st.columns(3)
    metric_found = k1.empty()
    metric_score = k2.empty()
    metric_new = k3.empty()
    
    # Initialize defaults
    metric_found.metric("Opportunities Found", 0)
    metric_score.metric("Avg Match Score", "0%")
    metric_new.metric("New Today", 0)

    st.markdown("---")

    # --- MAIN LAYOUT ---
    col_main, col_right = st.columns([3, 1])

    # --- RIGHT PANEL FILTERS ---
    with col_right:
        st.subheader("🔍 Filters")
        
        # 1. Location
        all_locs = sorted(list(set([j['location'] for j in raw_jobs]))) if raw_jobs else []
        sel_locs = st.multiselect("Location", all_locs)
        remote_only = st.checkbox("Remote Only", value=True)

        # 2. Match Score
        min_match = st.slider("Min Match %", 0, 100, 0, 5) # Default 0 to see all jobs if scoring fails

        # 3. Job Type (Mock data for now if not in scraper)
        job_types = ["Full-time", "Contract", "Internship", "Part-time"]
        sel_types = st.multiselect("Job Type", job_types, default=["Full-time"])

        # 4. Experience
        exp_levels = ["Entry Level", "Mid Level", "Senior Level", "Director"]
        sel_exp = st.selectbox("Experience Level", ["Any"] + exp_levels)

        # 5. Date Posted
        date_opts = {"Any": 0, "Last 24 Hours": 1, "Last 7 Days": 7, "Last 30 Days": 30}
        sel_date = st.selectbox("Date Posted", list(date_opts.keys()))
 

    # --- MAIN CONTENT ---
    with col_main:
        # Processing Logic
        filters = {
            "locations": sel_locs,
            "remote": remote_only,
            "min_match_score": min_match,
            "job_type": sel_types,
            "experience_level": sel_exp if sel_exp != "Any" else None,
            "date_posted_days": date_opts[sel_date]
        }
        
        # 1. Processing
        processed_jobs = recommender.filter_and_score_jobs(user_id, raw_jobs, filters)
        
        # Persist updated match scores to DB so they are valid for future queries
        if processed_jobs:
             from utils.database import update_job_match_scores
             updates = [(j['id'], j['match_percentage']) for j in processed_jobs]
             update_job_match_scores(user_id, updates)
        
        # UPDATE STATS with real values
        p_count = len(processed_jobs)
        p_avg = int(sum(j.get('match_percentage', 0) for j in processed_jobs)/p_count) if p_count > 0 else 0
        p_new = len([j for j in processed_jobs if "hour" in str(j.get('posted_date', '')).lower() or "minute" in str(j.get('posted_date', '')).lower()])
        
        metric_found.metric("Opportunities Found", p_count)
        metric_score.metric("Avg Match Score", f"{p_avg}%")
        metric_new.metric("New Today", p_new)
        
        if p_count > 0 and p_avg == 0:
            st.warning("⚠️ Match scores are 0%. Please ensuring you have uploaded and analyzed your resume in the Dashboard so we can calculate matches.")
        
        # Sorting
        sort_opts = {
            "Best Match": "match_percentage",
            "Recency": "posted_date", 
            "Applicants (Low to High)": "applicant_count" 
        }
        sort_by = st.selectbox("Sort By", list(sort_opts.keys()))
        
        if sort_by == "Best Match":
            processed_jobs.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
        elif sort_by == "Applicants (Low to High)":
            processed_jobs.sort(key=lambda x: x.get('applicant_count', 9999))
            
        grouped_jobs = recommender.group_jobs(processed_jobs)

        # Tabs Layout inside Main Column
        tab_rec, tab_saved, tab_compare = st.tabs(["Recommended Jobs", "My Allocations", "Compare Jobs"])

        with tab_rec:
            # 2. Group Display
            st.write(f"Showing {len(processed_jobs)} jobs matching criteria.")
                
            # Featured Section (Always Top)
            if grouped_jobs["Featured"]:
                st.subheader("🔥 Featured & Urgent")
                for job in grouped_jobs["Featured"]:
                    _render_job_card(job, recommender, user_id, is_featured=True, key_suffix="feat")
                st.markdown("---")
            
            # Main Content - Unified List with Pagination
            main_list = [j for j in processed_jobs if j not in grouped_jobs.get("Featured", [])] 
            
            if not main_list:
                st.info("No matching jobs found.")
            else:
                items_per_page = 20
                if "job_rec_page_index" not in st.session_state: st.session_state.job_rec_page_index = 0
                
                # Dynamic Pagination Reset
                if st.session_state.job_rec_page_index * items_per_page >= len(main_list):
                    st.session_state.job_rec_page_index = 0
                
                total_pages = max(1, math.ceil(len(main_list) / items_per_page))
                current_page = st.session_state.job_rec_page_index
                
                start_idx = current_page * items_per_page
                end_idx = start_idx + items_per_page
                page_jobs = main_list[start_idx:end_idx]
                
                for job in page_jobs:
                        _render_job_card(job, recommender, user_id, key_suffix="main")
                
                # Pagination Controls
                if total_pages > 1:
                    c_prev, c_cent, c_next = st.columns([1, 2, 1])
                    with c_prev:
                        if st.button("Previous", disabled=(current_page == 0)):
                            st.session_state.job_rec_page_index -= 1
                            st.rerun()
                    with c_next:
                        if st.button("Next", disabled=(current_page >= total_pages - 1)):
                            st.session_state.job_rec_page_index += 1
                            st.rerun()
                    with c_cent:
                        st.markdown(f"<div style='text-align: center; padding-top: 10px;'>Page {current_page + 1} of {total_pages}</div>", unsafe_allow_html=True)

        with tab_saved:
            st.subheader("Tracked Applications")
            saved_jobs = [j for j in raw_jobs if j.get('status') in ['saved', 'applied', 'interviewing', 'rejected']]
            if not saved_jobs:
                st.info("You haven't saved any jobs yet.")
            else:
                for job in saved_jobs:
                    st.markdown(f"**{job['job_title']}** at {job['company_name']} - Status: `{job.get('status')}`")
                    # Expandable management for status
                    with st.expander("Manage"):
                        new_status = st.selectbox("Update Status", ["saved", "applied", "interviewing", "rejected"], key=f"status_{job['id']}")
                        if st.button("Update", key=f"upd_{job['id']}"):
                            from utils.database import update_job_status
                            update_job_status(user_id, job['id'], new_status)
                            st.rerun()

        with tab_compare:
            st.subheader("Compare Jobs")
            selected_names = []
            if not raw_jobs:
                st.info("No jobs to compare.")
            else:
                # Multi-select
                job_options = {f"{j['job_title']} @ {j['company_name']}": j for j in raw_jobs}
                selected_names = st.multiselect("Select jobs to compare (2-4 recommended)", list(job_options.keys()))
            
            if selected_names:
                selected_jobs = [job_options[n] for n in selected_names]
                
                # Comparison Table Data
                comp_data = []
                for j in selected_jobs:
                    analysis = j.get('job_analysis', {})
                    scores = j.get('match_scores', {})
                    comp_data.append({
                        "Job Title": j['job_title'],
                        "Company": j['company_name'],
                        "Match Score": f"{int(j.get('match_percentage', 0))}%",
                        "Location": j['location'],
                        "Salary": analysis.get('salary_range', 'Not listed'),
                        "Experience": f"{analysis.get('required_experience_years', '?')} years",
                        "Applicants": j.get('applicant_count', '?'),
                        "Skills Match": f"{int(scores.get('skills_score', 0))}%"
                    })
                
                df = pd.DataFrame(comp_data)
                st.table(df)


def _render_job_card(job, recommender, user_id, is_featured=False, key_suffix=""):
    """Helper to render a single job card with actions."""
    # Styles
    border_color = "#FFD700" if is_featured else "#333"
    bg_color = "#1e1e1e" 
    
    scores = job.get('match_scores', {})
    
    # Progress Bar Color
    match_pct = int(job.get('match_percentage', 0))
    bar_color = "#00c853" if match_pct > 80 else "#FFD700" if match_pct > 60 else "#FF5252"
    
    clean_desc = (job.get('job_description', '') or '').replace("About the job", "").strip()
    short_desc = clean_desc[:250] + "..." if len(clean_desc) > 250 else clean_desc

    # HTML Card
    card_html = f"""<div class="job-card" style="border-color: {border_color}; background-color: {bg_color}; margin-bottom: 20px; padding: 20px; border-radius: 10px; border: 1px solid #333;">"""
    card_html += f"""<div style="display: flex; justify-content: space-between;">"""
    card_html += f"""<div><a href="{job['job_url']}" target="_blank" style="color: #00ADB5; font-size: 1.2rem; font-weight: bold; text-decoration: none;">{job['job_title']}</a>"""
    card_html += f"""<div style="color: #EEE;">{job['company_name']}</div></div>"""
    card_html += f"""<div style="text-align: right;"><span style="color: {bar_color}; font-weight: bold; font-size: 1.2rem;">{match_pct}% Match</span></div></div>"""
    
    # Visual Progress Bar
    card_html += f"""<div style="width: 100%; background-color: #444; height: 6px; border-radius: 3px; margin-top: 5px;">"""
    card_html += f"""<div style="width: {match_pct}%; background-color: {bar_color}; height: 6px; border-radius: 3px;"></div></div>"""
    
    card_html += f"""<div style="margin-top: 10px; color: #AAA; font-size: 0.9rem;">📍 {job['location']} | 👥 {job.get('applicant_count', 0)} Applicants | 📅 {job.get('posted_date', 'N/A')}</div>"""
    card_html += f"""<div style="margin-top: 10px; color: #CCC; font-size: 0.9rem; line-height: 1.5;">{short_desc}</div>"""
    card_html += f"""</div>"""

    st.markdown(card_html, unsafe_allow_html=True)
    
    # Actions
    unique_key = f"{job['id']}_{key_suffix}"

            
    with st.expander("Show Details & Analysis"):
        st.write(f"**Match Analysis**: {scores.get('match_analysis', 'N/A')}")
        
        # Skills Chips
        if scores.get('matching_skills'):
            st.markdown("**Matching Skills:** " + " ".join([f"`{s}`" for s in scores['matching_skills']]))
        if scores.get('missing_skills'):
             st.markdown("**Missing / To Improve:** " + " ".join([f"`{s}`" for s in scores['missing_skills']]))

        st.markdown("---")
        st.markdown(clean_desc)
        
        if st.button("Generate AI Tips", key=f"tips_{unique_key}"):
             with st.spinner("Generating..."):
                 tips = recommender.generate_detailed_application_guide(user_id, job)
                 if tips:
                     st.subheader("💡 AI Application Strategy")
                     
                     # 1. Cover Letter
                     if tips.get('cover_letter_points'):
                        st.markdown("**📝 Cover Letter Points**")
                        for point in tips['cover_letter_points']:
                            st.markdown(f"- {point}")
                     
                     # 2. Resume Tweaks
                     if tips.get('resume_tweaks'):
                        st.markdown("**📄 Resume Tweaks**")
                        for tweak in tips['resume_tweaks']:
                            st.markdown(f"- {tweak}")
                            
                     # 3. Interview Prep
                     if tips.get('interview_prep'):
                        st.markdown("**🎤 Interview Prep**")
                        for q in tips['interview_prep']:
                            st.markdown(f"- {q}")

                     # 4. Missing Skills Strategy
                     if tips.get('missing_skills_strategy'):
                        st.markdown("**📚 Upskilling Strategy**")
                        strategy = tips['missing_skills_strategy']
                        if isinstance(strategy, list):
                            for item in strategy:
                                st.markdown(f"- {item}")
                        else:
                            st.info(strategy)

                     # 5. Company Research
                     if tips.get('company_research'):
                        st.markdown("**🏢 Company Research**")
                        for item in tips['company_research']:
                             st.markdown(f"- {item}")

    # Actions (Moved to bottom)
    st.write("") # Spacer
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Save", key=f"s_{unique_key}"):
            from utils.database import update_job_status
            update_job_status(user_id, job['id'], 'saved')
            st.toast("Job Saved!")
            st.rerun()
    with c2:
        if st.button("Ignore", key=f"i_{unique_key}"):
            from utils.database import update_job_status
            update_job_status(user_id, job['id'], 'rejected')
            st.toast("Job marked as Rejected")
            st.rerun()
