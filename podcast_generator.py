from typing import Any, Dict
import logging
from openai_client import OpenAIClient
from openai_client import OpenAIClientError

logger = logging.getLogger(__name__)

class PodcastGenerator:
    """
    A class for generating podcast content using OpenAI's language model.
    """

    def __init__(self, client: OpenAIClient) -> None:
        """
        Initialize the PodcastGenerator.

        Args:
            client (OpenAIClient): An instance of the OpenAIClient.
        """
        self.client = client
        logger.debug("PodcastGenerator initialized with OpenAIClient.")

    async def generate_summary(self, text: str, max_tokens: int = 300) -> str:
        """
        Generate a summary of the given text.

        Args:
            text (str): The input text to summarize.
            max_tokens (int, optional): The maximum number of tokens to generate. Defaults to 300.

        Returns:
            str: The generated summary.

        Raises:
            OpenAIClientError: If the summary generation fails.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a skilled summarizer. Create a concise summary of the following text."
            },
            {
                "role": "user",
                "content": text
            }
        ]
        logger.debug("Generating summary with provided text.")
        summary = await self.client.create_chat_completion(messages, max_tokens=max_tokens)
        logger.info("Summary generated successfully.")
        return summary

    async def chain_of_density(self, summary: str, iterations: int = 3, max_tokens: int = 300) -> str:
        """
        Apply the chain of density technique to compress the summary.

        Args:
            summary (str): The initial summary.
            iterations (int, optional): The number of compression iterations. Defaults to 3.
            max_tokens (int, optional): The maximum number of tokens to generate per iteration. Defaults to 300.

        Returns:
            str: The compressed summary.

        Raises:
            OpenAIClientError: If the compression process fails.
        """
        dense_summary = summary
        logger.debug(f"Starting chain of density with {iterations} iterations.")
        for i in range(1, iterations + 1):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert in information compression. Your task is to make the given text "
                        "more concise while preserving all key information. Aim to reduce the word count by "
                        "25% without losing important content."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Original text:\n{dense_summary}\n\n"
                        "Compress this text, maintaining all key points but reducing verbosity."
                    )
                }
            ]
            logger.debug(f"Compression iteration {i} of {iterations}.")
            dense_summary = await self.client.create_chat_completion(messages, max_tokens=max_tokens)
            logger.info(f"Compression iteration {i} completed successfully.")
        logger.info("Chain of density compression completed.")
        return dense_summary

    async def create_podcast_outline(self, compressed_summary: str, max_tokens: int = 300) -> str:
        """
        Create a podcast outline based on the compressed summary.

        Args:
            compressed_summary (str): The compressed summary of the topic.
            max_tokens (int, optional): The maximum number of tokens to generate. Defaults to 300.

        Returns:
            str: The generated podcast outline.

        Raises:
            OpenAIClientError: If the outline creation fails.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "Create a high-level outline for a podcast episode based on the following summary. "
                    "Include 3-5 main topics to discuss."
                )
            },
            {
                "role": "user",
                "content": compressed_summary
            }
        ]
        logger.debug("Creating podcast outline with compressed summary.")
        outline = await self.client.create_chat_completion(messages, max_tokens=max_tokens)
        logger.info("Podcast outline created successfully.")
        return outline

    async def generate_full_podcast(self, input_text: str) -> str:
        """
        Generate a full podcast script based on the input text.

        Args:
            input_text (str): The input text to base the podcast on.

        Returns:
            str: The generated podcast script.

        Raises:
            OpenAIClientError: If any step in the podcast generation process fails.
        """
        try:
            logger.info("Starting podcast generation process.")

            logger.info("Generating summary...")
            summary = await self.generate_summary(input_text)

            logger.info("Compressing summary...")
            compressed_summary = await self.chain_of_density(summary)

            logger.info("Creating podcast outline...")
            podcast_input = f"## Topic Summary:\n{compressed_summary}\n## Full Document:\n{input_text[:20000]}"
            outline = await self.create_podcast_outline(compressed_summary)

            full_podcast = f"## Talking Points:\n{outline}\n\n## Topic Summary:\n{compressed_summary}\n## Full Document:\n{input_text[:20000]}"
            logger.info("Podcast generation completed successfully.")
            return full_podcast

        except OpenAIClientError as e:
            logger.error(f"Podcast generation failed: {e}")
            raise

