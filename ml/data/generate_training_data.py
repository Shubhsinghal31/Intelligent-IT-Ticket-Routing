"""
Synthetic training data generator for helpdesk-ai ML models.

Priority signal is embedded into ticket text so models can learn
real correlations between language and urgency level.
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

DEPARTMENTS = ["IT Support", "HR", "Finance", "Facilities", "Security"]

# =====================================================
# Priority-specific language modifiers
# These embed real signal into the text
# =====================================================

CRITICAL_PREFIXES = [
    "URGENT: ",
    "CRITICAL: ",
    "EMERGENCY: ",
    "P1: ",
    "OUTAGE: ",
]

CRITICAL_SUFFIXES = [
    " All users are affected and work has completely stopped.",
    " Production system is down. Immediate escalation needed.",
    " Complete outage affecting the entire organization.",
    " Business operations have halted. SLA breach imminent.",
    " All teams impacted. CEO has been notified.",
]

HIGH_SUFFIXES = [
    " Multiple colleagues are affected and unable to work.",
    " This is blocking critical project delivery.",
    " Several users reporting the same issue urgently.",
    " Escalating as this impacts team productivity significantly.",
    " Need resolution within today to meet client deadline.",
]

MEDIUM_SUFFIXES = [
    " Issue is intermittent but happening frequently.",
    " A workaround exists but it is inefficient.",
    " Affecting some users, not all.",
    " Please resolve when possible, medium priority.",
    " Happening occasionally, need a permanent fix.",
]

LOW_SUFFIXES = [
    " No urgency, please handle when time permits.",
    " Minor inconvenience, low priority.",
    " This is a general request, not blocking work.",
    " Can wait until next maintenance window.",
    " Just a small enhancement request.",
]

PRIORITY_SUFFIXES = {
    "critical": CRITICAL_SUFFIXES,
    "high": HIGH_SUFFIXES,
    "medium": MEDIUM_SUFFIXES,
    "low": LOW_SUFFIXES,
}

# =====================================================
# Base ticket templates per department
# =====================================================

TICKET_TEMPLATES = {
    "IT Support": [
        ("VPN not connecting", "Unable to connect to company VPN. Error: authentication failed."),
        ("Laptop running slow", "My laptop has become very slow and takes long to boot."),
        ("Cannot access shared drive", "Getting access denied on the shared network drive."),
        ("Email not syncing", "Outlook is not syncing emails since this morning."),
        ("Software installation request", "Need Adobe Acrobat installed for document signing."),
        ("Monitor flickering", "The external monitor keeps flickering and going black."),
        ("Printer not working", "Office printer showing offline even though powered on."),
        ("Password reset needed", "Locked out of account after too many failed attempts."),
        ("Internet connection dropping", "Wi-Fi keeps disconnecting every few minutes at my desk."),
        ("Two-factor auth not working", "Authenticator codes are not being accepted at login."),
        ("Server unreachable", "Cannot reach the internal application server from any device."),
        ("Database connection lost", "Application throwing database connection timeout errors."),
    ],
    "HR": [
        ("Leave balance incorrect", "My leave balance shows wrong number of days remaining."),
        ("Payslip not received", "Did not receive payslip for last month via email."),
        ("Onboarding documents missing", "New joiner documents not uploaded to the HR portal."),
        ("Performance review access", "Cannot access my performance review form on the portal."),
        ("Training enrollment issue", "Unable to enroll in the mandatory compliance training."),
        ("Work from home policy query", "Need clarification on the updated WFH policy."),
        ("Contract renewal needed", "My contract expires soon and renewal paperwork is pending."),
        ("Benefits portal down", "Cannot log in to the benefits enrollment portal."),
        (
            "Payroll system error",
            "Payroll system showing incorrect salary deduction for all staff.",
        ),
    ],
    "Finance": [
        ("Expense reimbursement delayed", "Submitted expenses weeks ago but not reimbursed."),
        ("Invoice approval stuck", "Vendor invoice has been pending approval for weeks."),
        ("Budget report access", "Need read access to the quarterly budget report."),
        ("Purchase order not raised", "PO for office equipment has not been raised yet."),
        ("Tax document missing", "Form 16 for last financial year not uploaded to portal."),
        ("Payment gateway error", "Getting errors when processing customer payments."),
        ("Financial system down", "Core financial system inaccessible, blocking all transactions."),
    ],
    "Facilities": [
        ("AC not working", "Air conditioning in the office is not functioning."),
        ("Water leak reported", "There is a water leak near the pantry area."),
        ("Desk chair broken", "My office chair is broken and causing discomfort."),
        ("Meeting room booking issue", "Meeting room appears booked but is empty."),
        ("Parking space request", "Need a parking spot for client visits."),
        ("Office supplies needed", "Running low on printer paper and stationery."),
        ("Elevator malfunction", "Elevator making grinding noise and stopping abruptly."),
        (
            "Fire alarm triggered",
            "Fire alarm went off unexpectedly. Building evacuation in progress.",
        ),
    ],
    "Security": [
        ("Suspicious email received", "Received a phishing email asking for login credentials."),
        ("Unauthorized access attempt", "Security log shows login attempts from unknown IP."),
        ("Badge access not working", "Access badge is not opening the server room door."),
        ("Data breach concern", "Found unencrypted spreadsheet with customer PII on shared drive."),
        ("CCTV camera offline", "CCTV camera at main entrance has been offline."),
        (
            "Ransomware detected",
            "Ransomware alert triggered on multiple workstations across the floor.",
        ),
        ("Credentials compromised", "Employee credentials found in a public data breach database."),
    ],
}

PRIORITIES = ["low", "medium", "high", "critical"]

# Realistic priority distribution across all tickets
PRIORITY_WEIGHTS = [0.25, 0.40, 0.25, 0.10]

RESOLUTION_HOURS = {
    "low": (24, 120),
    "medium": (8, 48),
    "high": (2, 24),
    "critical": (0.5, 8),
}

SLA_BREACH_PROB = {
    "low": 0.35,
    "medium": 0.20,
    "high": 0.15,
    "critical": 0.08,
}


def generate_dataset(n_samples: int = 2000) -> pd.DataFrame:
    records = []

    for _ in range(n_samples):
        dept = random.choice(DEPARTMENTS)
        title, base_desc = random.choice(TICKET_TEMPLATES[dept])

        # Sample priority first
        priority = np.random.choice(PRIORITIES, p=PRIORITY_WEIGHTS)

        # Build description with priority-specific language signal
        suffix = random.choice(PRIORITY_SUFFIXES[priority])
        description = base_desc + suffix

        # Critical tickets get an urgent prefix on the title
        if priority == "critical":
            title = random.choice(CRITICAL_PREFIXES) + title

        low_h, high_h = RESOLUTION_HOURS[priority]
        resolution_hours = round(random.uniform(low_h, high_h), 2)
        sla_breached = int(random.random() < SLA_BREACH_PROB[priority])

        records.append(
            {
                "title": title,
                "description": description,
                "department": dept,
                "priority": priority,
                "resolution_hours": resolution_hours,
                "sla_breached": sla_breached,
            }
        )

    return pd.DataFrame(records)


if __name__ == "__main__":
    output_path = Path(__file__).parent / "training_data.csv"

    print("Generating 2000 synthetic tickets...")
    df = generate_dataset(n_samples=2000)
    df.to_csv(output_path, index=False)

    print(f"Saved to {output_path}")
    print(f"\nPriority distribution:\n{df['priority'].value_counts()}")
    print(f"\nSLA breach rate: {df['sla_breached'].mean():.1%}")
    print(
        f"\nSample critical ticket:\n{df[df['priority']=='critical'].iloc[0][['title','description']].to_string()}"
    )
