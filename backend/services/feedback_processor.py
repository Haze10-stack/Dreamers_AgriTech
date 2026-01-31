"""
Feedback Processor

Analyzes farmer's responses to tasks and detects deviations from the plan
Uses Groq LLM to understand natural language feedback
"""

from typing import Dict, Optional, Tuple
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables")

groq_client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class FeedbackProcessor:
    """
    Processes farmer feedback to tasks
    """
    
    def __init__(self):
        self.client = groq_client
        self.model = GROQ_MODEL
    
    def analyze_feedback(
        self,
        planned_action: str,
        farmer_response: str,
        task_description: str = ""
    ) -> Dict:
        """
        Analyze farmer's feedback to determine if they deviated from plan
        
        Args:
            planned_action: What the agent instructed
            farmer_response: What the farmer said they did
            task_description: Optional context about the task
            
        Returns:
            Analysis dictionary with:
            - is_deviation: bool
            - actual_action: str (parsed action)
            - severity: str (minor/moderate/major)
            - impact_summary: str
            - requires_agent_response: bool
        """
        
        prompt = f"""You are analyzing farmer feedback to an agricultural task.

PLANNED ACTION: {planned_action}
TASK DESCRIPTION: {task_description}

FARMER'S RESPONSE: {farmer_response}

Your job is to determine:
1. Did the farmer complete the task as planned? (yes/no/delayed)
2. If not, what did they actually do?
3. Is this a deviation that requires plan adjustment? (yes/no)
4. How severe is the deviation? (minor/moderate/major/none)
5. Brief impact summary (1-2 sentences)

Respond ONLY with JSON in this exact format:
{{
    "completed_as_planned": true/false,
    "actual_action": "what farmer actually did",
    "is_deviation": true/false,
    "deviation_type": "fertilizer_change/delay/method_change/quantity_change/none",
    "severity": "none/minor/moderate/major",
    "impact_summary": "brief impact description",
    "requires_agent_response": true/false
}}

Examples:

PLANNED: Apply 50kg urea fertilizer
FARMER: I applied it yesterday
RESPONSE: {{"completed_as_planned": true, "actual_action": "Applied 50kg urea", "is_deviation": false, "deviation_type": "none", "severity": "none", "impact_summary": "Task completed as planned", "requires_agent_response": false}}

PLANNED: Apply 50kg urea fertilizer
FARMER: I used cow dung instead because urea was expensive
RESPONSE: {{"completed_as_planned": false, "actual_action": "Applied cow dung instead of urea", "is_deviation": true, "deviation_type": "fertilizer_change", "severity": "moderate", "impact_summary": "Organic fertilizer substitution - lower nitrogen content but improves soil health", "requires_agent_response": true}}

PLANNED: Water plants 2 liters per day
FARMER: I forgot yesterday but watered double today
RESPONSE: {{"completed_as_planned": false, "actual_action": "Skipped one day, compensated with double watering", "is_deviation": true, "deviation_type": "delay", "severity": "minor", "impact_summary": "Temporary water stress but compensated", "requires_agent_response": false}}

Now analyze the farmer's response above and return ONLY the JSON, nothing else."""

        try:
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an agricultural expert analyzing farmer actions. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse response
            import json
            result_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result = json.loads(result_text.strip())
            
            # Validate required fields
            required_fields = ["completed_as_planned", "actual_action", "is_deviation", "severity"]
            for field in required_fields:
                if field not in result:
                    result[field] = None
            
            return result
            
        except Exception as e:
            # Fallback: simple keyword-based analysis
            print(f"Error in LLM analysis: {e}")
            return self._fallback_analysis(planned_action, farmer_response)
    
    def _fallback_analysis(self, planned_action: str, farmer_response: str) -> Dict:
        """
        Simple fallback analysis if LLM fails
        """
        response_lower = farmer_response.lower()
        
        # Check for completion keywords
        completion_keywords = ["done", "completed", "did it", "finished", "applied", "yes"]
        completed = any(keyword in response_lower for keyword in completion_keywords)
        
        # Check for deviation keywords
        deviation_keywords = ["instead", "different", "couldn't", "forgot", "didn't", "other"]
        has_deviation = any(keyword in response_lower for keyword in deviation_keywords)
        
        if completed and not has_deviation:
            return {
                "completed_as_planned": True,
                "actual_action": planned_action,
                "is_deviation": False,
                "deviation_type": "none",
                "severity": "none",
                "impact_summary": "Task completed as planned",
                "requires_agent_response": False
            }
        else:
            return {
                "completed_as_planned": False,
                "actual_action": farmer_response,
                "is_deviation": True,
                "deviation_type": "unknown",
                "severity": "moderate",
                "impact_summary": "Farmer response indicates possible deviation - manual review needed",
                "requires_agent_response": True
            }
    
    def calculate_impact_metrics(
        self,
        deviation_type: str,
        severity: str,
        crop_type: str = "general"
    ) -> Dict:
        """
        Calculate estimated impact metrics for a deviation
        
        Args:
            deviation_type: Type of deviation
            severity: Severity level
            crop_type: Type of crop
            
        Returns:
            Impact metrics (yield change %, timeline change in days)
        """
        
        # Impact lookup table (rough estimates)
        impact_table = {
            "fertilizer_change": {
                "minor": {"yield": -2, "timeline": 0},
                "moderate": {"yield": -10, "timeline": 3},
                "major": {"yield": -20, "timeline": 7}
            },
            "delay": {
                "minor": {"yield": -1, "timeline": 1},
                "moderate": {"yield": -5, "timeline": 3},
                "major": {"yield": -15, "timeline": 7}
            },
            "method_change": {
                "minor": {"yield": -3, "timeline": 0},
                "moderate": {"yield": -8, "timeline": 2},
                "major": {"yield": -12, "timeline": 5}
            },
            "quantity_change": {
                "minor": {"yield": -2, "timeline": 0},
                "moderate": {"yield": -7, "timeline": 1},
                "major": {"yield": -15, "timeline": 3}
            }
        }
        
        impact = impact_table.get(deviation_type, {}).get(severity, {"yield": 0, "timeline": 0})
        
        return {
            "estimated_yield_change_percent": impact["yield"],
            "estimated_timeline_change_days": impact["timeline"],
            "confidence": "low"  # Since these are rough estimates
        }
    
    def generate_adaptation_prompt(
        self,
        deviation_analysis: Dict,
        current_plan: str,
        crop_type: str
    ) -> str:
        """
        Generate a prompt for agents to adapt the plan
        
        Args:
            deviation_analysis: Analysis from analyze_feedback()
            current_plan: Current crop plan
            crop_type: Type of crop
            
        Returns:
            Prompt for agents
        """
        
        prompt = f"""DEVIATION DETECTED in {crop_type} crop plan:

PLANNED ACTION: {deviation_analysis.get('planned_action', 'N/A')}
ACTUAL ACTION: {deviation_analysis['actual_action']}
DEVIATION TYPE: {deviation_analysis.get('deviation_type', 'unknown')}
SEVERITY: {deviation_analysis['severity']}
IMPACT: {deviation_analysis['impact_summary']}

CURRENT PLAN:
{current_plan}

Please analyze this deviation and:
1. Assess the impact on crop yield and timeline
2. Recommend adaptations to the plan
3. Create any new tasks needed to compensate
4. Provide guidance to the farmer in supportive language

Respond with your analysis and recommendations."""

        return prompt


# Convenience functions

def process_task_feedback(
    planned_action: str,
    farmer_response: str,
    task_description: str = "",
    crop_type: str = "general"
) -> Tuple[Dict, Dict]:
    """
    Process farmer feedback and return analysis + impact metrics
    
    Returns:
        (analysis, impact_metrics)
    """
    processor = FeedbackProcessor()
    
    analysis = processor.analyze_feedback(planned_action, farmer_response, task_description)
    
    impact_metrics = {}
    if analysis["is_deviation"]:
        impact_metrics = processor.calculate_impact_metrics(
            analysis.get("deviation_type", "unknown"),
            analysis["severity"],
            crop_type
        )
    
    return analysis, impact_metrics


if __name__ == "__main__":
    print("=== Testing Feedback Processor ===\n")
    
    # Test 1: Completed as planned
    print("Test 1: Task completed as planned")
    processor = FeedbackProcessor()
    
    result1 = processor.analyze_feedback(
        planned_action="Apply 50kg urea fertilizer",
        farmer_response="I applied it yesterday morning",
        task_description="Fertilize rice crop"
    )
    print(f"Is deviation: {result1['is_deviation']}")
    print(f"Severity: {result1['severity']}")
    print(f"Impact: {result1['impact_summary']}\n")
    
    # Test 2: Fertilizer substitution
    print("Test 2: Fertilizer substitution")
    result2 = processor.analyze_feedback(
        planned_action="Apply 50kg urea fertilizer",
        farmer_response="I used cow dung instead because urea was too expensive",
        task_description="Fertilize rice crop"
    )
    print(f"Is deviation: {result2['is_deviation']}")
    print(f"Actual action: {result2['actual_action']}")
    print(f"Deviation type: {result2.get('deviation_type')}")
    print(f"Severity: {result2['severity']}")
    print(f"Impact: {result2['impact_summary']}\n")
    
    # Calculate impact
    if result2['is_deviation']:
        impact = processor.calculate_impact_metrics(
            result2.get('deviation_type', 'unknown'),
            result2['severity'],
            "rice"
        )
        print(f"Estimated yield impact: {impact['estimated_yield_change_percent']}%")
        print(f"Timeline impact: {impact['estimated_timeline_change_days']} days\n")
    
    # Test 3: Delay
    print("Test 3: Task delayed")
    result3 = processor.analyze_feedback(
        planned_action="Water plants 2 liters daily",
        farmer_response="I forgot yesterday but gave double water today",
        task_description="Daily irrigation"
    )
    print(f"Is deviation: {result3['is_deviation']}")
    print(f"Severity: {result3['severity']}")
    print(f"Requires agent response: {result3.get('requires_agent_response', False)}\n")
    
    # Test 4: Generate adaptation prompt
    print("Test 4: Generate adaptation prompt")
    if result2['is_deviation']:
        prompt = processor.generate_adaptation_prompt(
            result2,
            "Week 1: Sow seeds, Week 2: First fertilization...",
            "rice"
        )
        print(f"Prompt:\n{prompt[:200]}...\n")