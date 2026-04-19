import os
import json
from dotenv import load_dotenv
from app.services.backboard_client import BackboardClientWrapper

load_dotenv()

API_KEY = os.getenv("BACKBOARD_API_KEY")

client = BackboardClientWrapper(API_KEY)

class ResumeReasoningAgent:
    def __init__(self):
        self.assistant_id = None
        self.thread_id = None
        self.context = {}
    
    async def initialize(self):
        self.assistant_id = await client.create_assistant("Resume Reasoning Agent")
        self.thread_id = await client.create_thread(self.assistant_id)
        return self
    
    async def _chat(self, content, system_prompt=None):
        if system_prompt:
            content = f"{system_prompt}\n\n{content}"
        
        response = await client.chat(
            thread_id=self.thread_id,
            content=content
        )
        return response
    
    async def parse_resume(self, file):
        response = await self._chat(
            f"""
            Parse the uploaded resume document thoroughly. Extract ALL information available.

            JSON Resume Schema to map to:
            - basics: name, label, email, phone, url, summary, location, profiles
            - work: company, position, startDate, endDate, summary, highlights
            - education: institution, area, studyType, startDate, endDate, score, courses
            - skills: name, level, keywords
            - projects: name, description, highlights, keywords
            - awards, certificates, publications, languages, interests, references

            Return comprehensive JSON with all extracted details. Use empty arrays/strings for missing fields.
            Return ONLY JSON, no additional text.
            """
        )
        
        try:
            data = json.loads(response.get("content", response.get("message", "{}")))
        except:
            data = {"raw": response}
        
        self.context["resume_data"] = data
        
        resume_summary = self._create_resume_memory_summary(data)
        await client.add_message(
            thread_id=self.thread_id,
            content=resume_summary,
            memory="Auto",
            stream=False
        )
        
        return data
    
    def _create_resume_memory_summary(self, data):
        basics = data.get("basics", {})
        name = basics.get("name", "Unknown")
        email = basics.get("email", "")
        label = basics.get("label", "")
        
        work = data.get("work", [])
        companies = [w.get("name", "") for w in work if w.get("name")]
        
        education = data.get("education", [])
        edu_fields = [e.get("area", e.get("studyType", "")) for e in education if e.get("area") or e.get("studyType")]
        
        skills = data.get("skills", [])
        skill_names = [s.get("name", "") for s in skills if s.get("name")]
        
        summary = f"Candidate: {name}"
        if label:
            summary += f", {label}"
        if email:
            summary += f", Email: {email}"
        if companies:
            summary += f". Companies: {', '.join(companies)}"
        if edu_fields:
            summary += f". Education: {', '.join(edu_fields)}"
        if skill_names:
            skills_str = ", ".join(skill_names[:15])
            if len(skill_names) > 15:
                skills_str += f" and {len(skill_names) - 15} more"
            summary += f". Key Skills: {skills_str}"
        
        return summary
    
    async def extract_skills(self, resume_data):
        response = await self._chat(
            f"""
            Deep analysis: Extract ALL technical skills, soft skills, tools, frameworks, 
            certifications, and domain knowledge from this resume data.

            Resume Data:
            {json.dumps(resume_data, indent=2)}

            Provide:
            1. Technical Skills (programming languages, frameworks, tools, databases, cloud, etc.)
            2. Soft Skills (leadership, communication, problem-solving, etc.)
            3. Domain Knowledge (industry-specific expertise)
            4. Certifications (professional certifications, training)
            5. Years of experience (estimate from work history)
            6. Education level and field

            Return JSON with these categories. Return ONLY JSON.
            """
        )
        
        try:
            skills = json.loads(response.get("content", response.get("message", "{}")))
        except:
            skills = {"technical": [], "soft": [], "domain": [], "certifications": []}
        
        self.context["skills"] = skills
        return skills
    
    async def analyze_job_fit(self, job_description):
        resume_data = self.context.get("resume_data", {})
        skills = self.context.get("skills", {})
        
        response = await self._chat(
            f"""
            Agentic Reasoning: Evaluate candidate against job description.

            JOB DESCRIPTION:
            {job_description}

            CANDIDATE RESUME DATA:
            {json.dumps(resume_data, indent=2)}

            EXTRACTED SKILLS:
            {json.dumps(skills, indent=2)}

            Perform deep analysis:
            1. Match detection: Which required skills does candidate have?
            2. Gap analysis: What skills are missing?
            3. Partial matches: Which skills partially align?
            4. Transferable skills: What skills could transfer?
            5. Experience relevance: How relevant is work experience?
            6. Education alignment: Does education match?
            7. Risk factors: Any red flags?

            Return detailed JSON:
            {{
                "score": 0-100,
                "match_level": "excellent|good|partial|poor",
                "strengths": [
                    {{"skill": "", "evidence": "", "relevance": "high|medium|low"}}
                ],
                "gaps": [
                    {{"required": "", "priority": "must-have|nice-to-have"}}
                ],
                "partial_matches": [
                    {{"required": "", "candidate_skill": "", "gap": ""}}
                ],
                "transferable_skills": [],
                "experience_relevance": "high|medium|low",
                "education_alignment": "high|medium|low",
                "risk_flags": [],
                "recommendation": "",
                "reasoning_steps": []
            }}
            Return ONLY JSON.
            """
        )
        
        try:
            evaluation = json.loads(response.get("content", response.get("message", "{}")))
        except:
            evaluation = {"score": 0, "error": "Failed to parse evaluation"}
        
        self.context["evaluation"] = evaluation
        return evaluation
    
    async def research_skills_market(self, skills):
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=f"Research current market demand for: {skills_str}. Find: job trends, salary ranges, popular frameworks, industry adoption rates."
        )
        
        market_data = response.get("content", response.get("message", ""))
        self.context["market_research"] = market_data
        return {"market_research": market_data}
    
    async def validate_claims(self, enable_live_search=True):
        resume_data = self.context.get("resume_data", {})
        
        work = resume_data.get("work", [])
        companies = [w.get("name", "") for w in work if w.get("name")]
        
        if not companies:
            return {"validated": True, "notes": "No companies to validate"}
        
        if enable_live_search:
            response = await self._search(
                f"""
                Web Validation: Verify candidate's work history and credentials using live web search.

                Companies to validate: {companies}

                For each company:
                1. Check if company exists (search the web)
                2. Verify candidate's claimed role/title if possible
                3. Look for any public information about the candidate
                4. Find company website and industry information

                Return JSON:
                {{
                    "validated": true/false,
                    "validations": [
                        {{"company": "", "valid": true/false, "notes": ""}}
                    ],
                    "notes": ""
                }}
                Return ONLY JSON.
                """
            )
        else:
            response = await self._chat(
                f"""
                Validation: Verify candidate's work history and credentials.

                Companies to validate: {companies}

                For each company:
                1. Check if company exists
                2. Verify candidate's claimed role/title if possible

                Return JSON:
                {{
                    "validated": true/false,
                    "validations": [
                        {{"company": "", "valid": true/false, "notes": ""}}
                    ],
                    "notes": ""
                }}
                Return ONLY JSON.
                """
            )
        
        try:
            validation = json.loads(response.get("content", response.get("message", "{}")))
        except:
            validation = {"validated": False, "notes": "Validation failed"}
        
        self.context["validation"] = validation
        return validation
    
    async def _search(self, content, system_prompt=None):
        if system_prompt:
            content = f"{system_prompt}\n\n{content}"
        
        response = await client.web_search(
            thread_id=self.thread_id,
            content=content
        )
        return response
    
    async def comprehensive_evaluate(self, file, job_description, enable_live_search=True):
        await self.initialize()
        
        resume_data = await self.parse_resume(file)
        
        skills = await self.extract_skills(resume_data)
        
        if enable_live_search:
            skill_list = skills.get("technical", [])
            if skill_list:
                market_research = await self.research_skills_market(skill_list)
                self.context["market_research"] = market_research
        
        evaluation = await self.analyze_job_fit(job_description)
        
        validation = await self.validate_claims(enable_live_search=enable_live_search)
        
        evaluation["validation"] = validation
        
        result = {
            "resume_data": resume_data,
            "extracted_skills": skills,
            "evaluation": evaluation
        }
        
        if enable_live_search and "market_research" in self.context:
            result["market_research"] = self.context["market_research"]
        
        return result


async def agentic_comprehensive_evaluate(file, job_description):
    agent = ResumeReasoningAgent()
    return await agent.comprehensive_evaluate(file, job_description)


class DocumentProcessor:
    def __init__(self):
        self.assistant_id = None
        self.thread_id = None
        self.context = {}
    
    async def initialize(self):
        self.assistant_id = await client.create_assistant("Document Processor")
        self.thread_id = await client.create_thread(self.assistant_id)
        return self
    
    async def upload_document(self, file, metadata=None):
        doc_result = await client.upload_document(file, metadata or {}, assistant_id=self.assistant_id)
        self.context["document"] = doc_result
        return doc_result
    
    async def reason(self, question=None):
        question = question or "Analyze this document thoroughly and provide insights about its content, structure, and key information."
        
        response = await client.chat(
            thread_id=self.thread_id,
            content=f"{question}"
        )
        
        reasoning = response.get("content", response.get("message", ""))
        self.context["reasoning"] = reasoning
        return {"reasoning": reasoning}
    
    async def summarize(self):
        response = await client.chat(
            thread_id=self.thread_id,
            content="Provide a comprehensive summary of this document. Include: main topics, key points, structure overview, and important details."
        )
        
        summary = response.get("content", response.get("message", ""))
        self.context["summary"] = summary
        return {"summary": summary}
    
    async def ask(self, question):
        response = await client.chat(
            thread_id=self.thread_id,
            content=question
        )
        
        answer = response.get("content", response.get("message", ""))
        return {"answer": answer}
    
    async def process_document(self, file, metadata=None):
        await self.initialize()
        
        await self.upload_document(file, metadata)
        
        reasoning = await self.reason()
        
        summary = await self.summarize()
        
        return {
            "reasoning": reasoning.get("reasoning"),
            "summary": summary.get("summary")
        }


async def process_resume_document(file, metadata=None):
    processor = DocumentProcessor()
    return await processor.process_document(file, metadata)