import streamlit as st
import pandas as pd
from backend.auth import get_logged_in_user_id
from backend.scraper import LinkedInJobScraper
from utils.database import (
    get_job_recommendations, save_user_search_preferences,
    get_user_search_preferences, add_search_history_entry,
    get_search_history, update_job_match_scores, update_job_status
)
from backend.recommendations import JobRecommender
import time
import textwrap
import math
import json
from datetime import datetime

def recommendations_page():
    # --- Custom CSS for Premium Look ---
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            font-weight: 600;
        }
        .job-card {
            background-color: #1a1a1a;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid #333;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .job-card:hover {
            transform: translateY(-4px);
            border-color: #00ADB5;
            box-shadow: 0 10px 20px rgba(0, 173, 181, 0.15);
        }
        .metric-card {
            background-color: #262626;
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #00ADB5;
            text-align: center;
        }
        .history-item {
            padding: 10px;
            border-bottom: 1px solid #333;
            font-size: 0.9rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .history-item:hover {
            background-color: #333;
        }
        
        /* Form Styling */
        div[data-testid="stForm"] {
            background-color: #1e1e1e;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #444;
        }
        </style>
    """, unsafe_allow_html=True)

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

    # --- Load Saved Preferences ---
    saved_prefs = get_user_search_preferences(user_id) or {}

    st.title("🚀 Smart Job Search")
    
    # Layout: Sidebar for quick history, Main for Form & Results
    
    # --- SEARCH PREFERENCES FORM ---
    with st.expander("🔍 **Search Preferences & Configuration**", expanded=True):
        with st.form("job_search_form"):
            c1, c2 = st.columns([1, 1])
            with c1:
                job_title = st.text_input("Job Title", value=saved_prefs.get('job_title', 'Software Engineer'), placeholder="e.g. Data Scientist")
                location = st.text_input("Location", value=saved_prefs.get('location', 'Remote'), placeholder="e.g. New York, Remote")
            
            with c2:
               # Remote Preference (Single select simulating Radio for compactness)
               remote_map = {"Any": [], "Remote": ["remote"], "Hybrid": ["hybrid"], "On-site": ["on_site"]}
               # Reverse map for default
               saved_remote_code = saved_prefs.get('remote_type', 'Any')
               # Ensure robustness if saved value is invalid
               default_idx = 0
               try:
                   default_idx = ["Any", "Remote", "Hybrid", "On-site"].index(saved_remote_code)
               except ValueError:
                   default_idx = 0
                   
               remote_pref = st.selectbox("Workplace Type", ["Any", "Remote", "Hybrid", "On-site"], index=default_idx)

               exp_levels = ["Internship", "Entry Level", "Mid Level", "Senior Level", "Director"]
               saved_exp = saved_prefs.get('experience_level', 'Mid Level')
               # Robust index finding
               exp_idx = 2
               if saved_exp in exp_levels:
                   exp_idx = exp_levels.index(saved_exp)
               experience = st.selectbox("Experience Level", exp_levels, index=exp_idx)

            # Job Types
            st.markdown("**Job Type**")
            cols_jt = st.columns(4)
            jt_types = ["Full-time", "Part-time", "Contract", "Internship"]
            selected_jts = []
            
            # Helper to handle saved_jts list safety
            saved_jts = saved_prefs.get('job_type', ["Full-time"])
            if not isinstance(saved_jts, list): saved_jts = ["Full-time"]

            for i, jt in enumerate(jt_types):
                with cols_jt[i]:
                    if st.checkbox(jt, value=(jt in saved_jts)):
                        selected_jts.append(jt)

            # Advanced Section
            with st.expander("⚙️ Advanced Filters (Salary, Keywords, Company)"):
                ac1, ac2 = st.columns(2)
                with ac1:
                    min_salary = st.number_input("Min Annual Salary ($)", value=int(saved_prefs.get('min_salary', 0)), step=5000)
                    keywords_inc = st.text_input("Must-have Keywords", value=saved_prefs.get('keywords_include', ''), placeholder="python, machine learning")
                    visa_support = st.checkbox("Visa Sponsorship Required", value=saved_prefs.get('visa_sponsorship', False))

                with ac2:
                    default_inds = saved_prefs.get('industries', [])
                    if not isinstance(default_inds, list): default_inds = []
                    industries = st.multiselect("Industries", ["Tech", "Finance", "Healthcare", "Education", "Retail", "Manufacturing"], default=default_inds)
                    keywords_exc = st.text_input("Exclude Keywords", value=saved_prefs.get('keywords_exclude', ''), placeholder="sales, cold calling")
                    commute_max = st.slider("Max Commute (mins)", 0, 120, int(saved_prefs.get('max_commute', 45)))
                
                preferred_companies = st.text_area("Preferred Companies", value=saved_prefs.get('preferred_companies', ''), placeholder="Google, Microsoft (comma separated)")

                st.markdown("---")
                st.markdown("⏰ **Auto-Scheduling (Beta)**")
                schedule_freq = st.selectbox("Run this search automatically:", ["Off", "Daily", "Weekly"], index=["Off", "Daily", "Weekly"].index(saved_prefs.get('schedule_frequency', 'Off')))
                if schedule_freq != "Off":
                    st.caption("You will receive email notifications when new jobs are found.")

            # Actions
            col_act1, col_act2, col_act3 = st.columns([2, 1, 1])
            with col_act1:
                search_submitted = st.form_submit_button("🔎 Find Jobs Now", type="primary")
            with col_act2:
                # We can't have multiple submit buttons easily in Streamlit form in standard way, 
                # but checkboxes work fine to modify the submit action.
                save_prefs = st.checkbox("Save as Default", value=True)
            with col_act3:
                # Reset needs to be outside form or handled differently, but Streamlit forms are strict.
                # Actually, making reset a checkbox often works better inside logic, OR separate button OUTSIDE form.
                # Putting it here as submit button creates conflict if pressed. 
                # Common pattern: Just one submit button. 
                pass

    # Reset Button Outside Form
    if st.button("Reset Defaults"):
        if save_user_search_preferences(user_id, {}):
             st.toast("Preferences reset!")
             time.sleep(0.5)
             st.rerun()

    # --- HANDLING FORM SUBMISSION ---
    if search_submitted:
        # 1. Save Preferences
        current_prefs = {
            "job_title": job_title,
            "location": location,
            "remote_type": remote_pref,
            "experience_level": experience,
            "job_type": selected_jts,
            "min_salary": min_salary,
            "keywords_include": keywords_inc,
            "keywords_exclude": keywords_exc,
            "industries": industries,
            "max_commute": commute_max,
            "visa_sponsorship": visa_support,
            "preferred_companies": preferred_companies,
            "schedule_frequency": schedule_freq
        }
        
        if save_prefs:
            save_user_search_preferences(user_id, current_prefs)
            st.toast("Preferences Saved.")

        # 2. Logic to construct Scraper Query
        
        # Merge includes and job title
        full_query = job_title
        if keywords_inc:
            full_query += " " + keywords_inc
        if keywords_exc:
             # Add exclude logic (depends on scraper, mostly appending NOT)
             # LinkedIn supports NOT operator
             excludes = [f'NOT "{k.strip()}"' for k in keywords_exc.split(',') if k.strip()]
             full_query += " " + " ".join(excludes)
             
        # Map Experience
        # Map: 'Internship'->'internship', 'Entry Level'->'entry', 'Mid Level'->'mid_senior'
        exp_map_scraper = {
            "Internship": "internship", "Entry Level": "entry", 
            "Mid Level": "associate", "Senior Level": "mid_senior", "Director": "director" 
        }
        # Note: LinkedIn 'associate' is often used for Mid-level in scraper map, or 'mid_senior'.
        
        # Map Job Type
        jt_map_scraper = {
            "Full-time": "full_time", "Part-time": "part_time", 
            "Contract": "contract", "Internship": "internship"
        }
        
        scraper_filters = {
            "remote": remote_map.get(remote_pref, []),
            "experience": [exp_map_scraper.get(experience, "mid_senior")],
            "job_type": [jt_map_scraper.get(t) for t in selected_jts if t in jt_map_scraper],
            "date_posted": "week" # Default to week for freshness
        }

        # 4. Run Scraper
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total, eta):
            prog = min(current / total, 1.0)
            progress_bar.progress(prog)
            status_text.markdown(f"**Searching LinkedIn...**Found {current}/{total} jobs. <br>⏱️ Estimated time: {eta}", unsafe_allow_html=True)

        try:
            status_text.info("Initializing Intelligence Agent...")
            scraper = LinkedInJobScraper(user_id=user_id, headless=False)
            
            # Login
            import os
            email = os.getenv("LINKEDIN_EMAIL")
            password = os.getenv("LINKEDIN_PASSWORD")
            
            if scraper.login(email, password):
                status_text.info(f"Logged In. Searching for '{full_query}' in {location}...")
                
                jobs = scraper.search_jobs(
                    keywords=full_query,
                    location=location,
                    limit=10, # User defaults to 10 for speed
                    filters=scraper_filters,
                    progress_callback=update_progress
                )
                
                # 5. Log History
                # Scraper skips existing jobs in DB, so all returned jobs are 'new' to the system.
                new_count = len(jobs)
                add_search_history_entry(user_id, f"{job_title} - {location}", current_prefs, len(jobs), new_count)
                
                progress_bar.progress(1.0)
                status_text.success(f"Search Complete! Found {len(jobs)} new jobs.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Login failed. Check credentials.")
        except Exception as e:
            st.error(f"Search failed: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            if 'scraper' in locals():
                scraper.close()

    # --- MAIN DASHBOARD AREA ---
    
    col_dash, col_hist = st.columns([3, 1])
    
    # HISTORY SIDEBAR
    with col_hist:
        st.subheader("🕑 Recent Searches")
        history = get_search_history(user_id, limit=5)
        if not history:
            st.markdown("*No recent searches.*")
        else:
            for item in history:
                with st.container():
                     st.markdown(f"""
                     <div class="history-item">
                        <div>
                            <strong>{item['query_summary']}</strong><br>
                            <span style="color:#888; font-size:0.8em">{item['timestamp'][:10]}</span>
                        </div>
                        <div style="text-align:right">
                            <span style="color:#00ADB5; font-weight:bold">+{item['new']}</span><br>
                            <span style="color:#666; font-size:0.8em">new</span>
                        </div>
                     </div>
                     """, unsafe_allow_html=True)
                     if st.button("Rerun", key=f"hist_{item['id']}"):
                         # Load params and rerun (simplified: just load into Session State to fill form?)
                         # Ideally trigger search, but filling form is safer.
                         prefs = item['params']
                         save_user_search_preferences(user_id, prefs) # Set as current
                         st.toast("Configuration loaded! Click 'Find Jobs Now'.")
                         time.sleep(0.5)
                         st.rerun()

    # RESULTS AREA
    with col_dash:
        raw_jobs = get_job_recommendations(user_id)
        
        # Stats Bar
        k1, k2, k3 = st.columns(3)
        with k1: 
             st.markdown(f"<div class='metric-card'><h3>{len(raw_jobs)}</h3><p>Total Opportunities</p></div>", unsafe_allow_html=True)
        with k2:
             avg_match = int(sum(j.get('match_percentage', 0) for j in raw_jobs)/len(raw_jobs)) if raw_jobs else 0
             st.markdown(f"<div class='metric-card'><h3>{avg_match}%</h3><p>Avg Match Score</p></div>", unsafe_allow_html=True)
        with k3:
             new_jobs = len([j for j in raw_jobs if j.get('status') == 'new'])
             st.markdown(f"<div class='metric-card'><h3>{new_jobs}</h3><p>New / Unread</p></div>", unsafe_allow_html=True)

        st.markdown("---")
        
        # TABS
        tab_rec, tab_saved, tab_compare = st.tabs(["🎯 Recommended", "📌 My List", "⚖️ Compare"])
        
        with tab_rec:
            # Sort controls
            s1, s2 = st.columns([2,1])
            with s1:
                 st.caption(f"Showing top results based on AI matching.")
            with s2:
                 sort_opt = st.selectbox("Sort by", ["Match %", "Newest", "Applicants"], label_visibility="collapsed")
            
            # Filter Logic (Client Side for Display)
            display_jobs = [j for j in raw_jobs if j.get('status') not in ['rejected']]
            
            if sort_opt == "Match %":
                display_jobs.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
            elif sort_opt == "Newest":
                display_jobs.sort(key=lambda x: x.get('posted_date', ''), reverse=True)
            elif sort_opt == "Applicants":
                display_jobs.sort(key=lambda x: x.get('applicant_count', 999))

            # Pagination
            page_size = 5
            if "job_page" not in st.session_state: st.session_state.job_page = 0
            
            total_pages = math.ceil(len(display_jobs) / page_size)
            curr_page = st.session_state.job_page
            
            # Bounds check
            if curr_page >= total_pages: curr_page = 0
            
            start = curr_page * page_size
            end = start + page_size
            page_items = display_jobs[start:end]
            
            if not page_items:
                st.info("No jobs found matching your criteria. Try adjusting filters or running a new search.")
            
            for job in page_items:
                _render_job_card(job, recommender, user_id)
            
            # Pagination Controls
            if total_pages > 1:
                pc1, pc2, pc3 = st.columns([1, 2, 1])
                with pc1:
                     if st.button("Previous", disabled=curr_page==0):
                         st.session_state.job_page -= 1
                         st.rerun()
                with pc2:
                     st.caption(f"Page {curr_page+1} of {total_pages}")
                with pc3:
                     if st.button("Next", disabled=curr_page>=total_pages-1):
                         st.session_state.job_page += 1
                         st.rerun()

        with tab_saved:
             saved_list = [j for j in raw_jobs if j.get('status') in ['saved', 'applied', 'interviewing']]
             if saved_list:
                 for job in saved_list:
                      _render_job_card(job, recommender, user_id, mini=True)
             else:
                 st.info("No saved jobs yet.")

        with tab_compare:
            st.write("Select jobs to compare side-by-side.")
            # Reuse existing comparison logic or simplified
            opts = {f"{j['job_title']} @ {j['company_name']}": j for j in raw_jobs}
            sel = st.multiselect("Select 2-3 jobs", list(opts.keys()))
            if sel:
                sel_jobs = [opts[k] for k in sel]
                cols = st.columns(len(sel_jobs))
                for idx, j in enumerate(sel_jobs):
                    with cols[idx]:
                         st.markdown(f"#### {j['company_name']}")
                         st.markdown(f"**{j['job_title']}**")
                         st.success(f"{int(j.get('match_percentage', 0))}% Match")
                         st.write(f"📍 {j['location']}")
                         st.write(f"👥 {j.get('applicant_count', 0)} applicants")
                         st.caption(j['job_description'][:150] + "...")

def _render_job_card(job, recommender, user_id, mini=False):
    """Render a single job card."""
    match = int(job.get('match_percentage', 0))
    color = "#00c853" if match > 75 else "#ffd700" if match > 50 else "#ff5252"
    
    with st.container():
        st.markdown(f"""
        <div class="job-card" style="border-left: 5px solid {color};">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <a href="{job['job_url']}" target="_blank" style="text-decoration:none; color:#00ADB5; font-size:1.3em; font-weight:bold;">{job['job_title']}</a>
                    <div style="color:#eee; font-size:1.1em; margin-bottom:5px;">{job['company_name']}</div>
                    <div style="color:#aaa; font-size:0.9em;">📍 {job['location']} &nbsp;•&nbsp; 🗓️ Posted {job.get('posted_date', 'N/A')[:10]}</div>
                </div>
                <div style="text-align:right;">
                    <span style="background:{color}33; color:{color}; padding:5px 10px; border-radius:15px; font-weight:bold;">{match}% Match</span>
                    <br><span style="font-size:0.8em; color:#666;">{job.get('applicant_count', 0)} applicants</span>
                </div>
            </div>
            <div style="margin-top:15px; color:#ccc; font-size:0.95em; line-height:1.5;">
                {textwrap.shorten(job.get('job_description', ''), width=200, placeholder='...')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action Buttons
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        status = job.get('status', 'new')
        
        if not mini:
            with c1:
                if status != 'saved' and st.button("🔖 Save", key=f"s_{job['id']}"):
                    update_job_status(user_id, job['id'], 'saved')
                    st.rerun()
            with c2: 
                if status != 'rejected' and st.button("🚫 Ignore", key=f"i_{job['id']}"):
                    update_job_status(user_id, job['id'], 'rejected')
                    st.rerun()
            with c3:
                # Tips logic
                if st.button("💡 Tips", key=f"t_{job['id']}"):
                    with st.spinner("Analyzing..."):
                        tips = recommender.generate_detailed_application_guide(user_id, job)
                        if tips:
                            st.session_state[f"tips_{job['id']}"] = tips
        
        # Display tips if generated
        if f"tips_{job['id']}" in st.session_state:
            t = st.session_state[f"tips_{job['id']}"]
            with st.expander("✨ AI Application Strategy", expanded=True):
                 st.write("Cover Letter Ideas:")
                 for p in t.get('cover_letter_points', []): st.write(f"- {p}")
