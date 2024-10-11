import aiohttp
import logging
from typing import List, Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    A client for interacting with the OpenAI API.
    """

    API_VERSION = "2023-05-15"

    def __init__(
        self,
        api_key: str,
        api_base: str,
        deployment_name: str,
        realtime_deployment_name: str
    ) -> None:
        """
        Initialize the OpenAIClient.

        Args:
            api_key (str): The API key for authentication.
            api_base (str): The base URL for the API.
            deployment_name (str): The name of the deployment.
            realtime_deployment_name (str): The name of the realtime deployment.
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')  # Ensure no trailing slash
        self.deployment_name = deployment_name
        self.realtime_deployment_name = realtime_deployment_name
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp ClientSession.

        Returns:
            aiohttp.ClientSession: The aiohttp session.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.debug("Created new aiohttp ClientSession.")
        return self.session

    async def close(self) -> None:
        """
        Close the aiohttp ClientSession if it's open.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("Closed aiohttp ClientSession.")

    async def create_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Create a chat completion using the OpenAI API.

        Args:
            messages (List[Dict[str, Any]]): A list of message dictionaries.
            max_tokens (Optional[int], optional): The maximum number of tokens to generate.

        Returns:
            str: The generated chat completion content.

        Raises:
            OpenAIClientError: If the chat completion request fails.
        """
        url = (
            f"{self.api_base}/openai/deployments/{self.deployment_name}/chat/completions"
            f"?api-version={self.API_VERSION}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
        payload: Dict[str, Any] = {
            "messages": messages
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        logger.debug(f"Sending request to {url} with payload: {payload}")

        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.debug(f"Received response status: {response.status}")
                logger.debug(f"Response text: {response_text}")

                if response.status != 200:
                    logger.error(
                        f"Chat completion failed with status {response.status}: {response_text}"
                    )
                    raise OpenAIClientError(
                        f"Chat completion failed: {response.status} - {response_text}"
                    )

                result = await response.json()
                completion = result.get('choices', [{}])[0].get('message', {}).get('content', '')

                if not completion:
                    logger.warning("No content found in the response.")
                    raise OpenAIClientError("No content found in the response.")

                logger.info("Chat completion successful.")
                return completion

        except aiohttp.ClientError as e:
            logger.exception("HTTP request failed.")
            raise OpenAIClientError(f"HTTP request failed: {e}") from e

    async def __aenter__(self) -> 'OpenAIClient':
        """
        Enter the runtime context related to this object.

        Returns:
            OpenAIClient: The client instance.
        """
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        Exit the runtime context and close the session.
        """
        await self.close()


class OpenAIClientError(Exception):
    """Custom exception class for OpenAIClient errors."""
    pass