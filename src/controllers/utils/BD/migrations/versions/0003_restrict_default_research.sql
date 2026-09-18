UPDATE library_sections
SET read_policy = 'restricted', updated_at = CURRENT_TIMESTAMP
WHERE domain = 'research'
  AND key = 'main'
  AND read_policy = 'authenticated';
