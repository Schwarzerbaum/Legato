"""Payroll analysis agent — parses DATEV Lohn & Gehalt exports and runs
AI-powered compliance analysis on German payroll data.

Combines pure-math statistical checks (overtime patterns, sick-leave
clustering, minimum wage, Minijob thresholds) with LLM-powered risk
assessment via the Ollama swarm.  All inference is local.
"""
import csv
import io
import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, stdev

from backend.llm.router import smart_chat

logger = logging.getLogger(__name__)


# ===================================================================
# DATEV Lohn & Gehalt CSV parser
# ===================================================================

# Expected DATEV payroll export columns (German headers)
EXPECTED_COLUMNS = [
    "Personalnummer", "Name", "Vorname", "Eintritt",
    "Bruttolohn", "Nettolohn", "Steuerklasse",
    "SV_Beitrag_AG", "SV_Beitrag_AN",
    "Arbeitsstunden", "Ueberstunden", "Krankheitstage", "Urlaubstage",
    "Minijob", "Firmenwagen", "Geldwerter_Vorteil",
]

# Normalised field names for internal processing
FIELD_MAP = {
    "Personalnummer": "personnel_id",
    "Name": "last_name",
    "Vorname": "first_name",
    "Eintritt": "hire_date",
    "Bruttolohn": "gross_salary",
    "Nettolohn": "net_salary",
    "Steuerklasse": "tax_class",
    "SV_Beitrag_AG": "sv_employer",
    "SV_Beitrag_AN": "sv_employee",
    "Arbeitsstunden": "work_hours",
    "Ueberstunden": "overtime_hours",
    "Krankheitstage": "sick_days",
    "Urlaubstage": "vacation_days",
    "Minijob": "is_minijob",
    "Firmenwagen": "has_company_car",
    "Geldwerter_Vorteil": "non_cash_benefit",
}


def _parse_decimal(value: str) -> float:
    """Parse a German-format decimal (comma as separator)."""
    if not value or value.strip() == "":
        return 0.0
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_bool_de(value: str) -> bool:
    """Parse a German J/N boolean field."""
    return value.strip().upper() in ("J", "JA", "Y", "YES", "1", "TRUE")


def _parse_date_de(value: str) -> str | None:
    """Parse a German date (DD.MM.YYYY) to ISO format."""
    if not value or value.strip() == "":
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return value.strip()


def parse_payroll_csv(file_content: bytes, encoding: str = "cp1252") -> list[dict]:
    """Parse DATEV Lohn & Gehalt CSV export.

    Expected columns (German): Personalnummer, Name, Vorname, Eintritt,
    Bruttolohn, Nettolohn, Steuerklasse, SV_Beitrag_AG, SV_Beitrag_AN,
    Arbeitsstunden, Ueberstunden, Krankheitstage, Urlaubstage,
    Minijob (J/N), Firmenwagen (J/N), Geldwerter_Vorteil

    Returns list of employee dicts with normalised field names.
    """
    try:
        text = file_content.decode(encoding)
    except UnicodeDecodeError:
        text = file_content.decode("utf-8", errors="replace")

    # Detect delimiter — DATEV uses semicolons
    delimiter = ";" if ";" in text.split("\n")[0] else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        logger.warning("No headers found in payroll CSV")
        return []

    # Strip BOM and whitespace from headers
    cleaned_fields = [f.strip().lstrip("﻿") for f in reader.fieldnames]

    employees: list[dict] = []
    for row_num, row in enumerate(reader, start=2):
        # Re-key with cleaned headers
        cleaned_row = {}
        for orig, cleaned in zip(reader.fieldnames, cleaned_fields):
            cleaned_row[cleaned] = row.get(orig, "")

        try:
            emp = {
                "personnel_id": cleaned_row.get("Personalnummer", "").strip(),
                "last_name": cleaned_row.get("Name", "").strip(),
                "first_name": cleaned_row.get("Vorname", "").strip(),
                "hire_date": _parse_date_de(cleaned_row.get("Eintritt", "")),
                "gross_salary": _parse_decimal(cleaned_row.get("Bruttolohn", "0")),
                "net_salary": _parse_decimal(cleaned_row.get("Nettolohn", "0")),
                "tax_class": cleaned_row.get("Steuerklasse", "").strip(),
                "sv_employer": _parse_decimal(cleaned_row.get("SV_Beitrag_AG", "0")),
                "sv_employee": _parse_decimal(cleaned_row.get("SV_Beitrag_AN", "0")),
                "work_hours": _parse_decimal(cleaned_row.get("Arbeitsstunden", "0")),
                "overtime_hours": _parse_decimal(cleaned_row.get("Ueberstunden", "0")),
                "sick_days": _parse_decimal(cleaned_row.get("Krankheitstage", "0")),
                "vacation_days": _parse_decimal(cleaned_row.get("Urlaubstage", "0")),
                "is_minijob": _parse_bool_de(cleaned_row.get("Minijob", "N")),
                "has_company_car": _parse_bool_de(cleaned_row.get("Firmenwagen", "N")),
                "non_cash_benefit": _parse_decimal(
                    cleaned_row.get("Geldwerter_Vorteil", "0")
                ),
                "_row": row_num,
            }
            # Skip rows without a personnel ID
            if emp["personnel_id"]:
                employees.append(emp)
        except Exception as e:
            logger.warning("Skipping row %d: %s", row_num, e)
            continue

    logger.info("Parsed %d employees from payroll CSV", len(employees))
    return employees


# ===================================================================
# Statistical analysis functions (pure math, no LLM)
# ===================================================================

def analyze_overtime_patterns(employees: list[dict]) -> dict:
    """Flag employees consistently near the overtime threshold (48h/week).

    Per §3 ArbZG, weekly working hours must not exceed 48h on average.
    Flags employees with avg total hours > 45 as at-risk.
    """
    flags = []
    for emp in employees:
        total_hours = emp["work_hours"] + emp["overtime_hours"]
        # Approximate weekly hours (monthly hours / 4.33 weeks)
        weekly_avg = total_hours / 4.33 if total_hours > 0 else 0
        if weekly_avg > 45:
            flags.append({
                "employee": f"{emp['first_name']} {emp['last_name']}",
                "personnel_id": emp["personnel_id"],
                "monthly_hours": total_hours,
                "weekly_avg": round(weekly_avg, 1),
                "overtime_hours": emp["overtime_hours"],
                "severity": "high" if weekly_avg > 48 else "medium",
                "legal_ref": "§3 ArbZG",
            })

    return {
        "check": "overtime_patterns",
        "total_flagged": len(flags),
        "flags": flags,
        "summary": (
            f"{len(flags)} employee(s) near or exceeding 48h/week ArbZG limit"
        ),
    }


def analyze_sick_leave_patterns(employees: list[dict]) -> dict:
    """Detect Monday/Friday clustering in sick days.

    Flags if >60% of sick days fall on Mon/Fri (statistical anomaly
    suggesting potential abuse per §5 EFZG).

    Note: Without per-day breakdown, we flag employees with high sick-day
    counts relative to peers as requiring further investigation.
    """
    sick_days_list = [emp["sick_days"] for emp in employees if emp["sick_days"] > 0]
    if not sick_days_list:
        return {
            "check": "sick_leave_patterns",
            "total_flagged": 0,
            "flags": [],
            "summary": "No sick days recorded",
        }

    avg_sick = mean(sick_days_list) if sick_days_list else 0
    threshold = avg_sick * 2 if avg_sick > 0 else 10

    flags = []
    for emp in employees:
        if emp["sick_days"] > threshold:
            flags.append({
                "employee": f"{emp['first_name']} {emp['last_name']}",
                "personnel_id": emp["personnel_id"],
                "sick_days": emp["sick_days"],
                "team_average": round(avg_sick, 1),
                "ratio_to_avg": round(emp["sick_days"] / avg_sick, 1) if avg_sick else 0,
                "severity": "medium",
                "legal_ref": "§5 EFZG",
                "note": "Recommend requesting Arbeitsunfaehigkeitsbescheinigung review",
            })

    return {
        "check": "sick_leave_patterns",
        "total_flagged": len(flags),
        "avg_sick_days": round(avg_sick, 1),
        "flags": flags,
        "summary": f"{len(flags)} employee(s) with sick days >2x team average",
    }


def analyze_salary_distribution(employees: list[dict]) -> dict:
    """Find salary outliers — underpaid (flight risk) or overpaid.

    Uses standard deviation analysis, flags employees >1.5 std from mean.
    """
    # Group by employment type
    fulltime = [e for e in employees if not e["is_minijob"]]
    if len(fulltime) < 3:
        return {
            "check": "salary_distribution",
            "total_flagged": 0,
            "flags": [],
            "summary": "Too few full-time employees for distribution analysis",
        }

    salaries = [e["gross_salary"] for e in fulltime]
    avg_salary = mean(salaries)
    salary_std = stdev(salaries) if len(salaries) > 1 else 0

    flags = []
    for emp in fulltime:
        if salary_std == 0:
            continue
        z_score = (emp["gross_salary"] - avg_salary) / salary_std
        if abs(z_score) > 1.5:
            direction = "underpaid" if z_score < 0 else "overpaid"
            flags.append({
                "employee": f"{emp['first_name']} {emp['last_name']}",
                "personnel_id": emp["personnel_id"],
                "gross_salary": emp["gross_salary"],
                "team_average": round(avg_salary, 2),
                "z_score": round(z_score, 2),
                "direction": direction,
                "severity": "medium" if abs(z_score) < 2 else "high",
                "risk": "flight_risk" if direction == "underpaid" else "cost_optimisation",
            })

    return {
        "check": "salary_distribution",
        "total_flagged": len(flags),
        "average_salary": round(avg_salary, 2),
        "std_deviation": round(salary_std, 2),
        "flags": flags,
        "summary": f"{len(flags)} salary outlier(s) detected (>1.5 std from mean)",
    }


def check_minijob_compliance(employees: list[dict]) -> dict:
    """Check Minijob 520 EUR threshold and Scheinselbstaendigkeit risk.

    Per §8 SGB IV, Minijob earnings must not exceed 520 EUR/month.
    Flags minijobs at exactly 520 EUR (threshold gaming) or above.
    """
    minijobbers = [e for e in employees if e["is_minijob"]]
    flags = []

    for emp in minijobbers:
        issues = []
        if emp["gross_salary"] > 520:
            issues.append("Exceeds 520 EUR Minijob threshold")
            severity = "high"
        elif emp["gross_salary"] == 520:
            issues.append("Exactly at 520 EUR threshold — Scheinselbstaendigkeit risk")
            severity = "medium"
        else:
            continue

        # Check for full-time-like hours
        if emp["work_hours"] > 60:
            issues.append(
                f"Working {emp['work_hours']}h/month — unusual for Minijob"
            )
            severity = "high"

        flags.append({
            "employee": f"{emp['first_name']} {emp['last_name']}",
            "personnel_id": emp["personnel_id"],
            "gross_salary": emp["gross_salary"],
            "work_hours": emp["work_hours"],
            "issues": issues,
            "severity": severity,
            "legal_ref": "§8 SGB IV, §7 SGB IV",
        })

    return {
        "check": "minijob_compliance",
        "total_minijobs": len(minijobbers),
        "total_flagged": len(flags),
        "flags": flags,
        "summary": f"{len(flags)}/{len(minijobbers)} Minijob(s) flagged for compliance issues",
    }


def check_mindestlohn(employees: list[dict], min_wage: float = 12.82) -> dict:
    """Check minimum wage compliance (2026 Mindestlohn rate).

    Per MiLoG, calculates effective hourly rate = Bruttolohn / Arbeitsstunden
    and flags if below the legal minimum.
    """
    flags = []
    for emp in employees:
        if emp["work_hours"] <= 0:
            continue
        hourly_rate = emp["gross_salary"] / emp["work_hours"]
        if hourly_rate < min_wage:
            flags.append({
                "employee": f"{emp['first_name']} {emp['last_name']}",
                "personnel_id": emp["personnel_id"],
                "gross_salary": emp["gross_salary"],
                "work_hours": emp["work_hours"],
                "hourly_rate": round(hourly_rate, 2),
                "min_wage": min_wage,
                "shortfall_per_hour": round(min_wage - hourly_rate, 2),
                "severity": "high",
                "legal_ref": "MiLoG §1",
            })

    return {
        "check": "mindestlohn",
        "min_wage_2026": min_wage,
        "total_flagged": len(flags),
        "flags": flags,
        "summary": f"{len(flags)} employee(s) below Mindestlohn ({min_wage} EUR/h)",
    }


def analyze_lohnnebenkosten(employees: list[dict]) -> dict:
    """Calculate and forecast employer-side costs (Lohnnebenkosten).

    Sums SV_Beitrag_AG across all employees and projects next quarter costs.
    """
    total_gross = sum(e["gross_salary"] for e in employees)
    total_sv_ag = sum(e["sv_employer"] for e in employees)
    total_sv_an = sum(e["sv_employee"] for e in employees)
    total_benefits = sum(e["non_cash_benefit"] for e in employees)

    # Employer cost ratio
    cost_ratio = (total_sv_ag / total_gross * 100) if total_gross > 0 else 0

    # Quarterly projection (3 months)
    quarterly_gross = total_gross * 3
    quarterly_sv_ag = total_sv_ag * 3
    quarterly_total = quarterly_gross + quarterly_sv_ag

    return {
        "check": "lohnnebenkosten",
        "monthly": {
            "total_gross": round(total_gross, 2),
            "total_sv_employer": round(total_sv_ag, 2),
            "total_sv_employee": round(total_sv_an, 2),
            "total_non_cash_benefits": round(total_benefits, 2),
            "employer_cost_ratio_pct": round(cost_ratio, 1),
            "total_employer_cost": round(total_gross + total_sv_ag, 2),
        },
        "forecast_next_quarter": {
            "total_gross": round(quarterly_gross, 2),
            "total_sv_employer": round(quarterly_sv_ag, 2),
            "total_cost": round(quarterly_total, 2),
        },
        "headcount": len(employees),
        "summary": (
            f"Monthly employer cost: {total_gross + total_sv_ag:,.2f} EUR "
            f"({cost_ratio:.1f}% Lohnnebenkosten ratio)"
        ),
    }


def check_geldwerter_vorteil(employees: list[dict]) -> dict:
    """Check if non-cash benefits (company car, meals) are properly declared.

    Per §8 EStG, employees with Firmenwagen=J must have a corresponding
    Geldwerter_Vorteil entry.  Missing declarations create tax liability.
    """
    flags = []
    for emp in employees:
        if emp["has_company_car"] and emp["non_cash_benefit"] <= 0:
            flags.append({
                "employee": f"{emp['first_name']} {emp['last_name']}",
                "personnel_id": emp["personnel_id"],
                "has_company_car": True,
                "declared_benefit": emp["non_cash_benefit"],
                "issue": "Firmenwagen without declared Geldwerter Vorteil",
                "severity": "high",
                "legal_ref": "§8 EStG",
                "note": "Missing 1%-Regelung or Fahrtenbuch declaration",
            })

    return {
        "check": "geldwerter_vorteil",
        "total_with_car": sum(1 for e in employees if e["has_company_car"]),
        "total_flagged": len(flags),
        "flags": flags,
        "summary": (
            f"{len(flags)} employee(s) with Firmenwagen but no "
            f"declared Geldwerter Vorteil"
        ),
    }


# ===================================================================
# LLM-powered analysis
# ===================================================================

PAYROLL_ANALYST_SYSTEM = (
    "You are a German payroll compliance expert (Lohnbuchhalter). "
    "Analyze payroll data for:\n"
    "1. OVERTIME: Employees near Arbeitszeitgesetz limits "
    "(§3 ArbZG: max 48h/week averaged)\n"
    "2. SICK LEAVE: Monday/Friday clustering suggesting abuse (§5 EFZG)\n"
    "3. MINIJOB: Scheinselbstaendigkeit risk (§7 SGB IV)\n"
    "4. MINDESTLOHN: Below minimum wage (MiLoG)\n"
    "5. SOZIALVERSICHERUNG: Correct SV categories and thresholds\n"
    "6. GELDWERTER VORTEIL: Undeclared benefits (§8 EStG)\n"
    "7. KURZARBEIT: Optimisation opportunities (§95-109 SGB III)\n\n"
    "You receive pre-computed statistical analysis results. Evaluate them, "
    "provide expert commentary, and identify any issues the statistical "
    "checks may have missed.\n\n"
    "Output valid JSON with this structure:\n"
    "{\n"
    '  "anomalies": [{"type": str, "employee": str, "description": str, '
    '"severity": "high"|"medium"|"low", "legal_ref": str}],\n'
    '  "risk_level": "high"|"medium"|"low",\n'
    '  "total_lohnnebenkosten": float,\n'
    '  "forecast_next_quarter": float,\n'
    '  "recommendations": [str]\n'
    "}"
)


async def run_payroll_analysis(employees: list[dict]) -> dict:
    """Run full payroll analysis — statistical checks + LLM expert review.

    1. Runs all statistical analysis functions
    2. Aggregates findings into a summary
    3. Sends to LLM agent for expert commentary and missed issues
    4. Returns combined results
    """
    # ── Step 1: Run all statistical checks ──────────────────────
    checks = {
        "overtime": analyze_overtime_patterns(employees),
        "sick_leave": analyze_sick_leave_patterns(employees),
        "salary_distribution": analyze_salary_distribution(employees),
        "minijob": check_minijob_compliance(employees),
        "mindestlohn": check_mindestlohn(employees),
        "lohnnebenkosten": analyze_lohnnebenkosten(employees),
        "geldwerter_vorteil": check_geldwerter_vorteil(employees),
    }

    # ── Step 2: Build summary for LLM ───────────────────────────
    total_flags = sum(c.get("total_flagged", 0) for c in checks.values())
    high_severity = sum(
        1
        for c in checks.values()
        for f in c.get("flags", [])
        if f.get("severity") == "high"
    )

    summary_lines = [
        f"Payroll analysis for {len(employees)} employees:",
        f"Total flags: {total_flags} ({high_severity} high severity)",
        "",
    ]
    for name, result in checks.items():
        summary_lines.append(f"--- {name.upper()} ---")
        summary_lines.append(result.get("summary", "No summary"))
        for flag in result.get("flags", []):
            summary_lines.append(f"  - {flag.get('employee', 'N/A')}: "
                                 f"{flag.get('issue', flag.get('issues', ''))}")
        summary_lines.append("")

    # Add cost data
    kosten = checks["lohnnebenkosten"]
    summary_lines.append(f"Monthly employer cost: "
                         f"{kosten['monthly']['total_employer_cost']:,.2f} EUR")
    summary_lines.append(f"Quarterly forecast: "
                         f"{kosten['forecast_next_quarter']['total_cost']:,.2f} EUR")

    prompt = "\n".join(summary_lines)

    # ── Step 3: Send to LLM for expert analysis ─────────────────
    try:
        llm_response, model_used = await smart_chat(
            prompt=prompt,
            system=PAYROLL_ANALYST_SYSTEM,
            temperature=0.3,
            max_tokens=4096,
            json_mode=True,
        )

        # Parse LLM JSON response
        try:
            llm_result = json.loads(llm_response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r"```json?\s*(.*?)\s*```", llm_response, re.DOTALL)
            if json_match:
                llm_result = json.loads(json_match.group(1))
            else:
                llm_result = {
                    "raw_response": llm_response,
                    "parse_error": "Could not parse LLM response as JSON",
                }

    except Exception as e:
        logger.error("LLM payroll analysis failed: %s", e)
        llm_result = {
            "error": str(e),
            "anomalies": [],
            "risk_level": "unknown",
            "recommendations": ["LLM analysis unavailable — review statistical results manually"],
        }
        model_used = "none"

    # ── Step 4: Combine results ─────────────────────────────────
    return {
        "employee_count": len(employees),
        "statistical_checks": checks,
        "llm_analysis": llm_result,
        "model_used": model_used,
        "total_flags": total_flags,
        "high_severity_flags": high_severity,
        "risk_level": llm_result.get("risk_level", "medium" if high_severity > 0 else "low"),
        "total_lohnnebenkosten": kosten["monthly"]["total_employer_cost"],
        "forecast_next_quarter": kosten["forecast_next_quarter"]["total_cost"],
    }
