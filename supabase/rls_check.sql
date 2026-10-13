-- Our Week: check that the privacy rules hold.
-- Run in the Supabase SQL Editor (or any Postgres set up with schema.sql). It changes nothing:
-- it finishes with a deliberate error, which undoes everything it did and shows the results.
-- Before running, put your two member emails in the first two variables below.

do $$
declare
  member_one text := 'person-one@example.com';
  member_two text := 'person-two@example.com';
  report text := '';
  n int;
begin
  -- A signed-out visitor (the "anon" role) tries to add an entry.
  set local role anon;
  begin
    insert into public.entries (date, name, owner, type) values ('2026-01-01', 'lock test', 'both', 'plan');
    report := report || E'\n❌ A signed-out visitor was able to ADD an entry.';
  exception when insufficient_privilege then
    report := report || E'\n✅ A signed-out visitor is refused when adding an entry.';
  end;

  -- Someone signed in whose email is NOT on the list tries to add.
  set local role authenticated;
  perform set_config('request.jwt.claims', '{"email":"stranger@example.com","role":"authenticated"}', true);
  begin
    insert into public.entries (date, name, owner, type) values ('2026-01-01', 'lock test', 'both', 'plan');
    report := report || E'\n❌ A signed-in stranger was able to ADD an entry.';
  exception when insufficient_privilege then
    report := report || E'\n✅ A signed-in stranger is refused when adding an entry.';
  end;

  -- The first member adds an entry.
  perform set_config('request.jwt.claims', json_build_object('email', member_one, 'role', 'authenticated')::text, true);
  begin
    insert into public.entries (date, name, owner, type) values ('2026-01-01', 'lock test', 'both', 'plan');
    report := report || E'\n✅ A member can add an entry.';
  exception when others then
    report := report || E'\n❌ A member could NOT add an entry: ' || sqlerrm;
  end;

  -- A signed-out visitor tries to see it. Either a refusal or zero rows counts as blocked.
  set local role anon;
  begin
    select count(*) into n from public.entries;
    report := report || case when n = 0 then E'\n✅ A signed-out visitor sees no entries.' else E'\n❌ A signed-out visitor can see ' || n || ' entries.' end;
  exception when insufficient_privilege then
    report := report || E'\n✅ A signed-out visitor is refused when reading entries.';
  end;
  set local role authenticated;

  -- The stranger tries to see, change and delete it.
  perform set_config('request.jwt.claims', '{"email":"stranger@example.com","role":"authenticated"}', true);
  select count(*) into n from public.entries;
  report := report || case when n = 0 then E'\n✅ A signed-in stranger cannot see the entry.' else E'\n❌ A signed-in stranger can see ' || n || ' entries.' end;
  update public.entries set done = true where true;
  get diagnostics n = row_count;
  report := report || case when n = 0 then E'\n✅ A signed-in stranger cannot change it.' else E'\n❌ A signed-in stranger changed ' || n || ' entries.' end;
  delete from public.entries where true;
  get diagnostics n = row_count;
  report := report || case when n = 0 then E'\n✅ A signed-in stranger cannot delete it.' else E'\n❌ A signed-in stranger deleted ' || n || ' entries.' end;

  -- The stranger cannot read the members list either.
  begin
    select count(*) into n from public.members;
    report := report || case when n = 0 then E'\n✅ A signed-in stranger sees nothing in the members list.' else E'\n❌ A signed-in stranger can see ' || n || ' members.' end;
  exception when insufficient_privilege then
    report := report || E'\n✅ A signed-in stranger cannot read the members list.';
  end;

  -- The second member can see what the first added.
  perform set_config('request.jwt.claims', json_build_object('email', member_two, 'role', 'authenticated')::text, true);
  select count(*) into n from public.entries;
  report := report || case when n = 1 then E'\n✅ The second member can see the entry the first added.' else E'\n❌ The second member sees ' || n || ' entries instead of 1.' end;

  -- Ending with an error on purpose: it undoes everything above, so nothing is saved.
  raise exception E'RESULT (nothing was saved):%', report;
end
$$;
