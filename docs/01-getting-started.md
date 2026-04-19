# Getting Started

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Backboard API key (sign up at https://app.backboard.io)

## Installation

1. Clone the repository and navigate to the project directory

2. Create and activate a virtual environment:
   - Windows: venv\Scripts\activate
   - Linux/Mac: source venv/bin/activate

3. Install dependencies:
   pip install -r requirements.txt

4. Configure environment variables in .env file:
   BACKBOARD_API_KEY=your_api_key_here
   BACKBOARD_LLM_PROVIDER=openai
   BACKBOARD_MODEL_NAME=gpt-5-mini
   BACKBOARD_TIMEOUT=1800

## Running the Application

uvicorn app.main:app --reload

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
