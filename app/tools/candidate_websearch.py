import os
import json
from dotenv import load_dotenv
from app.services.backboard_client import BackboardClientWrapper

load_dotenv()

API_KEY = os.getenv("BACKBOARD_API_KEY")

client = BackboardClientWrapper(API_KEY)

class CandidateWebSearch:
    def __init__(self):
        self.assistant_id = None
        self.thread_id = None
        self.context = {}
    
    async def initialize(self):
        self.assistant_id = await client.create_assistant("Candidate Web Search")
        self.thread_id = await client.create_thread(self.assistant_id)
        return self
    
    async def search(self, query):
        response = await client.web_search(
            thread_id=self.thread_id,
            content=query
        )
        
        result = response.get("content", response.get("message", ""))
        self.context["last_search"] = result
        return {"results": result}
    
    async def validate_company(self, company_name, role=None):
        query = f"Research {company_name}" + (f" and {role}" if role else "") + ". Find: company website, industry, size, description, recent news. Validate if this is a real company."
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=query
        )
        
        result = response.get("content", response.get("message", ""))
        
        self.context["company_validation"] = {
            "company": company_name,
            "role": role,
            "research": result
        }
        
        return {"company": company_name, "role": role, "research": result}
    
    async def validate_credentials(self, person_name, credentials):
        credentials_str = ", ".join(credentials) if isinstance(credentials, list) else credentials
        
        query = f"Research {person_name} with credentials: {credentials_str}. Find: LinkedIn profile, professional background, publications, certifications, work history."
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=query
        )
        
        result = response.get("content", response.get("message", ""))
        
        self.context["credentials_validation"] = {
            "person": person_name,
            "credentials": credentials,
            "research": result
        }
        
        return {"person": person_name, "research": result}
    
    async def search_candidate_profile(self, name, email=None, company=None):
        search_terms = [name]
        
        if email:
            search_terms.append(email)
        if company:
            search_terms.append(company)
        
        query = "Find professional information about: " + " ".join(search_terms) + ". Look for LinkedIn, GitHub, portfolio, publications, or other professional profiles."
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=query
        )
        
        result = response.get("content", response.get("message", ""))
        
        self.context["profile_search"] = {
            "name": name,
            "email": email,
            "company": company,
            "results": result
        }
        
        return {"name": name, "results": result}
    
    async def research_technical_skills(self, skills):
        skills_str = ", ".join(skills) if isinstance(skills, list) else skills
        
        query = f"Research current market demand and trends for: {skills_str}. Find: job market trends, salary ranges, popular frameworks/tools, industry adoption."
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=query
        )
        
        result = response.get("content", response.get("message", ""))
        
        self.context["skills_research"] = {
            "skills": skills,
            "research": result
        }
        
        return {"skills": skills, "research": result}
    
    async def comprehensive_research(self, resume_data):
        name = resume_data.get("basics", {}).get("name", "")
        email = resume_data.get("basics", {}).get("email", "")
        work = resume_data.get("work", [])
        skills = resume_data.get("skills", [])
        
        await self.initialize()
        
        results = {"candidate": name}
        
        if name:
            profile_results = await self.search_candidate_profile(name, email)
            results["profile"] = profile_results.get("results")
        
        companies = []
        for job in work:
            company = job.get("name")
            if company and company not in companies:
                companies.append(company)
        
        company_validations = []
        for company in companies:
            validation = await self.validate_company(company)
            company_validations.append(validation)
        
        results["company_validations"] = company_validations
        
        if skills:
            skill_names = [s.get("name", "") for s in skills if s.get("name")]
            if skill_names:
                skills_research = await self.research_technical_skills(skill_names)
                results["skills_research"] = skills_research.get("research")
        
        return results


async def search_candidate(query):
    search = CandidateWebSearch()
    await search.initialize()
    return await search.search(query)


async def validate_candidate_companies(resume_data):
    search = CandidateWebSearch()
    await search.initialize()
    
    work = resume_data.get("work", [])
    companies = []
    
    for job in work:
        company = job.get("name")
        role = job.get("position")
        if company and company not in [c.get("company") for c in companies]:
            companies.append({"company": company, "role": role})
    
    validations = []
    for company in companies:
        validation = await search.validate_company(company["company"], company["role"])
        validations.append(validation)
    
    return {"validations": validations}


async def research_candidate_profile(name, email=None, company=None):
    search = CandidateWebSearch()
    await search.initialize()
    return await search.search_candidate_profile(name, email, company)