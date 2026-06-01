SELECT (
    key,
    value
)::service.key_value_table_v0
FROM service.key_value_table WHERE key=$1
