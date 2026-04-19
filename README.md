# Recruit Intelligence Agent

AI-powered recruitment assistant for screening candidates, generating job descriptions, and answering hiring questions. Built on Backboard for document processing and reasoning.

## Overview

Recruit Intelligence Agent is a production-ready AI-powered recruitment API built with FastAPI and Backboard. It streamlines the hiring process through automated candidate screening, resume parsing into standardized JSON Resume format, intelligent job matching with gap analysis, job description generation with market research, and candidate validation via live web searches.

Key capabilities:
- Parse resumes (Backboard supported files) into structured JSON Resume format
- Evaluate candidates against job descriptions with scoring and analysis
- Perform deep agentic reasoning with multi-step analysis pipelines
- Validate candidate work history and credentials via web search
- Research skill market trends and salary ranges
- Generate optimized, inclusive job descriptions
- Analyze team composition for skill gaps
- General document Q&A and summarization

## Setup

### Prerequisites

- Python 3.8+
- Backboard API Key

### Installation

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file with your configuration:

```
BACKBOARD_API_KEY=your_api_key_here
BACKBOARD_LLM_PROVIDER=openai
BACKBOARD_MODEL_NAME=gpt-5-mini
BACKBOARD_TIMEOUT=1800
```

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKBOARD_API_KEY` | Backboard API key (required) | - |
| `BACKBOARD_LLM_PROVIDER` | LLM provider (openai, anthropic, etc.) | openai |
| `BACKBOARD_MODEL_NAME` | Model name to use | gpt-5-mini |
| `BACKBOARD_TIMEOUT` | API request timeout in seconds | 1800 |

## Running the Application

```bash
uvicorn app.main:app --reload
```

Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health
- Cost metrics: http://localhost:8000/metrics/costs

## Documentation
- Architecture: [docs/architecture.drawio](docs/architecture.drawio)
- Getting Started: [docs/01-getting-started.md](docs/01-getting-started.md)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check endpoint |
| `GET /metrics/costs` | Get cost tracking summary |
| `POST /upload` | Upload a document and get thread_id |
| `POST /parse` | Parse a resume and extract structured JSON Resume data |
| `POST /evaluate` | Evaluate a candidate against a job description |
| `POST /comprehensive_evaluate` | Agentic reasoning with skill extraction, market research, and gap detection |
| `POST /summarize` | Summarize an uploaded document |
| `POST /reasoning` | Perform reasoning on a document with custom question |
| `POST /qa` | Ask questions about a document (Q&A) |
| `POST /websearch` | Search the web for candidate information |
| `POST /validate` | Validate candidate profile via web search |
| `POST /validate-companies` | Validate all companies mentioned in a resume |
| `POST /jd/generate` | Generate optimized job description |
| `POST /jd/research-trends` | Research market trends for a role |
| `POST /jd/analyze-team` | Analyze existing team composition |

## Usage Guide

### Quick Start

The application supports two modes of operation:

**Mode 1: Stateful (Recommended for multiple operations on same document)**
```bash
# Step 1: Upload a document
curl -X POST http://localhost:8000/upload -F file=@resume.pdf

# Response: {"thread_id": "thread_xxx", "status": "indexed"}

# Step 2: Use thread_id for all subsequent calls
curl -X POST http://localhost:8000/parse -F thread_id=thread_xxx
curl -X POST http://localhost:8000/evaluate -F thread_id=thread_xxx -F job_description="Senior Python Developer with Django, PostgreSQL experience..."
curl -X POST http://localhost:8000/comprehensive_evaluate -F thread_id=thread_xxx -F job_description="Senior Python Developer..."
```

**Mode 2: Fallback (Single operation, creates new session each time)**
```bash
# Direct file upload - no need to manage document_id/thread_id
curl -X POST http://localhost:8000/parse -F file=@resume.pdf
curl -X POST http://localhost:8000/evaluate -F file=@resume.pdf -F job_description="Senior Python Developer..."
```

### Endpoint Examples

**Parse Resume (JSON Resume format)**
```bash
curl -X POST http://localhost:8000/parse -F thread_id=thread_xxx
```
Returns structured resume data with basics, work, education, skills, projects, etc.

**Evaluate Candidate**
```bash
curl -X POST http://localhost:8000/evaluate \
  -F thread_id=thread_xxx \
  -F job_description="Senior Python Developer with 5+ years experience in Django, FastAPI, PostgreSQL, AWS"
```
Returns score, strengths, gaps, risk flags, and recommendation.

**Comprehensive Agentic Evaluation**
```bash
curl -X POST http://localhost:8000/comprehensive_evaluate \
  -F thread_id=thread_xxx \
  -F job_description="Senior Python Developer..."
```
Performs full pipeline: resume parsing → skill extraction → market research → job fit analysis → validation.

**Summarize Document**
```bash
curl -X POST http://localhost:8000/summarize -F thread_id=thread_xxx
```

**Reason on Document**
```bash
curl -X POST http://localhost:8000/reasoning \
  -F thread_id=thread_xxx \
  -F question="What are the candidate's leadership experiences?"
```

**Q&A**
```bash
curl -X POST http://localhost:8000/qa \
  -F thread_id=thread_xxx \
  -F question="What Python frameworks has the candidate used?"
```

**Web Search for Candidate**
```bash
# General search
curl -X POST http://localhost:8000/websearch \
  -F thread_id=thread_xxx \
  -F query="John Doe Python developer GitHub"

# Search with known details
curl -X POST http://localhost:8000/websearch \
  -F name="John Doe" \
  -F email="john@example.com" \
  -F company="Google"
```

**Validate Candidate Profile**
```bash
curl -X POST http://localhost:8000/validate \
  -F name="John Doe" \
  -F email="john@example.com" \
  -F company="Google"
```

**Validate All Companies from Resume**
```bash
curl -X POST http://localhost:8000/validate-companies \
  -F thread_id=thread_xxx
```

**Generate Job Description**
```bash
curl -X POST http://localhost:8000/jd/generate \
  -F role_requirements="Senior Python Developer with Django, FastAPI, PostgreSQL experience. 5+ years of backend development."
```

**Research Role Market Trends**
```bash
curl -X POST http://localhost:8000/jd/research-trends \
  -F role="Software Engineer" \
  -F industry="Technology"
```

**Analyze Existing Team**
```bash
curl -X POST http://localhost:8000/jd/analyze-team \
  -F team_composition_json='[{"role": "Frontend Developer", "skills": ["React", "TypeScript"], "experience": 3}, {"role": "Backend Developer", "skills": ["Python", "Django"], "experience": 5}]'
```

## Features

### Resume Parsing
Extract structured JSON Resume data from PDF/DOCX files. Maps to standard JSON Resume schema including:
- Basic info (name, email, phone, location, summary, profiles)
- Work experience (company, position, dates, highlights)
- Education (institution, degree, field, dates, courses)
- Skills (technical, soft skills, keywords with levels)
- Projects, awards, certificates, publications, languages, interests

### Agentic Reasoning Pipeline
Deep multi-step analysis using the `ResumeReasoningAgent`:
1. Parse resume and extract all structured information
2. Deep skill extraction (technical, soft skills, domain knowledge, certifications)
3. Market research via web search for skill demand trends and salary ranges
4. Job fit analysis with detailed scoring, match detection, gap analysis, transferable skills
5. Validation of work history and credentials via live web search

### Candidate Evaluation
Score candidates against job descriptions with detailed analysis:
- Match detection (which required skills candidate possesses)
- Gap analysis (missing or underdeveloped skills)
- Partial matches and transferable skills identification
- Experience relevance assessment
- Education alignment evaluation
- Risk flag identification

### Memory-Enabled Context
Parsed resume data is automatically stored in agent memory for enhanced reasoning. After parsing, the agent remembers:
- Candidate name, professional label, and contact information
- Complete work history (companies, positions, dates)
- Education background and credentials
- Key skills and expertise areas
Enables better-informed decisions during subsequent analysis.

### Web Search & Validation
- Live web research for candidate professional profiles (LinkedIn, GitHub, portfolios)
- Company validation (verify work history, check company legitimacy)
- Profile verification (name, email, credentials)
- Skills market research (demand trends, salary ranges, industry adoption)

### Document Processing
General document understanding capabilities:
- Document summarization with key points extraction
- Q&A over document content
- Custom reasoning queries

### Job Description Generation
AI-powered job description creation with:
- Role-based JD generation with customizable sections
- Market research integration (skill trends, salary ranges)
- Team composition analysis for skill gap detection
- Inclusivity checking (gender-neutral, age-neutral, accessibility)
- Clarity scoring for role expectations
- Benefits and perks suggestions

### Observability & Monitoring
Built-in production-ready features:
- OpenTelemetry distributed tracing with trace IDs
- Structured JSON logging
- Cost tracking per request with summary endpoint (`/metrics/costs`)
- Configurable LLM providers (OpenAI, Anthropic, etc.)
- Request/response middleware with timing and logging


## Components

| Component | Description |
|-----------|-------------|
| `app/main.py` | FastAPI application with CORS, tracing middleware, cost tracking |
| `app/routes.py` | API endpoint definitions (13 endpoints) |
| `app/services/backboard_client.py` | Backboard SDK wrapper with monitoring and cost tracking |
| `app/core/monitoring.py` | OpenTelemetry tracing, structured logging, cost tracking |
| `app/tools/resume_tools.py` | Resume parsing, JSON Resume schema mapping, skill extraction |
| `app/tools/reasoning_tools.py` | ResumeReasoningAgent (agentic evaluation), DocumentProcessor (document Q&A) |
| `app/tools/candidate_websearch.py` | CandidateWebSearch (profile research, company validation, skill market research) |
| `app/tools/jd_generator.py` | JobDescriptionGenerator (JD creation, market research, team analysis) |
| `app/tools/resume_schema.json` | JSON Resume schema definition |

## JSON Resume Schema

The parser maps to the standard JSON Resume format:

```
{
  basics: {
    name: John Doe,
    label: Software Engineer,
    email: john@example.com,
    phone: +1-555-555-5555,
    url: https://johndoe.com,
    summary: Experienced software engineer...,
    location: {city: San Francisco, country: USA},
    profiles: [{network: LinkedIn, url: ...}]
  },
  work: [{
    name: Acme Corp,
    position: Software Engineer,
    startDate: 2020-01,
    endDate: Present,
    summary: Built...,
    highlights: [Improved performance by 50%]
  }],
  education: [{
    institution: Stanford University,
    area: Computer Science,
    studyType: Master,
    startDate: 2018-09,
    endDate: 2020-06
  }],
  skills: [{
    name: Python,
    level: Expert,
    keywords: [Django, Flask]
  }],
  projects: [...],
  awards: [...],
  certificates: [...],
  languages: [...]
}
```

## License

MIT License



