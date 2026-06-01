INSERT INTO service.key_value_table (key, value)
VALUES ($1, $2)
ON CONFLICT DO NOTHING
