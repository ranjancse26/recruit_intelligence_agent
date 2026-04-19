import json
from typing import Optional, List, Dict, Any
from app.tools.reasoning_tools import client as backboard_client


class JobDescriptionGenerator:
    def __init__(self):
        self.assistant_id = None
        self.thread_id = None
        self.context = {}

    async def initialize(self):
        self.assistant_id = await backboard_client.create_assistant("Job Description Generator")
        self.thread_id = await backboard_client.create_thread(self.assistant_id)
        return self

    async def generate_jd(
        self,
        role_requirements: str,
        market_trends: Optional[str] = None,
        team_composition: Optional[List[Dict[str, Any]]] = None,
        include_clarity: bool = True,
        include_inclusivity: bool = True,
        include_skill_alignment: bool = True
    ):
        team_context = ""
        if team_composition:
            team_context = "\nExisting Team Composition:\n"
            for member in team_composition:
                team_context += f"- {member.get('role', 'Team Member')}: {member.get('skills', 'N/A')}, {member.get('experience', 'N/A')} years exp\n"

        market_context = ""
        if market_trends:
            market_context = f"\nMarket Trends:\n{market_trends}\n"

        prompt = f"""
Generate an optimized job description based on the following inputs:

ROLE REQUIREMENTS:
{role_requirements}
{market_context}
{team_context}

REQUIREMENTS FOR THE JD:
- Clarity: {"Include clear, unambiguous role expectations" if include_clarity else "Not required"}
- Inclusivity: {"Use inclusive language, avoid biases, welcome diverse candidates" if include_inclusivity else "Not required"}
- Skill Alignment: {"Align skills with market trends and team needs" if include_skill_alignment else "Not required"}

Generate a professional job description with the following sections:
1. Job Title
2. Department/Team
3. Location (if applicable)
4. Employment Type
5. About the Role (summary)
6. Key Responsibilities
7. Required Qualifications & Skills
8. Preferred Qualifications & Skills
9. What We Offer (benefits/perks)
10. Equal Opportunity Statement

Ensure:
- Clear, action-oriented language
- Inclusive phrasing (avoid gendered terms, ableist language)
- Realistic qualifications based on market trends
- Skills that complement existing team composition
- No unnecessary requirements that would exclude qualified candidates

Return ONLY valid JSON with these sections. Use empty string for sections that don't apply.
{{
    "job_title": "",
    "department": "",
    "location": "",
    "employment_type": "",
    "about_role": "",
    "responsibilities": [],
    "required_qualifications": [],
    "preferred_qualifications": [],
    "benefits": [],
    "equal_opportunity_statement": "",
    "inclusivity_check": {{
        "gender_neutral": true/false,
        "age_neutral": true/false,
        "ability_inclusive": true/false,
        "cultural_inclusive": true/false
    }},
    "clarity_score": 0-10,
    "notes": ""
}}
Return ONLY JSON.
"""
        response = await backboard_client.chat(
            thread_id=self.thread_id,
            web_search="off",
            content=prompt
        )

        try:
            jd_data = json.loads(response.get("content", response.get("message", "{}")))
        except:
            jd_data = {"raw": response, "error": "Failed to parse JD"}

        self.context["jd"] = jd_data
        return jd_data

    async def research_market_trends(self, role: str, industry: str = "Technology"):
        prompt = f"""
Research current market trends for {role} roles in the {industry} industry.

Provide:
1. Must-have skills (technical)
2. Nice-to-have skills
3. Common job titles for this role
4. Experience level expectations
5. Salary ranges (if available)
6. Popular frameworks/tools in demand
7. Certifications that are valued

Return as JSON:
{{
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "common_titles": [],
    "experience_expectation": "",
    "salary_range": {{"min": "", "max": "", "currency": "USD"}},
    "popular_tools": [],
    "valued_certifications": []
}}
Return ONLY JSON.
"""
        response = await backboard_client.web_search(
            thread_id=self.thread_id,
            content=prompt
        )

        try:
            market_data = json.loads(response.get("content", response.get("message", "{}")))
        except:
            market_data = {"raw": response}

        self.context["market_trends"] = market_data
        return market_data

    async def analyze_team_skills(self, team_composition: List[Dict[str, Any]]):
        if not team_composition:
            return {"gaps": [], "strengths": [], "recommendations": []}

        team_summary = "\n".join([
            f"- {m.get('role', 'Member')}: {', '.join(m.get('skills', []))}"
            for m in team_composition
        ])

        prompt = f"""
Analyze the existing team composition and provide recommendations for the new role.

Team Composition:
{team_summary}

Provide:
1. Skill gaps that new hire should fill
2. Areas where team is strong
3. Recommendations for complementary skills
4. Collaboration opportunities

Return as JSON:
{{
    "skill_gaps": [],
    "team_strengths": [],
    "recommendations": [],
    "collaboration_opportunities": []
}}
Return ONLY JSON.
"""
        response = await backboard_client.chat(
            thread_id=self.thread_id,
            web_search="off",
            content=prompt
        )

        try:
            analysis = json.loads(response.get("content", response.get("message", "{}")))
        except:
            analysis = {"raw": response}

        self.context["team_analysis"] = analysis
        return analysis


async def generate_job_description(
    role_requirements: str,
    market_trends: Optional[str] = None,
    team_composition: Optional[List[Dict[str, Any]]] = None,
    include_clarity: bool = True,
    include_inclusivity: bool = True,
    include_skill_alignment: bool = True
) -> Dict[str, Any]:
    generator = JobDescriptionGenerator()
    await generator.initialize()

    return await generator.generate_jd(
        role_requirements=role_requirements,
        market_trends=market_trends,
        team_composition=team_composition,
        include_clarity=include_clarity,
        include_inclusivity=include_inclusivity,
        include_skill_alignment=include_skill_alignment
    )


async def research_role_market_trends(role: str, industry: str = "Technology") -> Dict[str, Any]:
    generator = JobDescriptionGenerator()
    await generator.initialize()

    return await generator.research_market_trends(role, industry)


async def analyze_existing_team(team_composition: List[Dict[str, Any]]) -> Dict[str, Any]:
    generator = JobDescriptionGenerator()
    await generator.initialize()

    return await generator.analyze_team_skills(team_composition)