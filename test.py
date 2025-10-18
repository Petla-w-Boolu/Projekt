from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-pro", contents="Korzystająć z danych GUS podaj mi korzystając z formatu JSON wszystkie dane dot ludności mieszkańców w poszególnych osiedlach w płocku")
print(response.text)