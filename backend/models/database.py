"""
MongoDB database connection and models using Motor (async driver)
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
from datetime import datetime
from bson import ObjectId
from config.settings import settings


class Database:
    """MongoDB database manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        cls.client = AsyncIOMotorClient(settings.MONGODB_URI)
        cls.db = cls.client[settings.MONGODB_DB_NAME]
        print(f"✅ Connected to MongoDB: {settings.MONGODB_DB_NAME}")
        
        # Create indexes for better query performance
        await cls.create_indexes()
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("❌ MongoDB connection closed")
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes"""
        # Farmers collection indexes
        await cls.db.farmers.create_index("phone", unique=True)
        
        # Crop seasons indexes
        await cls.db.crop_seasons.create_index("farmer_id")
        await cls.db.crop_seasons.create_index("status")
        await cls.db.crop_seasons.create_index("current_phase")
        
        # Tasks indexes
        await cls.db.tasks.create_index("season_id")
        await cls.db.tasks.create_index("status")
        await cls.db.tasks.create_index("scheduled_date")
        
        # Conversations index
        await cls.db.agent_conversations.create_index("season_id")
        
        print("✅ Database indexes created")
    
    @classmethod
    def get_sync_db(cls):
        """Get synchronous database connection (for non-async operations)"""
        sync_client = MongoClient(settings.MONGODB_URI)
        return sync_client[settings.MONGODB_DB_NAME]


# Collection helper functions
def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    
    if isinstance(doc, dict):
        doc = doc.copy()
        if '_id' in doc and isinstance(doc['_id'], ObjectId):
            doc['_id'] = str(doc['_id'])
        
        # Convert ObjectId fields
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, dict):
                doc[key] = serialize_doc(value)
            elif isinstance(value, list):
                doc[key] = serialize_doc(value)
        
        return doc
    
    return doc


# Data models (Pydantic schemas for validation)
from pydantic import BaseModel, Field
from typing import List, Dict, Any


class FarmerModel(BaseModel):
    """Farmer data model"""
    name: str
    phone: str
    location: str
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class CropSeasonModel(BaseModel):
    """Crop season data model"""
    farmer_id: str
    crop_type: str
    variety: Optional[str] = None
    start_date: datetime
    expected_harvest_date: Optional[datetime] = None
    current_phase: str = "pre_sowing"  # pre_sowing, growth, harvest, completed
    farmer_type: str  # greenhouse or normal
    soil_type: Optional[str] = None
    previous_crop: Optional[str] = None
    initial_weather_data: Optional[Dict] = None
    crop_plan: Optional[Dict] = None
    yield_prediction: Optional[float] = None
    actual_yield: Optional[float] = None
    status: str = "active"  # active, completed, failed
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class TaskModel(BaseModel):
    """Task data model"""
    season_id: str
    task_name: str
    description: Optional[str] = None
    planned_action: str
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: str = "pending"  # pending, completed, modified, skipped
    priority: str = "medium"  # low, medium, high, critical
    created_by_agent: str  # pre_sowing, growth, harvest
    phase: str  # Which phase this task belongs to
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class TaskCompletionModel(BaseModel):
    """Task completion data model"""
    task_id: str
    farmer_response: str
    actual_action: Optional[str] = None
    completion_date: Optional[datetime] = Field(default_factory=datetime.utcnow)
    is_deviation: bool = False
    agent_analysis: Optional[str] = None


class DeviationModel(BaseModel):
    """Deviation tracking model"""
    season_id: str
    task_id: Optional[str] = None
    deviation_type: str
    planned_action: str
    actual_action: str
    severity: str  # minor, moderate, major
    impact_on_yield: Optional[float] = None
    impact_on_timeline: Optional[int] = None
    agent_adaptation: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class AgentConversationModel(BaseModel):
    """Agent conversation model"""
    season_id: str
    farmer_message: str
    agent_debate: List[Dict[str, str]] = []
    final_response: Optional[str] = None
    active_agents: List[str] = []
    phase: str
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class SimulationDataModel(BaseModel):
    """Greenhouse simulation data model"""
    season_id: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    light_intensity: Optional[float] = None
    co2_level: Optional[float] = None
    water_given: Optional[float] = None
    fertilizer_given: Optional[str] = None
    plant_height: Optional[float] = None
    leaf_count: Optional[int] = None
    health_score: Optional[float] = None
    agent_action: Optional[str] = None


class PlantObservationModel(BaseModel):
    """Plant observation model for normal farmers"""
    season_id: str
    observation_date: datetime = Field(default_factory=datetime.utcnow)
    farmer_description: str
    plant_height: Optional[float] = None
    plant_color: Optional[str] = None
    plant_smell: Optional[str] = None
    visible_issues: Optional[str] = None
    agent_analysis: Optional[str] = None
    recommended_actions: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)