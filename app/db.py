import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "faturas.db"


SCHEMA = """
create table if not exists invoices (
  id text primary key,
  airhub text not null,
  competence text not null,
  site_name text,
  supplier text default 'DHL',
  thread_id text,
  message_id text,
  subject text,
  sender text,
  attachment_name text,
  attachment_path text,
  status text not null default 'aguardando_analise',
  total_labor real default 0,
  total_others real default 0,
  total_net real default 0,
  total_with_taxes real default 0,
  created_at text default current_timestamp,
  updated_at text default current_timestamp
);

create table if not exists analysis_lines (
  id integer primary key autoincrement,
  invoice_id text references invoices(id),
  group_name text,
  opex_line text,
  invoice_line text,
  opex_value real,
  invoice_value real,
  delta_value real,
  previous_delta_value real,
  risk text,
  status text,
  insight text
);

create table if not exists overtime_lines (
  id integer primary key autoincrement,
  invoice_id text references invoices(id),
  cause text,
  overtime_date text,
  hours real,
  total_value real,
  line_count integer,
  action text
);

create table if not exists others_lines (
  id integer primary key autoincrement,
  invoice_id text references invoices(id),
  item text,
  account text,
  supplier text,
  total_value real,
  opex_reference real,
  previous_delta real,
  insight text
);

create table if not exists decisions (
  id integer primary key autoincrement,
  invoice_id text references invoices(id),
  action text not null,
  status text not null,
  email_body text,
  n8n_payload text,
  created_at text default current_timestamp
);
"""


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def rows(query, params=()):
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def row(query, params=()):
    with connect() as conn:
        result = conn.execute(query, params).fetchone()
        return dict(result) if result else None
