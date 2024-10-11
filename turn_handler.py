import asyncio
import aiohttp
import base64
import json
import logging
from typing import Any, Dict, Tuple, Optional

from app_config import MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class TurnHandlerError(Exception):
    """Custom exception class for TurnHandler errors."""
    pass


class TurnHandler:
    """
    A class for handling turns in a podcast conversation.
    """

    def __init__(
        self,
        api_key: str,
        api_base: str,
        api_key_b: str,
        api_base_b: str,
        realtime_deployment_name: str
    ) -> None:
        """
        Initialize the TurnHandler.

        Args:
            api_key (str): The primary API key.
            api_base (str): The primary API base URL.
            api_key_b (str): The secondary API key.
            api_base_b (str): The secondary API base URL.
            realtime_deployment_name (str): The name of the realtime deployment.
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.api_key_b = api_key_b
        self.api_base_b = api_base_b.rstrip('/')
        self.realtime_deployment_name = realtime_deployment_name
        self.session: Optional[aiohttp.ClientSession] = None
        logger.debug("TurnHandler initialized with primary and secondary API credentials.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp ClientSession.

        Returns:
            aiohttp.ClientSession: The aiohttp session.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.debug("Created new aiohttp ClientSession for TurnHandler.")
        return self.session

    async def close(self) -> None:
        """
        Close the aiohttp ClientSession if it's open.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("Closed aiohttp ClientSession for TurnHandler.")

    async def handle_turn(self, request: Any) -> Dict[str, Any]:
        """
        Handle a turn in the podcast conversation.

        Args:
            request (Any): The turn request containing podcast script, transcript, and other information.

        Returns:
            Dict[str, Any]: A dictionary containing the speaker, transcript, and audio data.

        Raises:
            TurnHandlerError: If handling the turn fails.
        """
        try:
            audience_question: Optional[str] = getattr(request, 'audience_question', None)
            turn_number: int = getattr(request, 'turn', 0)
            podcast_script: str = getattr(request, 'podcast_script', '')
            combined_transcript: str = getattr(request, 'combined_transcript', '')

            logger.debug(f"Handling turn {turn_number} with audience question: {audience_question}")

            if turn_number % 2 == 0:
                speaker = "Dan"
                instructions = (
                    f"You are Dan, the host of a podcast. Make sure to move to the next talking point by asking "
                    f"questions to Anna. Discuss the following topic: {podcast_script}"
                )
                voice = "dan"
                api_key = self.api_key
                api_base = self.api_base
            else:
                speaker = "Anna"
                instructions = (
                    f"You are Anna, a guest on a podcast. Discuss the following topic: {podcast_script}"
                )
                voice = "marilyn"
                api_key = self.api_key_b
                api_base = self.api_base_b

            if audience_question:
                instructions += (
                    f" Answer the audience question before proceeding (start with 'Oh I see we have a question from the audience'): "
                    f"{audience_question}"
                )

            if turn_number == 6:
                instructions = (
                    "You are Dan, you just held a podcast with your guest Anna. Ask her and the audience for her time "
                    "and thoughts on the podcast. (i.e., do the outro)"
                )

            logger.info(f"Generating response for speaker: {speaker}, turn: {turn_number}")
            audio_base64, transcript = await self.generate_response(
                api_key=api_key,
                api_base=api_base,
                deployment_name=self.realtime_deployment_name,
                context=instructions,
                combined_transcript=combined_transcript,
                voice=voice,
                speaker=speaker
            )

            logger.info(f"Turn {turn_number} handled successfully for speaker: {speaker}")
            return {
                "speaker": speaker,
                "transcript": transcript,
                "audio_base64": audio_base64
            }

        except Exception as e:
            logger.exception(f"Failed to handle turn {getattr(request, 'turn', 'unknown')}: {e}")
            raise TurnHandlerError(f"Failed to handle turn: {e}") from e

    async def generate_response(
        self,
        api_key: str,
        api_base: str,
        deployment_name: str,
        context: str,
        combined_transcript: str,
        voice: str,
        speaker: str
    ) -> Tuple[str, str]:
        """
        Generate a response for the current turn.

        Args:
            api_key (str): The API key to use.
            api_base (str): The API base URL.
            deployment_name (str): The name of the deployment.
            context (str): The context for the response.
            combined_transcript (str): The combined transcript of the conversation so far.
            voice (str): The voice to use for the response.
            speaker (str): The name of the speaker.

        Returns:
            Tuple[str, str]: A tuple containing the base64 encoded audio and the transcript.

        Raises:
            TurnHandlerError: If all retry attempts fail.
        """
        url = f"{api_base.replace('https://', 'wss://')}/openai/realtime"
        query_params = f"?api-version=2024-10-01-preview&deployment={deployment_name}"
        full_url = f"{url}{query_params}"
        headers = {
            "api-key": api_key,
            "OpenAI-Beta": "realtime=v1"
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                async with session.ws_connect(full_url, headers=headers) as ws:
                    logger.debug(f"WebSocket connection established to {full_url}")

                    # Wait for session.created message
                    msg = await ws.receive_json()
                    if msg.get("type") != "session.created":
                        raise TurnHandlerError(f"Expected 'session.created', got '{msg.get('type')}'")
                    logger.debug("Session created successfully.")

                    # Send session.update message with instructions
                    await ws.send_json({
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": (
                                f"You are {speaker}. {context}. Always speak 1-2 sentences at a time. "
                                f"Continue the conversation (CONTINUE WHERE IT LEFT OFF at <your new message>!):\n"
                                f"{combined_transcript}\n\n{speaker}: <your new message>"
                            ),
                            "voice": voice,
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "turn_detection": None,
                            "temperature": 0.6,
                        }
                    })
                    logger.debug("Sent session.update with instructions.")

                    # Send response.create message
                    await ws.send_json({
                        "type": "response.create",
                        "response": {
                            "modalities": ["audio", "text"],
                            "voice": voice,
                            "output_audio_format": "pcm16",
                            "temperature": 0.6,
                        }
                    })
                    logger.debug("Sent response.create message.")

                    audio_data = bytearray()
                    transcript = ""

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            msg_type = data.get("type")
                            logger.debug(f"Received WebSocket message of type: {msg_type}")

                            if msg_type == "response.audio.delta":
                                delta = data.get("delta", "")
                                audio_bytes = base64.b64decode(delta)
                                audio_data.extend(audio_bytes)
                                logger.debug(f"Appended audio delta: {len(audio_bytes)} bytes.")

                            elif msg_type == "response.audio_transcript.done":
                                transcript = data.get("transcript", "")
                                logger.debug("Received completed transcript.")

                            elif msg_type == "response.done":
                                logger.debug("Received response.done message. Closing WebSocket.")
                                break

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            error_msg = msg.data
                            logger.error(f"WebSocket error: {error_msg}")
                            raise TurnHandlerError(f"WebSocket error: {error_msg}")

                    await ws.close()
                    logger.debug("WebSocket connection closed.")

                # Encode audio data to base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                logger.debug("Audio data encoded to base64.")

                if not transcript:
                    logger.warning("Transcript is empty after response.")
                    raise TurnHandlerError("Transcript is empty after response.")

                return audio_base64, transcript

            except (aiohttp.ClientError, TurnHandlerError) as e:
                logger.error(f"Attempt {attempt} failed with error: {e}")
                if attempt < MAX_RETRIES:
                    logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.critical("All retry attempts failed.")
                    raise TurnHandlerError(f"All retry attempts failed: {e}") from e
