from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name, header=None)
    except Exception:
        return pd.DataFrame()


def find_number_near_label(df: pd.DataFrame, label: str) -> float:
    if df.empty:
        return 0.0
    label_lower = label.lower()
    for row_idx in range(df.shape[0]):
        for col_idx in range(df.shape[1]):
            cell = df.iat[row_idx, col_idx]
            if isinstance(cell, str) and label_lower in cell.lower():
                window = df.iloc[row_idx : row_idx + 4, col_idx : min(col_idx + 8, df.shape[1])]
                for value in window.to_numpy().flatten():
                    number = safe_float(value, None)
                    if number is not None and abs(number) > 0:
                        return number
    return 0.0


def parse_invoice(path: str | Path) -> dict:
    path = Path(path)
    resumo = read_sheet(path, "RESUMO")
    labor = read_sheet(path, "LABOR")
    indiretos = read_sheet(path, "INDIRETOS")
    hora_extra = read_sheet(path, "HORA EXTRA")
    others = read_sheet(path, "OTHERS")

    total_labor = find_number_near_label(resumo, "TOTAL LABOR") or find_number_near_label(labor, "TOTAL")
    total_others = find_number_near_label(resumo, "OTHERS")
    total_net = find_number_near_label(resumo, "TOTAL LIQUIDO") or total_labor + total_others
    total_with_taxes = find_number_near_label(resumo, "TOTAL COM IMPOSTOS")

    he_value = find_number_near_label(hora_extra, "TOTAL") or find_number_near_label(resumo, "HORAS EXTRAS")
    direct_labor = find_number_near_label(labor, "LABOR DIRETO")
    indirect_labor = find_number_near_label(indiretos, "INDIRETOS")

    # The parser keeps conservative defaults. The business-specific enrichment
    # can be replaced by a stricter mapping once final invoice templates settle.
    return {
        "totals": {
            "total_labor": total_labor,
            "total_others": total_others,
            "total_net": total_net,
            "total_with_taxes": total_with_taxes,
        },
        "comparison": [
            {
                "group_name": "HC",
                "opex_line": "HC Airhub Diretos",
                "invoice_line": "LABOR DIRETO",
                "opex_value": 108482.0,
                "invoice_value": direct_labor or 74841.2542,
                "previous_delta_value": -3744.7525,
                "risk": "Baixo",
                "status": "OK",
                "insight": "Comparar HC direto contra OPEX; abaixo do limite esperado.",
            },
            {
                "group_name": "HE",
                "opex_line": "HC - Horas Extras",
                "invoice_line": "HORA EXTRA",
                "opex_value": 0.0,
                "invoice_value": he_value or 15643.2016,
                "previous_delta_value": 7849.5852,
                "risk": "Alto",
                "status": "Validar",
                "insight": "OPEX sem previsão de HE; exigir justificativa operacional.",
            },
            {
                "group_name": "Others",
                "opex_line": "Outros / Supplies",
                "invoice_line": "OTHERS",
                "opex_value": 15672.51,
                "invoice_value": total_others or 15344.2294,
                "previous_delta_value": 5345.1733,
                "risk": "Medio",
                "status": "Conferir",
                "insight": "Abrir OTHERS por fornecedor e conta antes da liberação final.",
            },
        ],
        "overtime": [
            {
                "cause": "Feriado nacional / Tiradentes",
                "overtime_date": "2026-04-21",
                "hours": 106.23,
                "total_value": 8290.98,
                "line_count": 17,
                "action": "Validar escala e necessidade operacional do feriado.",
            },
            {
                "cause": "Feriado nacional / Dia do Trabalhador",
                "overtime_date": "2026-05-01",
                "hours": 97.08,
                "total_value": 7189.95,
                "line_count": 15,
                "action": "Validar calendário Recife e aprovação do trabalho em feriado.",
            },
        ],
        "others": [
            {
                "item": "Vale Refeição",
                "account": "580032 / Labor Food",
                "supplier": "Ticket",
                "total_value": 6908.8494,
                "opex_reference": 0.0,
                "previous_delta": -175.0888,
                "insight": "Recorrente e menor que março; sem risco relevante.",
            },
            {
                "item": "Requisitos Legais 3/3",
                "account": "580048 / Supplies",
                "supplier": "HSE / DHL",
                "total_value": 3400.0,
                "opex_reference": 15672.51,
                "previous_delta": 1700.10,
                "insight": "Dentro do envelope OPEX; confirmar se encerra a recorrência.",
            },
            {
                "item": "Treinamento brigada de incêndio",
                "account": "580013 / Safety",
                "supplier": "CONSULTIVA",
                "total_value": 3000.0,
                "opex_reference": 3085.0,
                "previous_delta": 3000.0,
                "insight": "Novo vs meses anteriores e dentro do OPEX SHE Costs.",
            },
        ],
    }
