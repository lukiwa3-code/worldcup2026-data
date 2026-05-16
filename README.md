# World Cup 2026 Data Parser

Repozytorium automatycznie pobiera dane terminarza FIFA World Cup 2026 z publicznego endpointu FIFA i tworzy uproszczone pliki JSON dla aplikacji Android.

## Co robi GitHub Actions?

Workflow `.github/workflows/update-fifa-data.yml` uruchamia parser co 5 minut.

Parser:
1. pobiera dane z FIFA,
2. czyści strukturę,
3. zapisuje pliki:
   - `data/matches_clean.json`
   - `data/metadata.json`
4. robi commit tylko wtedy, gdy dane faktycznie się zmieniły.

## Źródło danych

Aktualny endpoint:

```text
https://api.fifa.com/api/v3/calendar/matches?language=en&count=500&idSeason=285023
```

Jeśli FIFA zmieni endpoint, zaktualizuj stałą `FIFA_MATCHES_URL` w pliku:

```text
parser/parser.py
```

## Ręczne uruchomienie na komputerze

```bash
pip install -r requirements.txt
python parser/parser.py
```

## Uruchomienie w GitHub

Po wrzuceniu plików do repozytorium:

1. Wejdź w zakładkę **Actions**.
2. Kliknij workflow **Update FIFA World Cup 2026 Data**.
3. Kliknij **Run workflow**.
4. Po wykonaniu powinny pojawić się pliki:
   - `data/matches_clean.json`
   - `data/metadata.json`

## Linki RAW dla aplikacji Android

Po wrzuceniu do repozytorium publicznego pliki będą dostępne pod adresami:

```text
https://raw.githubusercontent.com/TWOJ_LOGIN/NAZWA_REPO/main/data/matches_clean.json
```

```text
https://raw.githubusercontent.com/TWOJ_LOGIN/NAZWA_REPO/main/data/metadata.json
```

Podmień `TWOJ_LOGIN` i `NAZWA_REPO` na swoje dane.

## Najważniejsze pola w matches_clean.json

Każdy mecz zawiera m.in.:

- `match_number`
- `id_match`
- `stage`
- `group`
- `date_utc`
- `date_poland`
- `home`
- `away`
- `home_score`
- `away_score`
- `stadium`
- `match_status_code`

## Uwaga

To jest nieoficjalny parser korzystający z publicznych danych FIFA. Jeśli FIFA zmieni format odpowiedzi lub adres endpointu, parser może wymagać poprawki.
