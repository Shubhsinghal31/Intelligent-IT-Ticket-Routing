-- Insert SLA policies per priority
INSERT INTO sla_policies (priority, response_time_hours, resolution_time_hours, description) VALUES
    ('critical', 1,  4,   'P1 — major outage; immediate response, 4-hour fix'),
    ('high',     2,  8,   'P2 — significant impact; same-day resolution'),
    ('medium',   4,  24,  'P3 — moderate impact; next-business-day'),
    ('low',      8,  72,  'P4 — minor; 3-business-day resolution')
ON CONFLICT (priority) DO NOTHING;