"""Few-shot examples that steer SQL generation toward correct joins.

Each example pairs a question with the SELECT it should produce. They teach the
model the house style: join lookup tables, return readable names, alias
aggregates, and never touch a forbidden table.
"""

EXAMPLES = [
    {
        "question": "How many permits are pending?",
        "sql": (
            "SELECT COUNT(*) AS total "
            "FROM permits p "
            "JOIN permit_statuses ps ON ps.id = p.status_id "
            "WHERE ps.status = 'Pending'"
        ),
    },
    {
        "question": "Count permits by status.",
        "sql": (
            "SELECT ps.status, COUNT(*) AS permit_count "
            "FROM permits p "
            "JOIN permit_statuses ps ON ps.id = p.status_id "
            "GROUP BY ps.status "
            "ORDER BY permit_count DESC"
        ),
    },
    {
        "question": "Show electrical permits.",
        "sql": (
            "SELECT p.application_number, p.applicant_name, "
            "pt.name AS permit_type "
            "FROM permits p "
            "JOIN permit_types pt ON pt.id = p.permit_type_id "
            "WHERE pt.name = 'Electrical' "
            "LIMIT 100"
        ),
    },
    {
        "question": "Which officer approved the most permits?",
        "sql": (
            "SELECT o.name AS officer, COUNT(*) AS approved "
            "FROM permits p "
            "JOIN officers o ON o.id = p.officer_id "
            "JOIN permit_statuses ps ON ps.id = p.status_id "
            "WHERE ps.status = 'Approved' "
            "GROUP BY o.name "
            "ORDER BY approved DESC "
            "LIMIT 100"
        ),
    },
    {
        # There is no inspection-date column; "Inspection Scheduled" is a
        # status. Bridge the question to the status the schema actually stores.
        "question": "Is permit PERM-2026-000005's inspection scheduled?",
        "sql": (
            "SELECT p.application_number, ps.status "
            "FROM permits p "
            "JOIN permit_statuses ps ON ps.id = p.status_id "
            "WHERE p.application_number = 'PERM-2026-000005' "
            "LIMIT 100"
        ),
    },
    {
        # Single-permit lookup -> the labelled status card. Pull every card
        # field in one query and LEFT JOIN pending documents (received = 0) so
        # a permit with nothing outstanding still returns its row.
        "question": "What's the status of permit PERM-2026-000012?",
        "sql": (
            "SELECT p.application_number, ps.status, "
            "pt.name AS permit_type, p.submitted_date, "
            "p.estimated_completion_date, o.name AS officer, o.department, "
            "d.doc_name AS pending_document "
            "FROM permits p "
            "JOIN permit_statuses ps ON ps.id = p.status_id "
            "JOIN permit_types pt ON pt.id = p.permit_type_id "
            "JOIN officers o ON o.id = p.officer_id "
            "LEFT JOIN permit_documents d "
            "ON d.permit_id = p.id AND d.received = 0 "
            "WHERE p.application_number = 'PERM-2026-000012'"
        ),
    },
]
