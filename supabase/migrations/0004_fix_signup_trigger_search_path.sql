-- Fix: SECURITY DEFINER functions invoked by the Auth server run with a minimal
-- search_path, so the unqualified table references in 0003 (profiles, categories)
-- failed to resolve, surfacing to the client as "Database error saving new user".
-- Fix: pin search_path explicitly and fully-qualify table names with `public.`.

create or replace function seed_default_categories_for_user(p_user_id uuid)
returns void as $$
declare
  v_parent_id uuid;
begin
  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Food & Dining', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Restaurants', v_parent_id, true),
    (p_user_id, 'Food Delivery', v_parent_id, true),
    (p_user_id, 'Cafes', v_parent_id, true),
    (p_user_id, 'Fast Food', v_parent_id, true),
    (p_user_id, 'Groceries', v_parent_id, true),
    (p_user_id, 'Bakery', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Travel & Transport', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Flights', v_parent_id, true),
    (p_user_id, 'Hotels', v_parent_id, true),
    (p_user_id, 'Trains', v_parent_id, true),
    (p_user_id, 'Bus', v_parent_id, true),
    (p_user_id, 'Cab', v_parent_id, true),
    (p_user_id, 'Fuel', v_parent_id, true),
    (p_user_id, 'Parking', v_parent_id, true),
    (p_user_id, 'Toll', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Entertainment', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Movies', v_parent_id, true),
    (p_user_id, 'OTT', v_parent_id, true),
    (p_user_id, 'Events', v_parent_id, true),
    (p_user_id, 'Gaming', v_parent_id, true),
    (p_user_id, 'Music', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Shopping', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Clothing', v_parent_id, true),
    (p_user_id, 'Electronics', v_parent_id, true),
    (p_user_id, 'Online Shopping', v_parent_id, true),
    (p_user_id, 'Household', v_parent_id, true),
    (p_user_id, 'Personal Care', v_parent_id, true),
    (p_user_id, 'Gifts', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Utilities', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Mobile', v_parent_id, true),
    (p_user_id, 'Internet', v_parent_id, true),
    (p_user_id, 'Electricity', v_parent_id, true),
    (p_user_id, 'Gas', v_parent_id, true),
    (p_user_id, 'DTH', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Professional', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Software', v_parent_id, true),
    (p_user_id, 'Courses', v_parent_id, true),
    (p_user_id, 'Books', v_parent_id, true),
    (p_user_id, 'Office Expenses', v_parent_id, true),
    (p_user_id, 'Professional Services', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Financial', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Interest', v_parent_id, true),
    (p_user_id, 'GST', v_parent_id, true),
    (p_user_id, 'Late Payment Fee', v_parent_id, true),
    (p_user_id, 'Annual Fee', v_parent_id, true),
    (p_user_id, 'Bank Charges', v_parent_id, true),
    (p_user_id, 'EMI', v_parent_id, true),
    (p_user_id, 'Insurance', v_parent_id, true),
    (p_user_id, 'Investments', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Health', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Pharmacy', v_parent_id, true),
    (p_user_id, 'Doctor', v_parent_id, true),
    (p_user_id, 'Medical Tests', v_parent_id, true),
    (p_user_id, 'Fitness', v_parent_id, true);

  insert into public.categories (user_id, name, system_default) values (p_user_id, 'Other', true) returning id into v_parent_id;
  insert into public.categories (user_id, name, parent_id, system_default) values
    (p_user_id, 'Family', v_parent_id, true),
    (p_user_id, 'Charity', v_parent_id, true),
    (p_user_id, 'Miscellaneous', v_parent_id, true);
end;
$$ language plpgsql security definer set search_path = public, pg_temp;

create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (user_id, display_name) values (new.id, new.raw_user_meta_data->>'full_name');
  perform public.seed_default_categories_for_user(new.id);
  return new;
end;
$$ language plpgsql security definer set search_path = public, pg_temp;
