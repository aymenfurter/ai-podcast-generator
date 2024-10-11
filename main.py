import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any

from openai_client import OpenAIClient, OpenAIClientError
from podcast_generator import PodcastGenerator
from turn_handler import TurnHandler, TurnHandlerError
from app_config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    OPENAI_DEPLOYMENT_NAME,
    OPENAI_REALTIME_DEPLOYMENT_NAME,
    OPENAI_API_KEY_B,
    OPENAI_API_BASE_B
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def lifespan(app: FastAPI):
    """
    Lifespan event handler to manage startup and shutdown events.
    Initializes shared clients on startup and ensures proper closure on shutdown.
    """
    logger.info("Lifespan startup: Initializing OpenAIClient and TurnHandler.")

    app.state.openai_client = OpenAIClient(
        api_key=OPENAI_API_KEY,
        api_base=OPENAI_API_BASE,
        deployment_name=OPENAI_DEPLOYMENT_NAME,
        realtime_deployment_name=OPENAI_REALTIME_DEPLOYMENT_NAME
    )
    await app.state.openai_client.__aenter__() 

    app.state.turn_handler = TurnHandler(
        api_key=OPENAI_API_KEY,
        api_base=OPENAI_API_BASE,
        api_key_b=OPENAI_API_KEY_B,
        api_base_b=OPENAI_API_BASE_B,
        realtime_deployment_name=OPENAI_REALTIME_DEPLOYMENT_NAME
    )
    await app.state.turn_handler._get_session()

    logger.info("OpenAIClient and TurnHandler initialized successfully.")

    try:
        yield
    finally:
        logger.info("Lifespan shutdown: Closing OpenAIClient and TurnHandler.")

        await app.state.openai_client.close()
        await app.state.turn_handler.close()

        logger.info("OpenAIClient and TurnHandler closed successfully.")

app = FastAPI(
    title="Podcast Generator API",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class PodcastRequest(BaseModel):
    topic: str

class TurnRequest(BaseModel):
    podcast_script: str
    combined_transcript: str
    audience_question: Optional[str] = None
    turn: int

async def get_openai_client() -> OpenAIClient:
    return app.state.openai_client

async def get_podcast_generator(client: OpenAIClient = Depends(get_openai_client)) -> PodcastGenerator:
    return PodcastGenerator(client)

async def get_turn_handler() -> TurnHandler:
    return app.state.turn_handler

@app.post("/generate_podcast_script")
async def generate_podcast_script(
    request: PodcastRequest,
    generator: PodcastGenerator = Depends(get_podcast_generator)
) -> Dict[str, Any]:
    """
    Generate a podcast script based on the given topic.

    Args:
        request (PodcastRequest): The request containing the podcast topic.
        generator (PodcastGenerator): The injected PodcastGenerator instance.

    Returns:
        dict: A dictionary containing the generated podcast script.

    Raises:
        HTTPException: If the podcast script generation fails.
    """
    logger.info(f"Received request to generate podcast script for topic: '{request.topic}'")
    try:
        podcast_script = await generator.generate_full_podcast(request.topic)
        logger.info("Podcast script generated successfully.")
        return {"podcast_script": podcast_script}
    except OpenAIClientError as e:
        logger.error(f"Failed to generate podcast script: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate podcast script.") from e
    except Exception as e:
        logger.exception(f"Unexpected error during podcast script generation: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from e

@app.post("/next_turn")
async def next_turn(
    request: TurnRequest,
    turn_handler: TurnHandler = Depends(get_turn_handler)
) -> Dict[str, Any]:
    """
    Handle the next turn in the podcast conversation.

    Args:
        request (TurnRequest): The request containing the turn information.
        turn_handler (TurnHandler): The injected TurnHandler instance.

    Returns:
        dict: A dictionary containing the speaker, transcript, and audio data.

    Raises:
        HTTPException: If handling the turn fails.
    """
    logger.info(f"Received request to handle turn {request.turn}.")
    try:
        response = await turn_handler.handle_turn(request)
        logger.info(f"Turn {request.turn} handled successfully.")
        return response
    except TurnHandlerError as e:
        logger.error(f"Failed to handle turn {request.turn}: {e}")
        raise HTTPException(status_code=500, detail="Failed to handle the turn.") from e
    except Exception as e:
        logger.exception(f"Unexpected error during turn {request.turn} handling: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from e

@app.get("/", response_class=HTMLResponse)
async def read_root() -> str:
    """
    Serve the main HTML page.

    Returns:
        str: The content of the index.html file.

    Raises:
        HTTPException: If index.html is not found.
    """
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
        logger.info("Served index.html successfully.")
        return content
    except FileNotFoundError:
        logger.error("index.html not found.")
        raise HTTPException(status_code=404, detail="index.html not found.")
    except Exception as e:
        logger.exception(f"Error serving index.html: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve the main page.") from e

def main():
    """
    Entry point to run the FastAPI application using Uvicorn.
    """
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
