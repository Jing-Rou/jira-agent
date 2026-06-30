import os
import logging

# ======================================================================================
#                                    CONFIGURE LOGS 
# ======================================================================================
# ensure the logs directory exists
os.makedirs("jiraToolWrapper/logs", exist_ok=True)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [jira-mcp-server] %(message)s",
    handlers=[
        logging.FileHandler("jiraToolWrapper/logs/jira_mcp_server.log",  mode="a"),
        logging.StreamHandler() #  print log to terminal as well to log file
    ],
)
# creates a logger object.
logger = logging.getLogger("jira-mcp-server")
