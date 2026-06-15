# Controle de faturas - Python + n8n

MVP sem Apps Script para:

- buscar faturas no Gmail via n8n
- enviar anexos para um app Python
- salvar dados em SQLite
- mostrar dashboard compartilhável
- registrar decisão
- devolver payload para o n8n responder a thread original

## Stack disponível

- Python 3
- SQLite via `sqlite3`
- pandas
- openpyxl
- HTML/JS servido pelo Python

Sem FastAPI neste ambiente. O servidor usa `http.server` da biblioteca padrão.

## Rodar localmente

```bash
cd faturas-python-n8n
python3 seed.py
python3 -m app.server
```

Abra:

```text
http://127.0.0.1:8790
```

## Endpoints

### Health

```text
GET /api/health
```

### Dashboard

```text
GET /api/dashboard
GET /api/dashboard?invoice_id=BRAPE1-2026-05
```

### Intake de fatura

```text
POST /api/intake
```

Payload esperado:

```json
{
  "invoice_id": "BRAPE1-2026-05",
  "airhub": "BRAPE1",
  "competence": "2026-05",
  "site_name": "Recife Meli Air",
  "supplier": "DHL",
  "thread_id": "THREAD_ID",
  "message_id": "MESSAGE_ID",
  "subject": "FATURA 3PL_DHL...",
  "sender": "email@dhl.com",
  "attachment_name": "fatura.xlsx",
  "attachment_base64": "BASE64_DO_ARQUIVO"
}
```

Alternativa local:

```json
{
  "local_file_path": "../fatura_brape1_maio_2026.xlsx"
}
```

### Registrar decisão

```text
POST /api/decision
```

Payload:

```json
{
  "invoice_id": "BRAPE1-2026-05",
  "action": "request_he",
  "n8n_response_webhook_url": "https://SEU_N8N/webhook/controle-faturas-resposta"
}
```

Ações:

- `approve`
- `request_he`
- `request_docs`
- `reject`

Se `n8n_response_webhook_url` for enviado, o app chama o n8n com:

```json
{
  "invoice_id": "BRAPE1-2026-05",
  "thread_id": "THREAD_ID",
  "message_id": "MESSAGE_ID",
  "action": "request_he",
  "email_body": "..."
}
```

## Workflows n8n

Importar:

- `workflows/01-gmail-intake.json`
- `workflows/02-gmail-reply-webhook.json`

Depois ajustar:

- credencial Gmail nos nodes
- URL `https://SEU_APP/api/intake`
- URL pública do webhook de resposta

## Produção

Para compartilhar, hospede este app Python em uma VM, Render, Railway, Fly.io ou Cloud Run.

SQLite funciona para MVP. Para uso simultâneo e histórico maior, migrar para Postgres/Supabase mantendo os mesmos conceitos de tabela.
