-- Run this first, while connected to any existing database (e.g. postgres):
--   psql -U halima -d postgres -f nasa_database.sql
DROP DATABASE IF EXISTS NASA;
CREATE DATABASE NASA;
\c nasa
CREATE TABLE envi(
   envi_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   mission_name VARCHAR (100) NOT NULL UNIQUE
);

CREATE TABLE astro (
   astro_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY ,
   astro_name VARCHAR (100) NOT NULL,
   envi_id INT NOT NULL,
   CONSTRAINT has FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE parameter(
  param_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY ,
  param_name VARCHAR (50) NOT NULL UNIQUE,
  category VARCHAR (50) NOT NULL ,
  unit VARCHAR (30),
  lower_limit DOUBLE precision,
  upper_limit DOUBLE PRECISION,
  explination TEXT
);


CREATE TABLE bio_data(
   bio_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   astro_id INT NOT NULL,
   time TIMESTAMP NOT NULL,
   bpm INT NOT NULL,
   sys INT NOT NULL,
   dia INT NOT NULL,
   envi_id INT NOT NULL,
   temperature DOUBLE PRECISION NOT NULL,
   rmssd DOUBLE PRECISION NOT NULL,
   CONSTRAINT fk_asto_bio  FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
   CONSTRAINT fk_envi_bio  FOREIGN KEY (astro_id) REFERENCES astro(astro_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE psycho_data(
   psycho_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   astro_id INT NOT NULL,
   envi_id  INT NOT NULL,
   time TIMESTAMP NOT NULL,
   work INT ,
   team INT ,
   mood INT,
   CONSTRAINT fk_psycho FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
   CONSTRAINT fk_astorpsych FOREIGN KEY (astro_id) REFERENCES astro(astro_id)
   ON UPDATE CASCADE ON DELETE CASCADE  
);

CREATE TABLE envi_data(
   envi_data_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   envi_id INT NOT NULL,
   time TIMESTAMP NOT NULL,
   humidity DOUBLE PRECISION,
   radiation DOUBLE PRECISION,
   o2 DOUBLE PRECISION ,
   CONSTRAINT  fk_envi_data FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
   ON UPDATE CASCADE ON DELETE CASCADE);

CREATE TABLE suggested_activity(
  activity_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  activity_name VARCHAR(100),
  category VARCHAR (50) NOT NULL,
  duration_minites INT,
  activity_descrip TEXT
);


CREATE TABLE indi_result(
   result_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   astro_id INT NOT NULL,
   evaluation_date DATE NOT NULL DEFAULT CURRENT_DATE,
   risk_level VARCHAR(30) NOT NULL,
   envi_id INT NOT NULL,
   stress_level INT,
   recomended_activity_id INT,
   CONSTRAINT fk_indi_envi  FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
   CONSTRAINT fk_indi_astro FOREIGN KEY (astro_id) REFERENCES astro(astro_id)
   ON UPDATE CASCADE ON DELETE CASCADE,  
   CONSTRAINT fk_indi_activity FOREIGN KEY (recomended_activity_id) REFERENCES suggested_activity(activity_id)
    ON UPDATE CASCADE ON DELETE SET NULL
);

 CREATE TABLE  team_result(
   team_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   envi_id INT NOT NULL,
   assessemnt TEXT,
   recomended_activity_id INT, 
   risk_level VARCHAR(30) NOT NULL,
   CONSTRAINT fk_team FOREIGN KEY (envi_id) REFERENCES envi(envi_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
   CONSTRAINT fk_indi_activity FOREIGN KEY (recomended_activity_id) REFERENCES suggested_activity(activity_id)
    ON UPDATE CASCADE ON DELETE SET NULL
   );
