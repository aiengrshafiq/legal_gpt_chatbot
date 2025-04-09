import openai
import config

# Make sure your OpenAI key is available via config
openai.api_key = config.OPENAI_API_KEY

def get_openai_embedding(text: str) -> list:
    try:
        response = openai.Embedding.create(
            model=config.EMBEDDING_MODEL,
            input=text
        )
        return response['data'][0]['embedding']
    except Exception as e:
        print(f"OpenAI Embedding failed: {e}")
        return []
