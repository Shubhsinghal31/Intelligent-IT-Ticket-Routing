-- ============================================================
-- Seed: Default admin user
-- ============================================================
-- Password: Admin@12345
-- bcrypt hash generated with cost factor 12
-- IMPORTANT: Change this password immediately after first login!
-- ============================================================

INSERT INTO users (
    email,
    username,
    password_hash,
    full_name,
    role_id,
    department_id,
    is_active
) VALUES (
    'admin@helpdesk.local',
    'admin',
    '$2b$12$18Oty7E5d2z9dVElebOsXOgzLiNcBMiBjdy5DN/kqSjq3OjTKgXQu',  -- bcrypt of "Admin@12345" (cost factor 12, generated via hash_password())
    'System Administrator',
    (SELECT id FROM roles WHERE name = 'admin'),
    (SELECT id FROM departments WHERE name = 'IT Support'),
    TRUE
)
ON CONFLICT (email) DO NOTHING;