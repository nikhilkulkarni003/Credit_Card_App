insert into banks (name, code, statement_format, active) values
  ('IndusInd Bank', 'INDUSIND', 'IndusInd Bank credit card e-statement PDF', true)
on conflict (code) do nothing;
