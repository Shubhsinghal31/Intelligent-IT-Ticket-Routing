-- Insert the 3 roles
INSERT INTO roles (name, description) VALUES
    ('admin',    'Full system access — manages users, dashboards, configs'),
    ('engineer', 'Resolves tickets within assigned department'),
    ('employee', 'Raises tickets and tracks their progress')
ON CONFLICT (name) DO NOTHING;