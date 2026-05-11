SELECT (
    key,
    value
)::key_value_table_v0
FROM key_value_table WHERE key=$1
