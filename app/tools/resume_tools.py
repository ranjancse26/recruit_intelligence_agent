
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from app.services.backboard_client import BackboardClientWrapper

load_dotenv()

API_KEY = os.getenv("BACKBOARD_API_KEY")

client = BackboardClientWrapper(API_KEY)

SCHEMA_FILE = Path(__file__).parent / "resume_schema.json"

JSON_RESUME_SCHEMA = {
    "basics": {
        "name": "",
        "label": "",
        "email": "",
        "phone": "",
        "url": "",
        "summary": "",
        "location": {
            "address": "",
            "city": "",
            "region": "",
            "postalCode": "",
            "countryCode": ""
        },
        "profiles": []
    },
    "work": [],
    "education": [],
    "skills": [],
    "projects": [],
    "awards": [],
    "certificates": [],
    "publications": [],
    "languages": [],
    "interests": [],
    "references": [],
    "meta": {}
}


def load_resume_schema() -> dict:
    with open(SCHEMA_FILE, "r") as f:
        return json.load(f)

def parse_json_resume(data: dict) -> dict:
    resume = {"basics": {}, "work": [], "education": [], "skills": [], "projects": [], "meta": {}}
    
    if "basics" in data:
        basics = data["basics"]
        resume["basics"] = {
            "name": basics.get("name", ""),
            "label": basics.get("label", ""),
            "email": basics.get("email", ""),
            "phone": basics.get("phone", ""),
            "url": basics.get("url", ""),
            "summary": basics.get("summary", ""),
            "location": basics.get("location", {}),
            "profiles": basics.get("profiles", [])
        }
    
    if "work" in data:
        resume["work"] = [
            {
                "name": w.get("name", ""),
                "position": w.get("position", ""),
                "url": w.get("url", ""),
                "startDate": w.get("startDate", ""),
                "endDate": w.get("endDate", ""),
                "summary": w.get("summary", ""),
                "highlights": w.get("highlights", [])
            }
            for w in data["work"]
        ]
    
    if "education" in data:
        resume["education"] = [
            {
                "institution": e.get("institution", ""),
                "area": e.get("area", ""),
                "studyType": e.get("studyType", ""),
                "startDate": e.get("startDate", ""),
                "endDate": e.get("endDate", ""),
                "score": e.get("score", ""),
                "courses": e.get("courses", [])
            }
            for e in data["education"]
        ]
    
    if "skills" in data:
        resume["skills"] = [
            {
                "name": s.get("name", ""),
                "level": s.get("level", ""),
                "keywords": s.get("keywords", [])
            }
            for s in data["skills"]
        ]
    
    if "projects" in data:
        resume["projects"] = [
            {
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "highlights": p.get("highlights", []),
                "keywords": p.get("keywords", [])
            }
            for p in data["projects"]
        ]
    
    if "meta" in data:
        resume["meta"] = data["meta"]
    
    return resume

def extract_skills_from_resume(resume: dict) -> list:
    skills = []
    
    if "skills" in resume:
        for skill_group in resume["skills"]:
            keywords = skill_group.get("keywords", [])
            skills.extend(keywords)
    
    if "work" in resume:
        for job in resume["work"]:
            highlights = job.get("highlights", [])
            for highlight in highlights:
                words = highlight.replace(",", " ").split()
                skills.extend([w for w in words if len(w) > 2])
    
    if "projects" in resume:
        for project in resume["projects"]:
            keywords = project.get("keywords", [])
            skills.extend(keywords)
    
    return list(set(skills))

async def parse_resume_internal(file):
    assistant_id = await client.create_assistant("Resume Parser")
    thread_id = await client.create_thread(assistant_id)
    await client.upload_document(file, metadata={"type": "resume"}, assistant_id=assistant_id)

    schema_json = json.dumps(load_resume_schema(), indent=2)

    response = await client.chat(
        thread_id=thread_id,
        content=f"""
        Parse the uploaded resume document and extract structured information.

        Return a JSON object following the JSON Resume schema:

        {schema_json}

        Extract all available information from the resume. Use empty strings/arrays for missing fields.
        Return ONLY the JSON object, no additional text.
        """
    )

    return response

async def evaluate_candidate(file, job_desc):

    assistant_id = await client.create_assistant("Recruit Agent")
    thread_id = await client.create_thread(assistant_id)
    await client.upload_document(file, metadata={"type": "resume"}, assistant_id=assistant_id)

    resume_data = {}
    if isinstance(file, dict):
        resume_data = parse_json_resume(file)
    elif isinstance(file, str):
        try:
            resume_data = parse_json_resume(json.loads(file))
        except:
            pass

    extracted_skills = extract_skills_from_resume(resume_data) if resume_data else []

    response = await client.chat(
        thread_id=thread_id,
        content=f"""
        Evaluate candidate against job:

        JOB:
        {job_desc}

        EXTRACTED RESUME DATA (JSON Resume Schema):
        {json.dumps(resume_data, indent=2) if resume_data else "No structured data available"}

        EXTRACTED SKILLS:
        {extracted_skills}

        Steps:
        1. Extract skills from resume using JSON Resume schema fields: basics, work, education, skills, projects
        2. Compare with job description
        3. Validate via web search
        4. Score candidate

        Return JSON:
        {{
          "score": 0-100,
          "strengths": [],
          "gaps": [],
          "risk_flags": [],
          "recommendation": ""
        }}
        """
    )

    return response
