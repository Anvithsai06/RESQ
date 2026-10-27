-- RESQ initial schema
-- Tables: buildings, cameras, zones, exits, incidents, tracks, events,
-- baselines, priority_history, notifications

create table if not exists buildings (
    building_id text primary key,
    name text not null,
    address text,
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists cameras (
    camera_id text primary key,
    building_id text references buildings(building_id),
    name text,
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists zones (
    zone_id text primary key,
    camera_id text references cameras(camera_id),
    type text not null,               -- danger | obstruction | safe_observation
    polygon jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists exits (
    exit_id text primary key,
    camera_id text references cameras(camera_id),
    polygon jsonb not null,
    trusted boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists tracks (
    id bigserial primary key,
    track_id integer not null,
    camera_id text references cameras(camera_id),
    class text not null,
    first_seen timestamptz not null,
    last_seen timestamptz not null,
    current_zone text,
    trajectory jsonb,
    created_at timestamptz not null default now()
);

create table if not exists events (
    id bigserial primary key,
    camera_id text references cameras(camera_id),
    event_type text not null,          -- zone_enter | zone_exit | exit_state_change | hazard_detected
    payload jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now()
);

create table if not exists baselines (
    id bigserial primary key,
    camera_id text references cameras(camera_id),
    stats jsonb not null,
    window_start timestamptz not null,
    window_end timestamptz not null,
    created_at timestamptz not null default now()
);

create table if not exists priority_history (
    id bigserial primary key,
    camera_id text references cameras(camera_id),
    priority numeric not null,
    contributors jsonb not null default '[]'::jsonb,
    confidence numeric,
    uncertainty boolean not null default false,
    recorded_at timestamptz not null default now()
);

create table if not exists incidents (
    incident_id bigserial primary key,
    camera_id text references cameras(camera_id),
    state jsonb not null,              -- full Incident State snapshot
    priority numeric not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists notifications (
    id bigserial primary key,
    incident_id bigint references incidents(incident_id),
    building_id text references buildings(building_id),
    recipient_service_id text not null,
    recipient_name text not null,
    channel_type text not null,        -- sms | email | webhook
    status text not null,              -- sent | failed | suppressed_cooldown | suppressed_not_persistent | pending
    payload jsonb not null,
    detail text,
    created_at timestamptz not null default now()
);

create index if not exists idx_events_camera_time on events(camera_id, occurred_at);
create index if not exists idx_priority_history_camera_time on priority_history(camera_id, recorded_at);
create index if not exists idx_notifications_incident on notifications(incident_id);
