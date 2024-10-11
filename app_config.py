import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME")
OPENAI_REALTIME_DEPLOYMENT_NAME = os.getenv("OPENAI_REALTIME_DEPLOYMENT_NAME")
OPENAI_API_KEY_B = os.getenv("OPENAI_API_KEY_B")
OPENAI_API_BASE_B = os.getenv("OPENAI_API_BASE_B")
MAX_RETRIES = 15
RETRY_DELAY = 5

required_env_vars = [
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_DEPLOYMENT_NAME",
    "OPENAI_REALTIME_DEPLOYMENT_NAME",
    "OPENAI_API_KEY_B",
    "OPENAI_API_BASE_B"
]

for var in required_env_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")
