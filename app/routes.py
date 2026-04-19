import json
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional, List
from app.tools import evaluate_candidate, parse_resume_internal
from app.tools.reasoning_tools import agentic_comprehensive_evaluate
from app.tools.candidate_websearch import search_candidate, validate_candidate_companies, research_candidate_profile
from app.tools.jd_generator import generate_job_description, research_role_market_trends, analyze_existing_team

router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), metadata: Optional[str] = Form(None)):
    from app.tools.reasoning_tools import client as backboard_client
    
    meta = json.loads(metadata) if metadata else {"type": "resume"}
    
    assistant_id = await backboard_client.create_assistant("Document Processor")
    thread_id = await backboard_client.create_thread(assistant_id)
    doc_result = await backboard_client.upload_document(file, meta, assistant_id=assistant_id)
    
    return {
        "thread_id": thread_id,
        "status": doc_result.get("status")
    }

@router.post("/parse")
async def parse_resume(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content="Parse this document and extract all structured information in JSON Resume format."
        )
        return {"parsed": response.get("content", response.get("message", ""))}
    
    if file:
        result = await parse_resume_internal(file)
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/evaluate")
async def evaluate(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None),
    job_description: str = ""
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content=f"Evaluate this candidate against the job description: {job_description}"
        )
        return {"evaluation": response.get("content", response.get("message", ""))}
    
    if file:
        result = await evaluate_candidate(file, job_description)
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/comprehensive_evaluate")
async def comprehensive_evaluate(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None),
    job_description: str = ""
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content=f"Perform agentic reasoning on this resume for job: {job_description}"
        )
        return {"reasoning": response.get("content", response.get("message", ""))}
    
    if file:
        result = await agentic_comprehensive_evaluate(file, job_description)
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/summarize")
async def summarize_document(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content="Provide a comprehensive summary of this document. Do not include your own thoughts or suggestions."
        )
        return {"summary": response.get("content", response.get("message", ""))}
    
    if file:
        from app.tools.reasoning_tools import DocumentProcessor
        processor = DocumentProcessor()
        await processor.initialize()
        await processor.upload_document(file)
        result = await processor.summarize()
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/reasoning")
async def reasoning_document(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None),
    question: Optional[str] = None
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        q = question or "Analyze this document thoroughly."
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content=q
        )
        return {"reasoning": response.get("content", response.get("message", ""))}
    
    if file:
        from app.tools.reasoning_tools import DocumentProcessor
        processor = DocumentProcessor()
        await processor.initialize()
        await processor.upload_document(file)
        result = await processor.reason(question)
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/qa")
async def question_answer_over_document(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None),
    question: str = Form(...)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.chat(
            thread_id=thread_id,
            web_search="off",
            content=question
        )
        return {"answer": response.get("content", response.get("message", ""))}
    
    if file:
        from app.tools.reasoning_tools import DocumentProcessor
        processor = DocumentProcessor()
        await processor.initialize()
        await processor.upload_document(file)
        result = await processor.ask(question)
        return result
    
    return {"error": "Provide either file or valid thread_id"}

@router.post("/websearch")
async def websearch(
    query: str = Form(""),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    company: Optional[str] = Form(None),
    thread_id: Optional[str] = Form(None)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        
        if name:
            content = f"Research professional profile for {name}" + (f", email: {email}" if email else "") + (f", company: {company}" if company else "")
        else:
            content = query
        
        response = await backboard_client.web_search(
            thread_id=thread_id,
            content=content
        )
        return {"results": response.get("content", response.get("message", ""))}
    
    if name:
        result = await research_candidate_profile(name, email, company)
        return result
    
    result = await search_candidate(query)
    return result

@router.post("/validate")
async def validate_research(
    name: str = Form(...),
    email: Optional[str] = Form(None),
    company: Optional[str] = Form(None),
    thread_id: Optional[str] = Form(None)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        content = f"Research and validate: {name}" + (f", {email}" if email else "") + (f", {company}" if company else "")
        response = await backboard_client.web_search(
            thread_id=thread_id,
            content=content
        )
        return {"validation": response.get("content", response.get("message", ""))}
    
    result = await research_candidate_profile(name, email, company)
    return result

@router.post("/validate-companies")
async def validate_companies_route(
    file: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None)
):
    if thread_id:
        from app.tools.reasoning_tools import client as backboard_client
        response = await backboard_client.web_search(
            thread_id=thread_id,
            content="Research and validate all companies mentioned in this resume. Verify they are real companies and gather information about each."
        )
        return {"validations": response.get("content", response.get("message", ""))}
    
    if file:
        from app.tools.reasoning_tools import ResumeReasoningAgent
        
        agent = ResumeReasoningAgent()
        await agent.initialize()
        resume_data = await agent.parse_resume(file)
        
        result = await validate_candidate_companies(resume_data)
        return result
    
    return {"error": "Provide either file or valid thread_id"}


@router.post("/jd/generate")
async def generate_jd(
    role_requirements: str = Form(...),
    market_trends: Optional[str] = Form(None),
    team_composition_json: Optional[str] = Form(None),
    include_clarity: bool = Form(True),
    include_inclusivity: bool = Form(True),
    include_skill_alignment: bool = Form(True)
):
    team_composition = None
    if team_composition_json:
        try:
            team_composition = json.loads(team_composition_json)
        except:
            pass
    
    result = await generate_job_description(
        role_requirements=role_requirements,
        market_trends=market_trends,
        team_composition=team_composition,
        include_clarity=include_clarity,
        include_inclusivity=include_inclusivity,
        include_skill_alignment=include_skill_alignment
    )
    return {"job_description": result}


@router.post("/jd/research-trends")
async def jd_research_trends(
    role: str = Form(...),
    industry: str = Form("Technology")
):
    result = await research_role_market_trends(role, industry)
    return {"market_trends": result}


@router.post("/jd/analyze-team")
async def jd_analyze_team(
    team_composition_json: str = Form(...)
):
    team_composition = json.loads(team_composition_json)
    result = await analyze_existing_team(team_composition)
    return {"team_analysis": result}