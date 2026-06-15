from app.service import ingest_invoice


payload = {
    "invoice_id": "BRAPE1-2026-05",
    "airhub": "BRAPE1",
    "competence": "2026-05",
    "site_name": "Recife Meli Air",
    "supplier": "DHL",
    "thread_id": "19e4c8047e2afa00",
    "message_id": "19e6aafd11129b25",
    "subject": "FATURA 3PL_DHL_BRAPE1_Maio_2026_Recife Meli Air",
    "sender": "DHL",
    "attachment_name": "FATURA 3PL_DHL_BRAPE1_Maio_2026_Recife Meli Air.xlsx",
    "local_file_path": "../fatura_brape1_maio_2026.xlsx",
}


if __name__ == "__main__":
    result = ingest_invoice(payload)
    print(result["invoice"]["id"])
