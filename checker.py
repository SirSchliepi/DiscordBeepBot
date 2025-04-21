import requests
import time

url = 'https://beepbot.org/checker.php?files=blabla3'
max_timeout = 300  

while True:
    try:
        print("Versuche, das Interface aufzurufen...")
        response = requests.get(url, timeout=max_timeout)
        if response.text != "ready":
            continue
        else:
            print("Datei existiert!")
            break
    except requests.exceptions.Timeout:
        print("Timeout nach 2 Minuten erreicht. Versuche erneut, die Verbindung aufzubauen...")
    except requests.exceptions.RequestException as e:
        print(f"Es ist ein Fehler aufgetreten: {e}. Versuche in 5 Sekunden erneut...")
        time.sleep(5)
