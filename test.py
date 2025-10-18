from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client()

with open('prompt.txt', 'r') as f:
    response = client.models.generate_content(
        model="gemini-2.5-pro", contents=f.readlines())
print(response.text)