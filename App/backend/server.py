from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize AI chat
def get_sentiment_chat():
    return LlmChat(
        api_key=os.environ.get('EMERGENT_LLM_KEY'),
        session_id="sentiment-analysis",
        system_message="You are a mental health AI assistant specializing in sentiment analysis for students. Analyze the emotional tone and provide supportive insights. Be empathetic, non-judgmental, and focus on student wellness."
    ).with_model("openai", "gpt-4o-mini")

def get_companion_chat(session_id: str):
    return LlmChat(
        api_key=os.environ.get('EMERGENT_LLM_KEY'),
        session_id=session_id,
        system_message="You are Serenity, a compassionate AI companion for students dealing with stress, anxiety, and academic pressure. Provide emotional support, coping strategies, and encourage healthy habits. Be warm, understanding, and never provide medical advice. Focus on student wellness and academic balance."
    ).with_model("openai", "gpt-4o-mini")

# Models
class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str
    mood_score: Optional[float] = None
    sentiment: Optional[str] = None
    tags: List[str] = []
    ai_insights: Optional[str] = None
    privacy_level: str = "private"  # private, anonymous
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class JournalEntryCreate(BaseModel):
    user_id: str
    content: str
    tags: List[str] = []
    privacy_level: str = "private"

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    message: str
    response: str
    sentiment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class MoodCheckIn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    mood_level: int  # 1-5 scale
    stress_level: int  # 1-5 scale
    energy_level: int  # 1-5 scale
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MoodCheckInCreate(BaseModel):
    user_id: str
    mood_level: int
    stress_level: int
    energy_level: int
    notes: Optional[str] = None

class UserStats(BaseModel):
    total_entries: int
    avg_mood: float
    avg_stress: float
    recent_patterns: List[str]
    recommendations: List[str]

# Helper functions
def prepare_for_mongo(data):
    """Convert datetime objects to ISO strings for MongoDB storage"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
    return data

async def analyze_sentiment(content: str) -> Dict[str, Any]:
    """Analyze sentiment and provide insights using AI"""
    try:
        chat = get_sentiment_chat()
        prompt = f"""
        Analyze the following journal entry from a student and provide:
        1. Sentiment (positive, neutral, negative, mixed)
        2. Mood score (1-10, where 1 is very negative, 10 is very positive)
        3. Brief supportive insight (2-3 sentences)
        4. Any stress indicators detected
        
        Journal entry: "{content}"
        
        Respond in this format:
        Sentiment: [sentiment]
        Mood Score: [score]
        Insight: [insight]
        Stress Indicators: [indicators or none]
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse AI response
        lines = response.strip().split('\n')
        result = {
            'sentiment': 'neutral',
            'mood_score': 5.0,
            'insights': 'Take care of yourself and remember that it\'s okay to have ups and downs.',
            'stress_indicators': []
        }
        
        for line in lines:
            if line.startswith('Sentiment:'):
                result['sentiment'] = line.split(':', 1)[1].strip().lower()
            elif line.startswith('Mood Score:'):
                try:
                    result['mood_score'] = float(line.split(':', 1)[1].strip())
                except:
                    result['mood_score'] = 5.0
            elif line.startswith('Insight:'):
                result['insights'] = line.split(':', 1)[1].strip()
            elif line.startswith('Stress Indicators:'):
                indicators_text = line.split(':', 1)[1].strip()
                if indicators_text.lower() != 'none':
                    result['stress_indicators'] = [indicators_text]
        
        return result
    except Exception as e:
        logging.error(f"Error in sentiment analysis: {e}")
        return {
            'sentiment': 'neutral',
            'mood_score': 5.0,
            'insights': 'Thank you for sharing. Remember to take care of yourself.',
            'stress_indicators': []
        }

# Routes
@api_router.get("/")
async def root():
    return {"message": "Serenity Student API - Your AI-powered wellness companion"}

# Journal routes
@api_router.post("/journal", response_model=JournalEntry)
async def create_journal_entry(entry: JournalEntryCreate):
    try:
        # Analyze sentiment
        analysis = await analyze_sentiment(entry.content)
        
        # Create entry with AI analysis
        entry_dict = entry.dict()
        entry_dict.update({
            'mood_score': analysis['mood_score'],
            'sentiment': analysis['sentiment'],
            'ai_insights': analysis['insights']
        })
        
        journal_entry = JournalEntry(**entry_dict)
        entry_to_store = prepare_for_mongo(journal_entry.dict())
        
        await db.journal_entries.insert_one(entry_to_store)
        return journal_entry
    except Exception as e:
        logging.error(f"Error creating journal entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to create journal entry")

@api_router.get("/journal/{user_id}", response_model=List[JournalEntry])
async def get_journal_entries(user_id: str, limit: int = 20):
    try:
        entries = await db.journal_entries.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return [JournalEntry(**entry) for entry in entries]
    except Exception as e:
        logging.error(f"Error fetching journal entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch journal entries")

# Chat routes
@api_router.post("/chat", response_model=ChatMessage)
async def chat_with_companion(chat_req: ChatRequest):
    try:
        # Get AI response
        chat = get_companion_chat(chat_req.session_id)
        user_message = UserMessage(text=chat_req.message)
        ai_response = await chat.send_message(user_message)
        
        # Analyze message sentiment
        analysis = await analyze_sentiment(chat_req.message)
        
        # Store chat message
        chat_message = ChatMessage(
            user_id=chat_req.user_id,
            session_id=chat_req.session_id,
            message=chat_req.message,
            response=ai_response,
            sentiment=analysis['sentiment']
        )
        
        message_to_store = prepare_for_mongo(chat_message.dict())
        await db.chat_messages.insert_one(message_to_store)
        
        return chat_message
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")

@api_router.get("/chat/{user_id}/{session_id}", response_model=List[ChatMessage])
async def get_chat_history(user_id: str, session_id: str, limit: int = 50):
    try:
        messages = await db.chat_messages.find(
            {"user_id": user_id, "session_id": session_id}
        ).sort("created_at", 1).limit(limit).to_list(limit)
        
        return [ChatMessage(**msg) for msg in messages]
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")

# Mood check-in routes
@api_router.post("/mood-checkin", response_model=MoodCheckIn)
async def create_mood_checkin(checkin: MoodCheckInCreate):
    try:
        mood_checkin = MoodCheckIn(**checkin.dict())
        checkin_to_store = prepare_for_mongo(mood_checkin.dict())
        
        await db.mood_checkins.insert_one(checkin_to_store)
        return mood_checkin
    except Exception as e:
        logging.error(f"Error creating mood check-in: {e}")
        raise HTTPException(status_code=500, detail="Failed to create mood check-in")

@api_router.get("/mood-checkin/{user_id}", response_model=List[MoodCheckIn])
async def get_mood_checkins(user_id: str, limit: int = 30):
    try:
        checkins = await db.mood_checkins.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return [MoodCheckIn(**checkin) for checkin in checkins]
    except Exception as e:
        logging.error(f"Error fetching mood check-ins: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch mood check-ins")

# Analytics routes
@api_router.get("/stats/{user_id}", response_model=UserStats)
async def get_user_stats(user_id: str):
    try:
        # Get journal entries count
        total_entries = await db.journal_entries.count_documents({"user_id": user_id})
        
        # Get recent mood check-ins for averages
        recent_checkins = await db.mood_checkins.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        avg_mood = sum(c['mood_level'] for c in recent_checkins) / len(recent_checkins) if recent_checkins else 3.0
        avg_stress = sum(c['stress_level'] for c in recent_checkins) / len(recent_checkins) if recent_checkins else 3.0
        
        # Generate recommendations based on patterns
        recommendations = []
        if avg_stress > 3.5:
            recommendations.append("Consider taking regular breaks during study sessions")
            recommendations.append("Try deep breathing exercises when feeling overwhelmed")
        if avg_mood < 2.5:
            recommendations.append("Engage in activities that bring you joy")
            recommendations.append("Consider reaching out to friends or counselors")
        if not recommendations:
            recommendations.append("Keep up the great work on your wellness journey!")
        
        recent_patterns = []
        if avg_stress > 3.5:
            recent_patterns.append("Elevated stress levels detected")
        if avg_mood > 3.5:
            recent_patterns.append("Generally positive mood")
        elif avg_mood < 2.5:
            recent_patterns.append("Lower mood levels - consider self-care")
        
        return UserStats(
            total_entries=total_entries,
            avg_mood=round(avg_mood, 1),
            avg_stress=round(avg_stress, 1),
            recent_patterns=recent_patterns,
            recommendations=recommendations
        )
    except Exception as e:
        logging.error(f"Error fetching user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user statistics")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()