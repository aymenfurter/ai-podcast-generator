# AI Podcast Generator

AI Podcast Generator is an demo app that leverages OpenAI's language models to create engaging podcast scripts effortlessly. Simply input your desired topic or content, and the AI will generate a comprehensive podcast. Enhance your podcasting experience by asking audience questions in real time.

[Watch the Demo Video](https://www.youtube.com/watch?v=CrdZtwO6x6o)

## Installation

1. **Clone the Repository:**
    ```bash
    git clone https://github.com/aymenfurter/ai-podcast-generator.git
    cd ai-podcast-generator
    ```

2. **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set Up Environment Variables:**
    - Create a `.env` file in the root directory.
    - Add the following variables (You'll need an Azure OpenAI Instance):
        ```env
        OPENAI_API_KEY=your_openai_api_key
        OPENAI_API_BASE=your_openai_api_base
        OPENAI_DEPLOYMENT_NAME=your_deployment_name
        OPENAI_REALTIME_DEPLOYMENT_NAME=your_realtime_deployment_name
        OPENAI_API_KEY_B=your_secondary_openai_api_key
        OPENAI_API_BASE_B=your_secondary_openai_api_base
        ```

## Usage

1. **Run the Application:**
    ```bash
    python main.py
    ```

2. **Access the Web Interface:**
    - Open your browser and navigate to `http://localhost:8000`.
    - Enter your podcast topic and generate your script.

## License

This project is licensed under the [MIT License](LICENSE).