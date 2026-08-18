-- Keep existing demo databases aligned with the current judge-facing case names.

UPDATE customers
SET display_name = CASE customer_id
  WHEN 'C-184' THEN 'Srinivas'
  WHEN 'C-044' THEN 'Maya Carter'
  WHEN 'C-771' THEN 'Daniel Brooks'
  WHEN 'C-841' THEN 'Elena Torres'
  WHEN 'C-992' THEN 'Noah Bennett'
END
WHERE customer_id IN ('C-184', 'C-044', 'C-771', 'C-841', 'C-992');
