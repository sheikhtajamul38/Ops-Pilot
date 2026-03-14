@"
create table if not exists audit_log (
  id serial primary key,
  query text,
  service text,
  tools_used text[],
  answer text,
  created_at timestamptz default now()
);

alter table audit_log disable row level security;
"@ | Out-File -FilePath migrations\002_audit_trail.sql -Encoding utf8