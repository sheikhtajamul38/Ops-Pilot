@"
create table if not exists services (
  id serial primary key,
  name text not null,
  owner text,
  repo_url text,
  runbook text,
  dependencies text[]
);

create table if not exists incidents (
  id serial primary key,
  title text,
  service text,
  severity text,
  start_time timestamptz,
  end_time timestamptz,
  symptoms text,
  root_cause text,
  resolution text,
  status text,
  tags text[]
);

create table if not exists deployments (
  id serial primary key,
  service text,
  version text,
  deployed_at timestamptz,
  commit_sha text,
  changed_by text,
  notes text
);

create table if not exists logs (
  id serial primary key,
  service text,
  level text,
  message text,
  timestamp timestamptz
);
"@ | Out-File -FilePath migrations\001_initial_schema.sql -Encoding utf8