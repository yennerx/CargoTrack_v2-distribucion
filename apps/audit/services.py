FILTER_KEY_RENAMES = {
    "broker": "broker_id",
    "carrier": "carrier_id",
    "customer": "customer_id",
    "status": "status_id",
}


def audit_filter_metadata(filters):
    safe_filters = {}
    for key, value in filters.items():
        if value is None or value == "" or key == "query":
            continue
        safe_key = FILTER_KEY_RENAMES.get(key, key)
        safe_value = value.pk if hasattr(value, "pk") else str(value)
        safe_filters[safe_key] = safe_value
    return safe_filters
