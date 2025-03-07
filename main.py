import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from utilities.logger import configure_logging
from utilities.project_discovery_graph import run_workflow
from datetime import datetime

configure_logging()
logger = logging.getLogger(__name__)

def run_pipeline():
    """Main data processing pipeline using LangGraph"""
    logger.info("Starting AI-powered project discovery pipeline...")
    
    try:
        # Run the LangGraph workflow
        result = run_workflow()
        
        if result.get('error'):
            logger.error(f"Pipeline failed: {result['error']}")
        else:
            logger.info(f"Pipeline completed successfully. Status: {result['status']}")
            
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # Run immediately when starting
    run_pipeline()
    # Then schedule future runs
    scheduler.add_job(run_pipeline, 'interval', hours=6, misfire_grace_time=3600)
    print("Starting scheduler... (Ctrl+C to exit)")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler stopped")