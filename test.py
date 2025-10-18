import requests

def znajdz_id_jednostki(nazwa: str, api_key: str):
    """
    Przeszukuje API GUS w poszukiwaniu jednostek terytorialnych
    i wyświetla ich nazwy, ID oraz poziomy administracyjne.
    """
    headers = {"X-ClientId": api_key}
    # Szukamy jednostek na wszystkich poziomach szczegółowości
    url = f"https://bdl.stat.gov.pl/api/v1/units?name={nazwa}&page-size=20"

    print(f"🔎 Szukam wszystkich jednostek administracyjnych dla: '{nazwa}'...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get('results'):
            print("\n--- Znalezione jednostki dla 'Płock' ---")
            for unit in data['results']:
                # Wyświetlamy kluczowe informacje: nazwę, ID i rodzaj jednostki
                print(f"✅ Nazwa: {unit['name']}\n   ID: {unit['id']}\n   Rodzaj: {unit['kind']}\n")
        else:
            print("❌ Nie znaleziono żadnych pasujących jednostek.")
            
    except requests.exceptions.HTTPError as err:
        print(f"⛔ BŁĄD HTTP: {err}")

# --- Uruchomienie ---
if __name__ == "__main__":
    moj_klucz_api = "f1419a42-2ab1-440c-caeb-08de-0e3351a1" # Użyj swojego klucza
    znajdz_id_jednostki("Płock", moj_klucz_api)