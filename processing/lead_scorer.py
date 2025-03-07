import logging
from datetime import datetime, timedelta
from config.settings import Config

class LeadScorer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_year = datetime.now().year
        
    def calculate_priority_score(self, project):
        """
        Calculate priority score based on contract value, steel requirement, timeline, and recency
        """
        try:
            # Extract key metrics
            contract_value = float(project.get('value', 0))  # in crores
            steel_requirement = self._get_conservative_steel_estimate(project)
            timeline_months = self._get_timeline_months(project)
            recency_factor = self._calculate_recency_factor(project)
            
            # Calculate priority score using the formula:
            # (Contract Value + Estimated Steel Tons) / (Timeline in Months)^2 * Recency Factor
            if timeline_months > 0:
                priority_score = (contract_value + steel_requirement) / (timeline_months ** 2) * recency_factor
            else:
                priority_score = 0
                
            # Add scoring details for transparency
            scoring_details = {
                'contract_value': contract_value,
                'steel_requirement': steel_requirement,
                'timeline_months': timeline_months,
                'recency_factor': recency_factor,
                'final_score': priority_score
            }
            
            return priority_score, scoring_details
            
        except Exception as e:
            self.logger.error(f"Error calculating priority score: {str(e)}")
            return 0, {}
    
    def _get_conservative_steel_estimate(self, project):
        """
        Get conservative steel estimate by applying 0.8 factor to the calculated requirement
        """
        try:
            # Get base steel requirement
            steel_req = project.get('steel_requirement', 0)
            
            # If no explicit requirement, estimate based on project type and value
            if not steel_req:
                project_type = self._determine_project_type(project)
                value_in_cr = project.get('value', 0)
                
                # Use Config's steel calculation rates with conservative factor
                base_rate = Config.PROJECT_DISCOVERY['steel_calculation_rates'].get(
                    project_type, 
                    Config.PROJECT_DISCOVERY['steel_calculation_rates']['infrastructure']
                )
                
                steel_req = value_in_cr * base_rate
            
            # Apply 0.8 conservative factor
            return steel_req * 0.8
            
        except Exception as e:
            self.logger.error(f"Error calculating conservative steel estimate: {str(e)}")
            return 0
    
    def _get_timeline_months(self, project):
        """
        Calculate months until project starts, default to 24 if unspecified
        """
        try:
            start_date = project.get('start_date')
            if not start_date:
                return 24  # Default timeline
                
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            
            months = (start_date - datetime.now()).days / 30
            return max(1, months)  # Ensure at least 1 month
            
        except Exception as e:
            self.logger.error(f"Error calculating timeline months: {str(e)}")
            return 24
    
    def _calculate_recency_factor(self, project):
        """
        Calculate recency factor based on news date
        """
        try:
            news_date = project.get('news_date', datetime.now())
            if isinstance(news_date, str):
                news_date = datetime.strptime(news_date, '%Y-%m-%d')
            
            months_old = (datetime.now() - news_date).days / 30
            
            if months_old <= 6:
                return 1.0
            elif months_old <= 12:
                return 0.7
            else:
                return 0.3
                
        except Exception as e:
            self.logger.error(f"Error calculating recency factor: {str(e)}")
            return 0.3
    
    def _determine_project_type(self, project):
        """
        Determine project type based on title and description
        """
        title = project.get('title', '').lower()
        description = project.get('description', '').lower()
        text = f"{title} {description}"
        
        if any(term in text for term in ['metro', 'railway', 'rail']):
            return 'metro'
        elif any(term in text for term in ['high rise', 'building', 'residential', 'commercial']):
            return 'high_rise'
        elif any(term in text for term in ['industrial', 'factory', 'plant', 'manufacturing']):
            return 'industrial'
        else:
            return 'infrastructure'

    def score_lead(self, project):
        """Calculate lead score 0-100 based on multiple factors"""
        score = 0
        
        # Budget scoring
        if project['budget'] >= Config.BUDGET_THRESHOLD:
            score += Config.BUDGET_WEIGHT * 100
            
        # Timeline scoring
        years_diff = project['start_date'].year - self.current_year
        if years_diff <= 1:
            score += Config.TIMELINE_WEIGHT * (100 - (years_diff * 30))
            
        # Phase scoring
        phase_score = self._calculate_phase_score(project['description'])
        score += Config.PHASE_WEIGHT * phase_score
        
        # Keyword scoring
        keyword_score = len(project['keywords']) * 10
        score += Config.KEYWORD_WEIGHT * keyword_score
        
        return min(100, max(0, round(score)))

    def _calculate_phase_score(self, description):
        """Score based on project phase mentioning steel requirements"""
        phase_keywords = {
            'initial': ['foundation', 'excavation', 'structural'],
            'mid': ['concrete', 'cement', 'formwork'],
            'final': ['painting', 'finishing']
        }
        
        if any(kw in description.lower() for kw in phase_keywords['initial']):
            return 80  # Highest score for steel-relevant phases
        elif any(kw in description.lower() for kw in phase_keywords['mid']):
            return 40
        else:
            return 20