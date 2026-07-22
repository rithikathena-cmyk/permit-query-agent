ALLOWED_TABLES = {
    "permits",
    "permit_types",
    "permit_statuses",
    "cities",
    "officers",
    "permit_details"
}

FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SET",
    "SHOW",
    "DESCRIBE",
    "INTO",
    "OUTFILE",
    "DUMPFILE",
    "LOAD_FILE"
}

MAX_LIMIT = 100
