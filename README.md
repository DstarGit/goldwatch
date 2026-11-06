# Numi GoldWatch (GoldInvest24 Monitor)

Aplikacja do automatycznego monitorowania, archiwizowania i wizualizacji cen 6 kluczowych serii złotych monet bulionowych (Krugerrand, Britannia, Kanadyjski Liść Klonowy, Wiedeński Filharmonik, Amerykański Orzeł, Złoty Kangur) w wagach 1 oz i 1/2 oz.

Projekt jest zoptymalizowany pod równoległą pracę w dwóch środowiskach:
1. **Mikrus VPS** (używając obrazu `:mikrus` i portu `40003`)
2. **Google Cloud Platform Cloud Run** (używając obrazu `:gcp` / `:latest` i dynamicznego portu `$PORT`)

---

## 1. Struktura repozytorium

```
.
├── .github/workflows/docker-publish.yml  # Automatyczne budowanie obu obrazów do ghcr.io
├── goldinvest/
│   ├── Dockerfile.mikrus                 # Dedykowany obraz dla Mikrusa (port 40003)
│   ├── Dockerfile.gcp                    # Dedykowany obraz dla GCP Cloud Run ($PORT 8080)
│   ├── docker-compose.yml                # Uruchomienie na Mikrusie
│   ├── docker-compose.gcp.yml            # Lokalne testy środowiska GCP
│   ├── requirements.txt                  # Pakiety Pythona (Flask, Gunicorn, tzdata)
│   ├── app/                              # Kod źródłowy aplikacji (app.py, db.py, scraper.py)
│   └── tests/                            # Testy jednostkowe parsera i logiki bazy
├── numi_mcp/
│   └── server.py                         # Lokalny serwer MCP dla agentów AI
├── .gitignore
└── README.md
```

---

## 2. Dwa obrazy w GitHub Container Registry (`ghcr.io`)

Po wypchnięciu kodu do GitHuba (`git push`), workflow GitHub Actions automatycznie publikuje:

- **`ghcr.io/<login>/numi:mikrus`**  
  Obraz dedykowany dla serwera Mikrus.
- **`ghcr.io/<login>/numi:gcp`** (oraz `:latest`, `:cloudrun`)  
  Obraz dedykowany dla GCP Cloud Run (obsługujący dynamiczny `$PORT`).

---

## 3. Uruchomienie na Mikrusie

Na serwerze Mikrus projekt uruchamia się za pomocą Docker Compose:

```bash
cd /root/MCPAPPS/goldinvest
docker compose up -d --build
```

Aplikacja dostępna jest pod adresem:
**`https://izabela211-40003.mikrus.cloud/`**

---

## 4. Wdrożenie na Google Cloud Run (GCP)

Mając obraz opublikowany w rejestrze GitHub Container Registry:

```bash
gcloud run deploy numi-goldwatch \
  --image ghcr.io/<twoj-login-github>/numi:gcp \
  --platform managed \
  --region europe-central2 \
  --allow-unauthenticated \
  --no-cpu-throttling \
  --min-instances 1 \
  --port 8080
```

> **Wskazówka dot. trwałości danych na Cloud Run:**  
> W GCP Cloud Run (2nd generation) można podpiąć zasobnik Google Cloud Storage (GCS) jako wolumen montowany w `/data`, co gwarantuje zachowanie bazy SQLite pomiędzy restartami usługi.
