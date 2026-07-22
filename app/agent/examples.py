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
]
