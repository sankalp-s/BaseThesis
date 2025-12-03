from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import asyncio
import hashlib
import time
from datetime import datetime
from enum import Enum

# Note: These imports would need actual installation
# pip install fastapi uvicorn sqlalchemy redis asyncpg

app = FastAPI(
    title="Conversational Memory API",
    description="Intelligent memory retention system for conversational AI",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Data Models ====================

class RetentionLevel(str, Enum):
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    IMMEDIATE = "immediate"


class ConversationTurnModel(BaseModel):
    speaker: str
    text: str
    turn_number: int
    timestamp: Optional[float] = None


class AnalyzeRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: str
    turns: List[ConversationTurnModel]
    options: Optional[Dict] = Field(default_factory=dict)


class MemoryItemResponse(BaseModel):
    content: str
    retention: RetentionLevel
    importance_score: float
    turn_number: int
    reasoning: str
    categories: List[str]
    entity_links: Optional[List[str]] = None


class AnalyzeResponse(BaseModel):
    conversation_id: str
    user_id: str
    processing_time_ms: float
    memory_items: List[MemoryItemResponse]
    summary: Dict
    cached: bool = False


class FeedbackRequest(BaseModel):
    conversation_id: str
    user_id: str
    statement: str
    actual_retention: RetentionLevel
    expected_retention: RetentionLevel
    comment: Optional[str] = None


class UserProfileResponse(BaseModel):
    user_id: str
    conversation_count: int
    entities_tracked: int
    important_facts: List[Dict]
    last_updated: datetime


# ==================== Mock Database ====================

class MockDatabase:
    """
    Mock database for demonstration.
    In production, replace with actual PostgreSQL using SQLAlchemy.
    """
    
    def __init__(self):
        self.conversations = {}
        self.user_profiles = {}
        self.feedback = []
    
    async def save_conversation(self, conversation_id: str, data: Dict):
        """Save conversation analysis"""
        self.conversations[conversation_id] = {
            **data,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Retrieve conversation"""
        return self.conversations.get(conversation_id)
    
    async def save_user_profile(self, user_id: str, profile: Dict):
        """Save user profile"""
        self.user_profiles[user_id] = {
            **profile,
            'updated_at': datetime.now()
        }
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get user profile"""
        return self.user_profiles.get(user_id)
    
    async def save_feedback(self, feedback: Dict):
        """Save user feedback"""
        self.feedback.append({
            **feedback,
            'created_at': datetime.now()
        })


# ==================== Mock Cache ====================

class MockCache:
    """
    Mock Redis cache for demonstration.
    In production, replace with actual Redis.
    """
    
    def __init__(self):
        self.cache = {}
        self.ttl = {}
    
    async def get(self, key: str) -> Optional[str]:
        """Get cached value"""
        if key in self.cache:
            if key in self.ttl and time.time() > self.ttl[key]:
                del self.cache[key]
                del self.ttl[key]
                return None
            return self.cache[key]
        return None
    
    async def set(self, key: str, value: str, ttl: int = 300):
        """Set cached value with TTL"""
        self.cache[key] = value
        self.ttl[key] = time.time() + ttl
    
    async def delete(self, key: str):
        """Delete cached value"""
        if key in self.cache:
            del self.cache[key]
        if key in self.ttl:
            del self.ttl[key]


# ==================== Global Instances ====================

db = MockDatabase()
cache = MockCache()


# ==================== Helper Functions ====================

def generate_conversation_id(user_id: str, turns: List[ConversationTurnModel]) -> str:
    """Generate unique conversation ID"""
    content = f"{user_id}_{len(turns)}_{turns[0].text[:50] if turns else ''}"
    return hashlib.md5(content.encode()).hexdigest()


def create_cache_key(conversation_id: str) -> str:
    """Create cache key for conversation"""
    return f"conversation:{conversation_id}"


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key (simple authentication)"""
    # In production, verify against database
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Mock verification
    valid_keys = ["demo_key_123", "test_key_456"]
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return x_api_key


async def process_conversation_async(conversation_id: str, user_id: str, 
                                    turns: List[ConversationTurnModel],
                                    enable_entities: bool = True,
                                    enable_llm: bool = False) -> Dict:
    """Process conversation asynchronously with entity linking"""
    
    from unified_memory_system import UnifiedMemorySystem
    
    # Convert to internal format
    internal_turns = [
        {
            'speaker': t.speaker,
            'content': t.text
        } for t in turns
    ]
    
    # Process with unified memory system (includes entity linking)
    system = UnifiedMemorySystem(
        user_id=user_id,
        enable_llm=enable_llm,
        enable_entities=enable_entities,  # Enable entity linking
        enable_learning=True,
        use_real_llm=False  # Set to True if OpenAI API key available
    )
    results = system.process_conversation(internal_turns)
    
    # Convert to response format
    items_response = []
    all_entities = set()
    
    for result in results:
        item = result.memory_item
        
        # Collect unique entity names
        entity_links = []
        if result.entities:
            for entity in result.entities:
                entity_links.append(entity.canonical_name)
                all_entities.add(entity.canonical_name)
        
        items_response.append(
            MemoryItemResponse(
                content=item.content,
                retention=RetentionLevel(item.retention.value),
                importance_score=item.importance_score,
                turn_number=item.turn_number,
                reasoning=item.reasoning,
                categories=item.categories,
                entity_links=entity_links if entity_links else None
            )
        )
    
    # Calculate summary with entity information
    long_term = sum(1 for r in results if r.memory_item.retention.value == "long_term")
    short_term = sum(1 for r in results if r.memory_item.retention.value == "short_term")
    immediate = sum(1 for r in results if r.memory_item.retention.value == "immediate")
    
    summary = {
        'total_items': len(results),
        'long_term': long_term,
        'short_term': short_term,
        'immediate': immediate,
        'retention_rate': (long_term + short_term) / len(results) if results else 0,
        'entities_found': len(all_entities),
        'entity_list': list(all_entities)
    }
    
    return {
        'conversation_id': conversation_id,
        'user_id': user_id,
        'memory_items': items_response,
        'summary': summary
    }


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Conversational Memory API",
        "version": "2.0.0",
        "status": "active",
        "endpoints": {
            "analyze": "/api/v1/analyze",
            "feedback": "/api/v1/feedback",
            "profile": "/api/v1/users/{user_id}/profile",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "cache": "connected"
    }
@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_conversation(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    enable_entities: bool = True,  # Enable entity linking by default
    enable_llm: bool = False  # Disable LLM by default (costs money)
):
    """_key: str = Depends(verify_api_key)
):
    """
    Analyze a conversation and make memory retention decisions.
    
    - Checks cache first for faster response
    - Processes conversation with memory system
    - Saves to database
    - Returns memory classifications
    """
    
    start_time = time.time()
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or generate_conversation_id(
        request.user_id, request.turns
    )
    
    # Check cache
    cache_key = create_cache_key(conversation_id)
    cached_result = await cache.get(cache_key)
    
    if cached_result:
        import json
        result = json.loads(cached_result)
        result['cached'] = True
        result['processing_time_ms'] = (time.time() - start_time) * 1000
        return result
    
    # Process conversation with entity linking
    result = await process_conversation_async(
        conversation_id, request.user_id, request.turns,
        enable_entities=enable_entities,
        enable_llm=enable_llm
    )
    
    processing_time = (time.time() - start_time) * 1000
    
    response = AnalyzeResponse(
        conversation_id=conversation_id,
        user_id=request.user_id,
        processing_time_ms=processing_time,
        memory_items=result['memory_items'],
        summary=result['summary'],
        cached=False
    )
    
    # Save to cache (background)
    import json
    background_tasks.add_task(
        cache.set,
        cache_key,
        json.dumps(response.dict(), default=str),
        ttl=3600  # 1 hour
    )
    
    # Save to database (background)
    background_tasks.add_task(
        db.save_conversation,
        conversation_id,
        response.dict()
    )
    
    return response


@app.post("/api/v1/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Submit user feedback on memory classification.
    
    - Collects user corrections
    - Updates adaptive learning system
    - Invalidates cache for affected conversations
    """
    
    # Save feedback
    feedback_data = {
        'conversation_id': request.conversation_id,
        'user_id': request.user_id,
        'statement': request.statement,
        'actual_retention': request.actual_retention.value,
        'expected_retention': request.expected_retention.value,
        'comment': request.comment,
        'timestamp': datetime.now().isoformat()
    }
    
    await db.save_feedback(feedback_data)
    
    # Invalidate cache (background)
    cache_key = create_cache_key(request.conversation_id)
    background_tasks.add_task(cache.delete, cache_key)
    
    # Update adaptive learning (would integrate adaptive_learning.py here)
    
    return {
        "status": "success",
        "message": "Feedback recorded",
        "feedback_id": f"{request.user_id}_{int(time.time())}"
    }


@app.get("/api/v1/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get user profile with conversation history and tracked entities.
    """
    
    profile = await db.get_user_profile(user_id)
    
    if not profile:
        # Create empty profile
        profile = {
            'user_id': user_id,
            'conversation_count': 0,
            'entities_tracked': 0,
            'important_facts': [],
            'last_updated': datetime.now()
        }
    
    return UserProfileResponse(**profile)


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Retrieve a specific conversation analysis"""
    
    # Check cache first
    cache_key = create_cache_key(conversation_id)
    cached = await cache.get(cache_key)
    
    if cached:
        import json
        return json.loads(cached)
    
    # Check database
    conversation = await db.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@app.get("/api/v1/stats")
async def get_system_stats(api_key: str = Depends(verify_api_key)):
    """Get system-wide statistics"""
    
    return {
        "total_conversations": len(db.conversations),
        "total_users": len(db.user_profiles),
        "total_feedback": len(db.feedback),
        "cache_size": len(cache.cache),
        "system_status": "operational"
    }


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 80)
    print("Starting Conversational Memory API")
    print("=" * 80)
    print()
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    print()
    print("Demo API Key: demo_key_123")
    print()
    
    uvicorn.run(
        "production_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
