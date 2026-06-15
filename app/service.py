from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from urllib import request

from .db import connect, init_db, row, rows
from .parser import parse_invoice


ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "uploads"


def invoice_id(airhub: str, competence: str) -> str:
    return f"{airhub}-{competence}"


def save_attachment(payload: dict) -> Path | None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    filename = payload.get("attachment_name") or "fatura.xlsx"

    if payload.get("attachment_base64"):
        target = UPLOADS / filename
        target.write_bytes(base64.b64decode(payload["attachment_base64"]))
        return target

    if payload.get("local_file_path"):
        source = Path(payload["local_file_path"])
        if source.exists():
            target = UPLOADS / filename
            shutil.copyfile(source, target)
            return target

    return None


def ingest_invoice(payload: dict) -> dict:
    init_db()
    airhub = payload.get("airhub") or "BRAPE1"
    competence = payload.get("competence") or "2026-05"
    inv_id = payload.get("invoice_id") or invoice_id(airhub, competence)
    attachment_path = save_attachment(payload)

    parsed = parse_invoice(attachment_path) if attachment_path else parse_invoice(ROOT / ".." / "fatura_brape1_maio_2026.xlsx")
    totals = parsed["totals"]

    with connect() as conn:
        conn.execute(
            """
            insert into invoices (
              id, airhub, competence, site_name, supplier, thread_id, message_id,
              subject, sender, attachment_name, attachment_path, status,
              total_labor, total_others, total_net, total_with_taxes, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'aguardando_decisao', ?, ?, ?, ?, current_timestamp)
            on conflict(id) do update set
              thread_id=excluded.thread_id,
              message_id=excluded.message_id,
              subject=excluded.subject,
              sender=excluded.sender,
              attachment_name=excluded.attachment_name,
              attachment_path=excluded.attachment_path,
              status='aguardando_decisao',
              total_labor=excluded.total_labor,
              total_others=excluded.total_others,
              total_net=excluded.total_net,
              total_with_taxes=excluded.total_with_taxes,
              updated_at=current_timestamp
            """,
            (
                inv_id,
                airhub,
                competence,
                payload.get("site_name") or "Recife Meli Air",
                payload.get("supplier") or "DHL",
                payload.get("thread_id"),
                payload.get("message_id"),
                payload.get("subject"),
                payload.get("sender"),
                payload.get("attachment_name"),
                str(attachment_path) if attachment_path else None,
                totals["total_labor"],
                totals["total_others"],
                totals["total_net"],
                totals["total_with_taxes"],
            ),
        )
        conn.execute("delete from analysis_lines where invoice_id = ?", (inv_id,))
        conn.execute("delete from overtime_lines where invoice_id = ?", (inv_id,))
        conn.execute("delete from others_lines where invoice_id = ?", (inv_id,))

        for item in parsed["comparison"]:
            delta = item["invoice_value"] - item["opex_value"]
            conn.execute(
                """
                insert into analysis_lines (
                  invoice_id, group_name, opex_line, invoice_line, opex_value,
                  invoice_value, delta_value, previous_delta_value, risk, status, insight
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inv_id,
                    item["group_name"],
                    item["opex_line"],
                    item["invoice_line"],
                    item["opex_value"],
                    item["invoice_value"],
                    delta,
                    item["previous_delta_value"],
                    item["risk"],
                    item["status"],
                    item["insight"],
                ),
            )

        for item in parsed["overtime"]:
            conn.execute(
                """
                insert into overtime_lines (
                  invoice_id, cause, overtime_date, hours, total_value, line_count, action
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inv_id,
                    item["cause"],
                    item["overtime_date"],
                    item["hours"],
                    item["total_value"],
                    item["line_count"],
                    item["action"],
                ),
            )

        for item in parsed["others"]:
            conn.execute(
                """
                insert into others_lines (
                  invoice_id, item, account, supplier, total_value,
                  opex_reference, previous_delta, insight
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inv_id,
                    item["item"],
                    item["account"],
                    item["supplier"],
                    item["total_value"],
                    item["opex_reference"],
                    item["previous_delta"],
                    item["insight"],
                ),
            )

        conn.commit()

    return get_dashboard(inv_id)


def get_dashboard(inv_id: str | None = None) -> dict:
    init_db()
    invoice = None
    if inv_id:
        invoice = row("select * from invoices where id = ?", (inv_id,))
    if not invoice:
        invoice = row("select * from invoices order by updated_at desc limit 1")
    if not invoice:
        return {"invoice": None, "comparison": [], "overtime": [], "others": [], "decisions": []}

    inv_id = invoice["id"]
    return {
        "invoice": invoice,
        "comparison": rows("select * from analysis_lines where invoice_id = ? order by id", (inv_id,)),
        "overtime": rows("select * from overtime_lines where invoice_id = ? order by total_value desc", (inv_id,)),
        "others": rows("select * from others_lines where invoice_id = ? order by total_value desc", (inv_id,)),
        "decisions": rows("select * from decisions where invoice_id = ? order by created_at desc", (inv_id,)),
    }


def build_email_body(action: str, dashboard: dict) -> str:
    invoice = dashboard["invoice"] or {}
    airhub = invoice.get("airhub", "BRAPE1")
    competence = invoice.get("competence", "2026-05")
    opening = f"Boa tarde!\n\nAnalisei a fatura {airhub} - {competence} considerando OPEX, histórico e detalhes do anexo."

    if action == "approve":
        return f"{opening}\n\nOs itens recorrentes e o HC comparável estão de acordo. Segue de acordo, condicionado ao registro da validação operacional das horas extras de feriado.\n\nAtenciosamente,\nAdames Oliveira"
    if action == "request_docs":
        return f"{opening}\n\nFavor complementar as evidências dos itens novos em OTHERS, especialmente Requisitos Legais 3/3, treinamento de brigada e transporte/Uber por chuvas.\n\nAtenciosamente,\nAdames Oliveira"
    if action == "reject":
        return f"{opening}\n\nNeste momento não consigo liberar a fatura por pendência de informação: horas extras de feriado sem previsão no OPEX e sem validação formal anexada.\n\nAtenciosamente,\nAdames Oliveira"
    return f"{opening}\n\nAntes da liberação, preciso da justificativa/aprovação operacional das horas extras: Tiradentes e Dia do Trabalhador. O OPEX de HE para maio está zerado, então preciso dessa evidência para concluir.\n\nAtenciosamente,\nAdames Oliveira"


def register_decision(payload: dict) -> dict:
    init_db()
    inv_id = payload.get("invoice_id")
    dashboard = get_dashboard(inv_id)
    invoice = dashboard["invoice"]
    if not invoice:
        raise ValueError("Nenhuma fatura encontrada para registrar decisão.")

    action = payload.get("action") or "request_he"
    email_body = payload.get("email_body") or build_email_body(action, dashboard)
    n8n_payload = {
        "invoice_id": invoice["id"],
        "thread_id": invoice["thread_id"],
        "message_id": invoice["message_id"],
        "action": action,
        "email_body": email_body,
    }

    with connect() as conn:
        cursor = conn.execute(
            """
            insert into decisions (invoice_id, action, status, email_body, n8n_payload)
            values (?, ?, 'aguardando_envio_n8n', ?, ?)
            """,
            (invoice["id"], action, email_body, json.dumps(n8n_payload, ensure_ascii=False)),
        )
        conn.execute("update invoices set status = ?, updated_at = current_timestamp where id = ?", (action, invoice["id"]))
        conn.commit()
        decision_id = cursor.lastrowid

    webhook_url = payload.get("n8n_response_webhook_url")
    if webhook_url:
        req = request.Request(
            webhook_url,
            data=json.dumps(n8n_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=20) as response:
            n8n_payload["n8n_status"] = response.status

    return {"decision_id": decision_id, **n8n_payload}
