--
-- PostgreSQL database dump
--

\restrict k7bDtKYqWHznGFpHYwHBNHg1EUwcld0dmlwwBgHoU4L2ncDzbMfevsUtBEKJBcy

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ticket_priority; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.ticket_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);


ALTER TYPE public.ticket_priority OWNER TO postgres;

--
-- Name: TYPE ticket_priority; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TYPE public.ticket_priority IS 'Urgency classification; drives SLA timer';


--
-- Name: ticket_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.ticket_status AS ENUM (
    'open',
    'in_progress',
    'on_hold',
    'resolved',
    'closed',
    'reopened'
);


ALTER TYPE public.ticket_status OWNER TO postgres;

--
-- Name: TYPE ticket_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TYPE public.ticket_status IS 'Lifecycle states a ticket can move through';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: attachments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.attachments (
    id integer NOT NULL,
    ticket_id integer NOT NULL,
    uploaded_by_id integer NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path character varying(500) NOT NULL,
    mime_type character varying(100) NOT NULL,
    file_size_bytes bigint NOT NULL,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_attachments_file_size_max CHECK ((file_size_bytes <= 10485760)),
    CONSTRAINT chk_attachments_file_size_positive CHECK ((file_size_bytes > 0))
);


ALTER TABLE public.attachments OWNER TO postgres;

--
-- Name: TABLE attachments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.attachments IS 'File metadata; actual files stored on disk/S3';


--
-- Name: COLUMN attachments.file_path; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.attachments.file_path IS 'Relative path or S3 key';


--
-- Name: COLUMN attachments.file_size_bytes; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.attachments.file_size_bytes IS 'Max 10 MB enforced at DB level';


--
-- Name: attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attachments_id_seq OWNER TO postgres;

--
-- Name: attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.attachments_id_seq OWNED BY public.attachments.id;


--
-- Name: comments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.comments (
    id integer NOT NULL,
    ticket_id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    is_internal boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_comments_content_not_empty CHECK ((length(TRIM(BOTH FROM content)) > 0))
);


ALTER TABLE public.comments OWNER TO postgres;

--
-- Name: TABLE comments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.comments IS 'Discussion thread on tickets';


--
-- Name: COLUMN comments.is_internal; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.comments.is_internal IS 'TRUE = visible only to engineers/admins';


--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.comments_id_seq OWNER TO postgres;

--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.comments_id_seq OWNED BY public.comments.id;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.departments OWNER TO postgres;

--
-- Name: TABLE departments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.departments IS 'Departments handling tickets (IT, HR, Network, etc.)';


--
-- Name: COLUMN departments.is_active; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.departments.is_active IS 'Soft-delete flag; inactive depts hidden from UI';


--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.departments_id_seq OWNER TO postgres;

--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_role_name_lowercase CHECK (((name)::text = lower((name)::text)))
);


ALTER TABLE public.roles OWNER TO postgres;

--
-- Name: TABLE roles; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.roles IS 'User roles: admin, engineer, employee';


--
-- Name: COLUMN roles.name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.roles.name IS 'Unique role identifier, lowercase';


--
-- Name: COLUMN roles.description; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.roles.description IS 'Human-readable role purpose';


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.roles_id_seq OWNER TO postgres;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: sla_policies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sla_policies (
    id integer NOT NULL,
    priority public.ticket_priority NOT NULL,
    response_time_hours integer NOT NULL,
    resolution_time_hours integer NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_sla_resolution_positive CHECK ((resolution_time_hours > 0)),
    CONSTRAINT chk_sla_response_lte_resolution CHECK ((response_time_hours <= resolution_time_hours)),
    CONSTRAINT chk_sla_response_positive CHECK ((response_time_hours > 0))
);


ALTER TABLE public.sla_policies OWNER TO postgres;

--
-- Name: TABLE sla_policies; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sla_policies IS 'SLA targets per priority level';


--
-- Name: COLUMN sla_policies.response_time_hours; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sla_policies.response_time_hours IS 'Max hours to first response';


--
-- Name: COLUMN sla_policies.resolution_time_hours; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sla_policies.resolution_time_hours IS 'Max hours to full resolution';


--
-- Name: sla_policies_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sla_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sla_policies_id_seq OWNER TO postgres;

--
-- Name: sla_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sla_policies_id_seq OWNED BY public.sla_policies.id;


--
-- Name: ticket_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_history (
    id integer NOT NULL,
    ticket_id integer NOT NULL,
    changed_by_id integer NOT NULL,
    field_changed character varying(50) NOT NULL,
    old_value text,
    new_value text,
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.ticket_history OWNER TO postgres;

--
-- Name: TABLE ticket_history; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.ticket_history IS 'Immutable audit log of all ticket changes';


--
-- Name: COLUMN ticket_history.field_changed; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ticket_history.field_changed IS 'Column name that changed, e.g. status, priority';


--
-- Name: COLUMN ticket_history.old_value; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ticket_history.old_value IS 'Value before change (as string)';


--
-- Name: COLUMN ticket_history.new_value; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.ticket_history.new_value IS 'Value after change (as string)';


--
-- Name: ticket_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ticket_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ticket_history_id_seq OWNER TO postgres;

--
-- Name: ticket_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ticket_history_id_seq OWNED BY public.ticket_history.id;


--
-- Name: tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tickets (
    id integer NOT NULL,
    ticket_number character varying(20) NOT NULL,
    title character varying(200) NOT NULL,
    description text NOT NULL,
    status public.ticket_status DEFAULT 'open'::public.ticket_status NOT NULL,
    priority public.ticket_priority DEFAULT 'medium'::public.ticket_priority NOT NULL,
    created_by_id integer NOT NULL,
    assigned_to_id integer,
    department_id integer,
    sla_policy_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    resolved_at timestamp without time zone,
    closed_at timestamp without time zone,
    sla_due_at timestamp without time zone,
    sla_breached boolean DEFAULT false NOT NULL,
    predicted_priority_score numeric(5,4),
    predicted_sla_breach_prob numeric(5,4),
    predicted_resolution_hours numeric(8,2),
    CONSTRAINT chk_tickets_closed_after_resolved CHECK (((closed_at IS NULL) OR (resolved_at IS NULL) OR (closed_at >= resolved_at))),
    CONSTRAINT chk_tickets_description_length CHECK ((length(TRIM(BOTH FROM description)) >= 10)),
    CONSTRAINT chk_tickets_predicted_priority_range CHECK (((predicted_priority_score IS NULL) OR ((predicted_priority_score >= (0)::numeric) AND (predicted_priority_score <= (1)::numeric)))),
    CONSTRAINT chk_tickets_predicted_sla_range CHECK (((predicted_sla_breach_prob IS NULL) OR ((predicted_sla_breach_prob >= (0)::numeric) AND (predicted_sla_breach_prob <= (1)::numeric)))),
    CONSTRAINT chk_tickets_resolved_after_created CHECK (((resolved_at IS NULL) OR (resolved_at >= created_at))),
    CONSTRAINT chk_tickets_title_length CHECK ((length(TRIM(BOTH FROM title)) >= 5))
);


ALTER TABLE public.tickets OWNER TO postgres;

--
-- Name: TABLE tickets; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.tickets IS 'Core ticket entity — drives the ITSM workflow';


--
-- Name: COLUMN tickets.ticket_number; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tickets.ticket_number IS 'Human-friendly ID like TKT-2025-00001';


--
-- Name: COLUMN tickets.sla_due_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tickets.sla_due_at IS 'Deadline derived from sla_policy.resolution_time_hours';


--
-- Name: COLUMN tickets.predicted_priority_score; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tickets.predicted_priority_score IS 'ML probability that priority should be HIGH; 0–1';


--
-- Name: COLUMN tickets.predicted_sla_breach_prob; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tickets.predicted_sla_breach_prob IS 'ML probability of SLA breach; 0–1';


--
-- Name: COLUMN tickets.predicted_resolution_hours; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tickets.predicted_resolution_hours IS 'ML-predicted resolution time in hours';


--
-- Name: tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tickets_id_seq OWNER TO postgres;

--
-- Name: tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tickets_id_seq OWNED BY public.tickets.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(100) NOT NULL,
    role_id integer NOT NULL,
    department_id integer,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login_at timestamp without time zone,
    CONSTRAINT chk_users_email_format CHECK (((email)::text ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'::text)),
    CONSTRAINT chk_users_username_format CHECK (((username)::text ~* '^[a-z0-9_]{3,50}$'::text))
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.users IS 'User accounts (admins, engineers, employees)';


--
-- Name: COLUMN users.password_hash; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.password_hash IS 'bcrypt hash; never plain text';


--
-- Name: COLUMN users.department_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.department_id IS 'For engineers: which dept they handle. NULL for employees';


--
-- Name: COLUMN users.last_login_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.last_login_at IS 'Last successful login timestamp; for audit';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: attachments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments ALTER COLUMN id SET DEFAULT nextval('public.attachments_id_seq'::regclass);


--
-- Name: comments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments ALTER COLUMN id SET DEFAULT nextval('public.comments_id_seq'::regclass);


--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: sla_policies id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sla_policies ALTER COLUMN id SET DEFAULT nextval('public.sla_policies_id_seq'::regclass);


--
-- Name: ticket_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_history ALTER COLUMN id SET DEFAULT nextval('public.ticket_history_id_seq'::regclass);


--
-- Name: tickets id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets ALTER COLUMN id SET DEFAULT nextval('public.tickets_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
879b53d74f82
\.


--
-- Data for Name: attachments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.attachments (id, ticket_id, uploaded_by_id, file_name, file_path, mime_type, file_size_bytes, uploaded_at) FROM stdin;
\.


--
-- Data for Name: comments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.comments (id, ticket_id, user_id, content, is_internal, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: departments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.departments (id, name, description, is_active, created_at, updated_at) FROM stdin;
1	IT Support	Hardware, OS, general IT issues	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
2	Network	Connectivity, VPN, firewall, Wi-Fi	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
3	Software	Application bugs, installations, licenses	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
4	Security	Account access, breaches, phishing	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
5	HR	HR systems, payroll, leave portal	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
6	Finance	Expense systems, invoice tools, ERP	t	2026-06-26 12:40:57.110183	2026-06-26 12:40:57.110183
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.roles (id, name, description, created_at) FROM stdin;
1	admin	Full system access — manages users, dashboards, configs	2026-06-26 12:40:30.112311
2	engineer	Resolves tickets within assigned department	2026-06-26 12:40:30.112311
3	employee	Raises tickets and tracks their progress	2026-06-26 12:40:30.112311
\.


--
-- Data for Name: sla_policies; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sla_policies (id, priority, response_time_hours, resolution_time_hours, description, created_at, updated_at) FROM stdin;
1	critical	1	4	P1 — major outage; immediate response, 4-hour fix	2026-06-26 12:41:21.453769	2026-06-26 12:41:21.453769
2	high	2	8	P2 — significant impact; same-day resolution	2026-06-26 12:41:21.453769	2026-06-26 12:41:21.453769
3	medium	4	24	P3 — moderate impact; next-business-day	2026-06-26 12:41:21.453769	2026-06-26 12:41:21.453769
4	low	8	72	P4 — minor; 3-business-day resolution	2026-06-26 12:41:21.453769	2026-06-26 12:41:21.453769
\.


--
-- Data for Name: ticket_history; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.ticket_history (id, ticket_id, changed_by_id, field_changed, old_value, new_value, changed_at) FROM stdin;
\.


--
-- Data for Name: tickets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tickets (id, ticket_number, title, description, status, priority, created_by_id, assigned_to_id, department_id, sla_policy_id, created_at, updated_at, resolved_at, closed_at, sla_due_at, sla_breached, predicted_priority_score, predicted_sla_breach_prob, predicted_resolution_hours) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, email, username, password_hash, full_name, role_id, department_id, is_active, created_at, updated_at, last_login_at) FROM stdin;
1	admin@helpdesk.local	admin	\\$2b$12$LQv3c1yqBwEHxv6mZJ8Z8O7P8N5dQEzKYpJ9BqEcMmqRxQ0vSXmFu	System Administrator	1	1	t	2026-06-26 12:41:49.716144	2026-06-26 12:41:49.716144	\N
\.


--
-- Name: attachments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.attachments_id_seq', 1, false);


--
-- Name: comments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.comments_id_seq', 1, false);


--
-- Name: departments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.departments_id_seq', 12, true);


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.roles_id_seq', 3, true);


--
-- Name: sla_policies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sla_policies_id_seq', 4, true);


--
-- Name: ticket_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ticket_history_id_seq', 1, false);


--
-- Name: tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tickets_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 3, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: attachments attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_pkey PRIMARY KEY (id);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: departments departments_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_name_key UNIQUE (name);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: sla_policies sla_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_pkey PRIMARY KEY (id);


--
-- Name: sla_policies sla_policies_priority_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_priority_key UNIQUE (priority);


--
-- Name: ticket_history ticket_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_history
    ADD CONSTRAINT ticket_history_pkey PRIMARY KEY (id);


--
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (id);


--
-- Name: tickets tickets_ticket_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_ticket_number_key UNIQUE (ticket_number);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: attachments fk_attachments_ticket; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT fk_attachments_ticket FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE CASCADE;


--
-- Name: attachments fk_attachments_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT fk_attachments_user FOREIGN KEY (uploaded_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: comments fk_comments_ticket; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT fk_comments_ticket FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE CASCADE;


--
-- Name: comments fk_comments_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: ticket_history fk_history_ticket; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_history
    ADD CONSTRAINT fk_history_ticket FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE CASCADE;


--
-- Name: ticket_history fk_history_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_history
    ADD CONSTRAINT fk_history_user FOREIGN KEY (changed_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: tickets fk_tickets_assigned_to; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT fk_tickets_assigned_to FOREIGN KEY (assigned_to_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: tickets fk_tickets_created_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT fk_tickets_created_by FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: tickets fk_tickets_department; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT fk_tickets_department FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: tickets fk_tickets_sla_policy; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT fk_tickets_sla_policy FOREIGN KEY (sla_policy_id) REFERENCES public.sla_policies(id) ON DELETE SET NULL;


--
-- Name: users fk_users_department; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_department FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: users fk_users_role; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict k7bDtKYqWHznGFpHYwHBNHg1EUwcld0dmlwwBgHoU4L2ncDzbMfevsUtBEKJBcy

