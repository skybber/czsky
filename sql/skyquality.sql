CREATE TABLE locations(location_id integer primary key,
    name varchar2(256),
    coords varchar2(128),
    create_by varchar2(128),
    elevation varchar2(128),
    descr text,
    accessibility text,
    sqm_avg varchar2(32),
    bortle_scale varchar2(32)
    );

 CREATE INDEX ix_locations_orig_id ON locations (orig_id);
