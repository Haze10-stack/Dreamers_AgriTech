"""
Phase Manager

Determines and manages crop lifecycle phases
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


class PhaseManager:
    """
    Manages crop lifecycle phases
    """
    
    PHASES = ["pre_sowing", "growth", "harvest", "completed"]
    
    # Typical days for each crop (can be customized)
    CROP_DURATIONS = {
        "rice": {"growth_days": 120, "harvest_window": 7},
        "wheat": {"growth_days": 120, "harvest_window": 7},
        "moong_dal": {"growth_days": 60, "harvest_window": 5},
        "cotton": {"growth_days": 150, "harvest_window": 14},
        "tomato": {"growth_days": 75, "harvest_window": 10},
        "cucumber": {"growth_days": 55, "harvest_window": 7},
        "lettuce": {"growth_days": 45, "harvest_window": 5},
        "default": {"growth_days": 90, "harvest_window": 7}
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.seasons_collection = db.crop_seasons
    
    async def get_current_phase(self, season_id: str) -> str:
        """
        Determine current phase based on season data
        
        Args:
            season_id: Crop season ID
            
        Returns:
            Current phase name
        """
        season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
        
        if not season:
            return "pre_sowing"
        
        # If manually set, return that
        if "current_phase" in season:
            return season["current_phase"]
        
        # Calculate based on dates
        if "start_date" not in season:
            return "pre_sowing"
        
        start_date = season["start_date"]
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        
        days_elapsed = (datetime.utcnow() - start_date).days
        
        crop_type = season.get("crop_type", "default").lower()
        duration_info = self.CROP_DURATIONS.get(crop_type, self.CROP_DURATIONS["default"])
        
        growth_days = duration_info["growth_days"]
        harvest_window = duration_info["harvest_window"]
        
        if days_elapsed < 0:
            return "pre_sowing"
        elif days_elapsed < growth_days:
            return "growth"
        elif days_elapsed < growth_days + harvest_window:
            return "harvest"
        else:
            return "completed"
    
    async def update_phase(self, season_id: str, new_phase: str) -> bool:
        """
        Manually update phase
        
        Args:
            season_id: Crop season ID
            new_phase: New phase name
            
        Returns:
            Success status
        """
        if new_phase not in self.PHASES:
            return False
        
        result = await self.seasons_collection.update_one(
            {"_id": ObjectId(season_id)},
            {
                "$set": {
                    "current_phase": new_phase,
                    "phase_updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def can_transition_to_harvest(self, season_id: str) -> Dict:
        """
        Check if crop is ready for harvest phase
        
        Returns:
            Dict with readiness status and reasons
        """
        season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
        
        if not season:
            return {"ready": False, "reasons": ["Season not found"]}
        
        reasons = []
        ready = True
        
        # Check age
        if "start_date" in season:
            start_date = season["start_date"]
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            
            days_elapsed = (datetime.utcnow() - start_date).days
            crop_type = season.get("crop_type", "default").lower()
            min_days = self.CROP_DURATIONS.get(crop_type, self.CROP_DURATIONS["default"])["growth_days"]
            
            if days_elapsed < min_days * 0.9:  # 90% of growth period
                ready = False
                reasons.append(f"Crop too young (needs ~{min_days - days_elapsed} more days)")
            else:
                reasons.append(f"Crop age: {days_elapsed} days (✓)")
        else:
            ready = False
            reasons.append("Start date not set")
        
        # Check health score (if available)
        if "health_score" in season:
            health = season["health_score"]
            if health < 50:
                ready = False
                reasons.append(f"Health too low: {health}/100")
            else:
                reasons.append(f"Health: {health}/100 (✓)")
        
        # Check if there are critical pending tasks
        from .task_service import TaskService
        task_service = TaskService(self.db)
        pending_tasks = await task_service.get_pending_tasks(season_id)
        
        critical_tasks = [t for t in pending_tasks if t.get("priority") == "critical"]
        if critical_tasks:
            ready = False
            reasons.append(f"{len(critical_tasks)} critical tasks pending")
        else:
            reasons.append("No critical tasks pending (✓)")
        
        return {
            "ready": ready,
            "reasons": reasons,
            "recommendation": "Can transition to harvest" if ready else "Continue growth phase"
        }
    
    async def auto_transition_phases(self, season_id: str) -> Optional[str]:
        """
        Automatically transition phases based on conditions
        
        Returns:
            New phase if transition occurred, None otherwise
        """
        current_phase = await self.get_current_phase(season_id)
        
        if current_phase == "pre_sowing":
            # Check if season has started (has start_date)
            season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
            if season and "start_date" in season:
                await self.update_phase(season_id, "growth")
                return "growth"
        
        elif current_phase == "growth":
            # Check if ready for harvest
            readiness = await self.can_transition_to_harvest(season_id)
            if readiness["ready"]:
                await self.update_phase(season_id, "harvest")
                return "harvest"
        
        elif current_phase == "harvest":
            # Check if harvest is complete (has actual_harvest_date)
            season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
            if season and "actual_harvest_date" in season:
                await self.update_phase(season_id, "completed")
                return "completed"
        
        return None
    
    async def get_phase_summary(self, season_id: str) -> Dict:
        """
        Get comprehensive phase summary
        """
        season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
        
        if not season:
            return {"error": "Season not found"}
        
        current_phase = await self.get_current_phase(season_id)
        
        summary = {
            "season_id": season_id,
            "current_phase": current_phase,
            "crop_type": season.get("crop_type", "unknown"),
        }
        
        # Add phase-specific info
        if "start_date" in season:
            start_date = season["start_date"]
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            
            days_elapsed = (datetime.utcnow() - start_date).days
            crop_type = season.get("crop_type", "default").lower()
            duration_info = self.CROP_DURATIONS.get(crop_type, self.CROP_DURATIONS["default"])
            
            summary.update({
                "days_elapsed": days_elapsed,
                "expected_harvest_in_days": max(0, duration_info["growth_days"] - days_elapsed),
                "start_date": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
            })
        
        # Add expected harvest date
        if "expected_harvest_date" in season:
            summary["expected_harvest_date"] = season["expected_harvest_date"]
        
        # Add readiness for next phase
        if current_phase == "growth":
            readiness = await self.can_transition_to_harvest(season_id)
            summary["harvest_readiness"] = readiness
        
        return summary
    
    async def get_phase_recommendations(self, season_id: str) -> List[str]:
        """
        Get recommendations based on current phase
        """
        current_phase = await self.get_current_phase(season_id)
        season = await self.seasons_collection.find_one({"_id": ObjectId(season_id)})
        
        recommendations = []
        
        if current_phase == "pre_sowing":
            recommendations.extend([
                "Choose the right crop for your soil and climate",
                "Check weather forecasts for the next 6 months",
                "Compare market prices for different crops",
                "Prepare your field (plowing, leveling)",
                "Source quality seeds from reliable vendors"
            ])
        
        elif current_phase == "growth":
            if season and "start_date" in season:
                start_date = season["start_date"]
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date)
                days_elapsed = (datetime.utcnow() - start_date).days
                
                if days_elapsed < 20:
                    recommendations.extend([
                        "Monitor germination and early growth",
                        "Ensure adequate watering",
                        "Watch for early pests and diseases",
                        "Apply first fertilization as scheduled"
                    ])
                elif days_elapsed < 60:
                    recommendations.extend([
                        "Monitor plant health daily",
                        "Check for nutrient deficiencies",
                        "Control weeds regularly",
                        "Adjust watering based on weather"
                    ])
                else:
                    recommendations.extend([
                        "Watch for harvest readiness signs",
                        "Prepare for harvest (equipment, labor)",
                        "Check market prices",
                        "Plan post-harvest storage"
                    ])
        
        elif current_phase == "harvest":
            recommendations.extend([
                "Harvest at optimal time (early morning usually best)",
                "Handle crops carefully to avoid damage",
                "Dry and store properly",
                "Compare prices at different markets",
                "Sell when prices are favorable"
            ])
        
        elif current_phase == "completed":
            recommendations.extend([
                "Analyze what went well and what could improve",
                "Prepare soil for next crop (add organic matter)",
                "Consider crop rotation",
                "Plan next season based on this season's learnings"
            ])
        
        return recommendations


if __name__ == "__main__":
    print("=== Phase Manager Module Loaded ===")
    print("Available phases:", PhaseManager.PHASES)
    print("Crop durations available for:", list(PhaseManager.CROP_DURATIONS.keys()))