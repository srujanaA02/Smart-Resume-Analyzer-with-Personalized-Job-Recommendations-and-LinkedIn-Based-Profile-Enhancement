# Resume Analysis and Job Recommendation System

An intelligent application that analyzes user resumes and provides personalized job recommendations using LLM technology. Built with Streamlit for a seamless user experience.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Resume Analysis](#resume-analysis--strengthsweaknesses-analyzer)
- [Resume Scoring System](#resume-scoring-system)
- [Skills Gap Analysis](#skills-gap-analysis)
- [Job Recommendations](#job-recommendations)
- [LLM Setup](#llm-setup)
- [Database Schema](#database-schema)
- [Contributing](#contributing)

## Features

✅ **User Authentication**: Secure registration and login with bcrypt password hashing
✅ **Resume Upload**: Support for PDF and DOCX file formats with validation
✅ **Text Extraction**: Automatic text extraction from resume files
✅ **Resume Analysis**: AI-powered analysis using Ollama LLM with strengths/weaknesses detection
✅ **Resume Scoring System**: Comprehensive multi-factor scoring with detailed breakdown (NEW)
✅ **Skills Gap Analysis**: Comprehensive skills extraction, industry comparison, and personalized learning roadmap
✅ **Intelligent Caching**: Two-level cache (memory + disk) to avoid re-analyzing identical resumes
✅ **Confidence Scoring**: 0-100% confidence scores on all analyses
✅ **Database Storage**: Persistent storage of analysis results linked to user profiles
✅ **Interactive Visualizations**: Plotly charts for skills distribution and gap analysis
✅ **Learning Recommendations**: Prioritized skill recommendations with resources and learning paths
✅ **User Dashboard**: Central hub for navigation, quick stats, and application tracking
✅ **Job Recommendations**: Personalized job recommendations based on resume analysis with specific 'Match %'
✅ **Application Tracker**: Track status of jobs (Saved, Applied, Rejected)

## Project Structure

```
ResumeAnalysisAndJobRecommendationSystem/
├── app.py                          # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── .env                           # Environment variables (not in git)
├── .gitignore                     # Git ignore rules
├── backend/
│   ├── __init__.py
│   ├── auth.py                    # Authentication & session management
│   ├── resume_parser.py           # PDF/DOCX text extraction
│   ├── llm_analyzer.py            # LLM-based analysis
│   ├── resume_scorer.py           # Resume scoring system
│   ├── recommendations.py         # Job matching logic
│   └── scraper.py                 # LinkedIn job scraper
├── frontend/
│   ├── __init__.py
│   ├── pages.py                   # Page routing configuration
│   ├── login.py                   # Login page
│   ├── registration.py            # Registration page
│   ├── dashboard.py               # Main dashboard
│   ├── profile.py                 # User profile page
│   ├── resume_analysis.py         # Resume analysis page
│   ├── analysis.py                # Analysis results display
│   ├── resume_scoring.py          # Resume scoring page
│   ├── skills_gap.py              # Skills gap analysis page
│   ├── job_recommendations.py     # Job recommendations page
│   └── settings.py                # User settings page
├── utils/
│   ├── __init__.py
│   └── database.py                # Database connection & CRUD operations
└── data/
    ├── database.db                # SQLite database
    └── resumes/                   # Uploaded resume files
```

## Setup & Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd ResumeAnalysisAndJobRecommendationSystem
```

### Step 2: Create a Virtual Environment

```bash
# On Windows
python -m venv .venv
.venv\Scripts\activate

# On macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root directory:

```env
# Database configuration
DB_PATH=data/database.db

# Optional: LinkedIn Credentials for Scraping
LINKEDIN_EMAIL=your_email
LINKEDIN_PASSWORD=your_password

# API Keys (add as needed for future integrations)
# OPENAI_API_KEY=your_key_here
```

### Step 5: Initialize the Database

The database is automatically initialized when the application starts.

## Running the Application

### Prerequisites: Start Ollama First

Ollama must be running before starting the Streamlit app. Open a terminal and run:

```bash
ollama serve
```

### Start the Streamlit Server

```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`.

---

## Resume Analysis & Strengths/Weaknesses Analyzer

### Overview

AI-powered analyzer using Ollama LLM to identify resume strengths and weaknesses with detailed categorization, severity levels, and actionable recommendations.

### Key Features
- **Strengths Identification**: Highlights top 5-7 strengths with importance levels (Critical, High, Medium).
- **Weakness Detection**: Identifies improvement areas with severity (Critical, Moderate, Minor) and location context.
- **Skills Extraction**: Automatically parses Technical and Soft skills.
- **Visual Reports**: Interactive charts and a downloadable **PDF Report**.

---

## Resume Scoring System

### Overview

Comprehensive scoring system that evaluates resumes on multiple criteria using a weighted multi-factor algorithm.

### Scoring Components (Weights)
1.  **Completeness (25%)**: Checks for essential sections (Summary, Experience, Education, etc.).
2.  **Content Quality (30%)**: Analyzes action verbs, quantifiable metrics, and impact.
3.  **Formatting (15%)**: Evaluates structure, length, and readability.
4.  **Keyword Relevance (20%)**: Checks validation against industry standards.
5.  **Experience (10%)**: Validates career progression and timeline.

### Classification
*   **Excellent (90-100)**
*   **Good (75-89)**
*   **Average (60-74)**
*   **Needs Improvement (<60)**

---

## Skills Gap Analysis

### Overview
This module bridges the gap between your current profile and your target role (e.g., "Full Stack Developer", "Data Scientist").

### Features
*   **Target Role Comparison**: Compares your resume skills against the requirements of specific job roles and seniority levels (Entry, Mid, Senior).
*   **Readiness Score**: A 0-100 score indicating how qualified you are for the target role.
*   **Missing Skills Detection**:
    *   **Critical Skills**: Must-haves for the role that you are missing.
    *   **Nice-to-Haves**: Bonus skills to boost your candidacy.
*   **Learning Roadmap**:
    *   Provides a structured learning path.
    *   Recommends specific courses, project ideas, and certifications.
    *   Estimates time to close the gap.

---

## Job Recommendations

### Overview
An intelligent job search engine that not only finds jobs but "matches" them to your resume using semantic analysis.

### Features
*   **Smart Search**:
    *   **Filters**: Location, Remote/Hybrid, Salary, Experience Level.
    *   **Scraper**: Integrated LinkedIn scraper (Headless or Browser mode) to fetch real-time listings.
*   **AI Match Scoring**:
    *   Instead of just keywords, the AI analyzes the *context* of the job description vs. your resume.
    *   Assigns a **Match %** (e.g., "85% Match") to every job.
*   **Application Guide**:
    *   Click "💡 Tips" on any job card to generate a tailored strategy.
    *   Includes **Cover Letter Points** and **Interview Prep Questions** specific to that job description.
*   **Application Tracker**:
    *   **Save** interesting jobs.
    *   Mark as **Applied** or **Rejected**.
    *   View your history and status in the "My Profile" page.

---

## LLM Setup

### Environment Configuration (.env)

The application uses the following LLM configuration defaults:

```env
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=llama3.2:latest   # or mistral, llama2, etc.
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=3000
```

### Supported Models
- **llama3.2** (Recommended for speed/quality balance)
- **mistral**
- **gemma**

---

## Database Schema

The application uses SQLite with the following core tables:

*   **users**: Identity and resume file path.
*   **resume_analysis**: Stored JSON results of LLM analysis (Strengths, Weaknesses).
*   **resume_scores**: Structured scoring history with component breakdowns.
*   **skills_gap_analysis**: Cache for gap analysis sessions.
*   **job_recommendations**: Scraped jobs with match scores and user status (saved/applied).
*   **search_history**: Log of user search parameters and results counts.

---

## Contributing

1.  Create a new branch for your feature.
2.  Make your changes and test thoroughly.
3.  Submit a pull request with a clear description.

## License

This project is licensed under the MIT License.
