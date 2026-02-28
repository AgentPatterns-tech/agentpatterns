from __future__ import annotations

from typing import Any

KB_DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "doc_sla_enterprise_v3",
        "source": "support_policy",
        "title": "Support Policy",
        "section": "Enterprise SLA",
        "updated_at": "2026-01-15",
        "text": (
            "Enterprise plan includes 99.95% monthly uptime SLA. "
            "For P1 incidents, first response target is 15 minutes, 24/7. "
            "For P2 incidents, first response target is 1 hour."
        ),
    },
    {
        "id": "doc_sla_standard_v2",
        "source": "support_policy",
        "title": "Support Policy",
        "section": "Standard SLA",
        "updated_at": "2025-11-10",
        "text": (
            "Standard plan includes 99.5% monthly uptime SLA. "
            "For P1 incidents, first response target is 1 hour during business hours."
        ),
    },
    {
        "id": "doc_security_incident_v2",
        "source": "security_policy",
        "title": "Security Incident Playbook",
        "section": "Escalation",
        "updated_at": "2026-01-20",
        "text": (
            "For enterprise customers, security-related P1 incidents require immediate escalation "
            "to the on-call incident commander and customer success lead."
        ),
    },
    {
        "id": "doc_refund_policy_v4",
        "source": "billing_policy",
        "title": "Billing and Refund Policy",
        "section": "Refund Eligibility",
        "updated_at": "2025-12-01",
        "text": (
            "Annual enterprise subscriptions may receive a prorated refund within 14 days "
            "under approved exception flow."
        ),
    },
    {
        "id": "doc_onboarding_checklist_v1",
        "source": "operations_notes",
        "title": "Enterprise Onboarding Checklist",
        "section": "Launch Prep",
        "updated_at": "2025-09-02",
        "text": (
            "Checklist for onboarding includes SSO setup, domain verification, and success plan kickoff."
        ),
    },
]
