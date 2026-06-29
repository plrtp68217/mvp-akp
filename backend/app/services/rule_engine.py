from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.rule import Rule

class RuleEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def process_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        
        rules = self.db.query(Rule).filter(Rule.is_active == True).all()
        
        for rule in rules:
            try:
                condition_result = eval(rule.condition, {}, data)

                result = {}

                if condition_result:
                    action_parts = rule.action.split('=', 1)
                    if len(action_parts) == 2:
                        field = action_parts[0].strip()
                        value = eval(action_parts[1].strip(), {}, data)
                        result[field] = value
                        
            except Exception as e:
                print(f"Error in rule '{rule.name}': {e}")
                continue
        
        return result