-- Insert default departments
INSERT INTO departments (name, description) VALUES
    ('IT Support',  'Hardware, OS, general IT issues'),
    ('Network',     'Connectivity, VPN, firewall, Wi-Fi'),
    ('Software',    'Application bugs, installations, licenses'),
    ('Security',    'Account access, breaches, phishing'),
    ('HR',          'HR systems, payroll, leave portal'),
    ('Finance',     'Expense systems, invoice tools, ERP')
ON CONFLICT (name) DO NOTHING;

