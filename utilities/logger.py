import logging
import os
from datetime import datetime

def configure_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"jsw_agent_{timestamp}.log")
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # Ensure all loggers propagate to root
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.propagate = True
        logger.setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")
    return logger