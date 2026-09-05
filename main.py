import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
model_name = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

if not project_id:
    raise RuntimeError(
        "Missing GOOGLE_CLOUD_PROJECT. Add it to your .env file or environment."
    )

client = genai.Client(
    vertexai=True,
    project=project_id,
    location=location,
)

response = client.models.generate_content(
    model=model_name,
    contents="Reply with exactly: Gemini is responding from my Google Cloud project.",
)

print(response.text)
