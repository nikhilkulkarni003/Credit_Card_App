insert into banks (name, code, statement_format, active) values
  ('ICICI Bank', 'ICICI', 'Amazon Pay ICICI Bank credit card e-statement PDF', true)
on conflict (code) do nothing;
