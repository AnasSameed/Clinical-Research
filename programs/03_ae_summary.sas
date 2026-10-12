/*------------------------------------------------------------------
  03_ae_summary.sas  -  adverse event table: subjects with >=1 treatment-emergent AE
  Input : data/raw/ae_raw.csv, outlib.adsl
  Output: a PROC REPORT table (n and % of safety-population subjects, by treatment)

  Rules used (simplified):
   * Only the safety population (SAFFL="Y") is counted
   * Treatment-emergent = AE start date on or after first dose date
   * A subject is counted once per term (and once per body system)
-------------------------------------------------------------------*/
/* Run 00_setup.sas first, in the same SAS session, so the macro variable ROOT and the library OUTLIB exist. */

/* 1. Read raw AEs */
data ae_raw;
  infile "&root./data/raw/ae_raw.csv" dsd firstobs=2 truncover;
  length SUBJID $4 AETERM $60 AEBODSYS $60 AESEV $8 AESTDTC $10 AESER $1;
  input SUBJID $ AETERM $ AEBODSYS $ AESEV $ AESTDTC $ AESER $;
run;

/* 2. Join to ADSL (inner join also drops AEs of subjects who are not in the safety population) */
proc sql;
  create table adae as
  select a.*, d.USUBJID, d.TRT01P, d.TRT01PN, d.TRTSDT
  from ae_raw as a
       inner join outlib.adsl as d
       on a.SUBJID = d.SUBJID
  where d.SAFFL = "Y";
quit;

data adae;
  set adae;
  AESTDT = input(AESTDTC, ?? yymmdd10.);
  format AESTDT date9.;
  if not missing(AESTDT) and AESTDT >= TRTSDT then TRTEMFL = "Y";
  else TRTEMFL = "N";
run;

/* 3. Denominators (N per treatment) and subject counts per body system / term */
proc sql noprint;
  create table denom as
  select TRT01PN, count(distinct USUBJID) as bigN
  from outlib.adsl
  where SAFFL = "Y"
  group by TRT01PN;

  select bigN into :n1 trimmed from denom where TRT01PN = 1;
  select bigN into :n2 trimmed from denom where TRT01PN = 2;

  create table aecount as
  select TRT01PN, AEBODSYS, AETERM, count(distinct USUBJID) as n
  from adae
  where TRTEMFL = "Y"
  group by TRT01PN, AEBODSYS, AETERM;
quit;

/* 4. Build the "n (xx.x%)" text cell */
proc sql;
  create table aesum as
  select c.AEBODSYS, c.AETERM, c.TRT01PN,
         cats(put(c.n, 3.), " (", put(100 * c.n / d.bigN, 5.1), "%)") as cell length=20
  from aecount as c inner join denom as d on c.TRT01PN = d.TRT01PN;
quit;

proc sort data=aesum; by AEBODSYS AETERM TRT01PN; run;

proc transpose data=aesum out=aewide(drop=_name_) prefix=TRT;
  by AEBODSYS AETERM;
  id TRT01PN;
  var cell;
run;

/* terms that never occurred in an arm should show 0, not blank */
data aewide;
  set aewide;
  if missing(TRT1) then TRT1 = "0";
  if missing(TRT2) then TRT2 = "0";
run;

/* 5. Report */
title "Subjects with Treatment-Emergent Adverse Events (Safety Population)";
title2 "Synthetic practice data";
proc report data=aewide nowd headline split="|";
  column AEBODSYS AETERM TRT1 TRT2;
  define AEBODSYS / order "System Organ Class" order=internal width=34 flow;
  define AETERM   / order "Preferred Term"     order=internal width=30 flow;
  define TRT1     / display "Placebo|(N=&n1.)" center width=14;
  define TRT2     / display "Drug 10 mg|(N=&n2.)" center width=14;
run;
title;
