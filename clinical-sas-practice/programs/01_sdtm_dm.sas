/*------------------------------------------------------------------
  01_sdtm_dm.sas  -  build a simplified SDTM DM (Demographics) dataset
  Input : data/raw/dm_raw.csv   (synthetic)
  Output: outlib.dm
  Note  : simplified for practice; not a full CDISC SDTM-IG compliant build.
-------------------------------------------------------------------*/
/* Run 00_setup.sas first, in the same SAS session, so the macro variable ROOT and the library OUTLIB exist. */

/* 1. Read the raw CSV with explicit lengths so nothing is truncated or guessed */
data dm_raw;
  infile "&root./data/raw/dm_raw.csv" dsd firstobs=2 truncover;
  length SUBJID $4 SITEID $3 SEX $1 RACE $40 ARM $20
         CONSENTDT FIRSTDOSE LASTDOSE $10;
  input SUBJID $ SITEID $ AGE SEX $ RACE $ ARM $ CONSENTDT $ FIRSTDOSE $ LASTDOSE $;
run;

/* 2. Derive SDTM variables */
data outlib.dm;
  length STUDYID $8 DOMAIN $2 USUBJID $20 ARMCD $8 AGEU $5
         RFICDTC RFSTDTC RFENDTC $10;
  set dm_raw;

  STUDYID = "DEMO001";
  DOMAIN  = "DM";
  USUBJID = catx("-", STUDYID, SITEID, SUBJID);

  AGEU = "YEARS";

  /* planned treatment arm code */
  select (ARM);
    when ("Placebo")        ARMCD = "PBO";
    when ("Drug 10 mg")     ARMCD = "TRT10";
    when ("Screen Failure") ARMCD = "SCRNFAIL";
    otherwise               ARMCD = "";
  end;

  /* reference dates (ISO 8601 character dates, as SDTM requires) */
  RFICDTC = CONSENTDT;
  RFSTDTC = FIRSTDOSE;
  RFENDTC = LASTDOSE;

  keep STUDYID DOMAIN USUBJID SUBJID SITEID AGE AGEU SEX RACE ARM ARMCD
       RFICDTC RFSTDTC RFENDTC;
  label STUDYID="Study Identifier" DOMAIN="Domain Abbreviation"
        USUBJID="Unique Subject Identifier" SUBJID="Subject Identifier for the Study"
        SITEID="Study Site Identifier" AGE="Age" AGEU="Age Units" SEX="Sex" RACE="Race"
        ARM="Description of Planned Arm" ARMCD="Planned Arm Code"
        RFICDTC="Date/Time of Informed Consent" RFSTDTC="Subject Reference Start Date/Time"
        RFENDTC="Subject Reference End Date/Time";
run;

/* 3. QC */
%check_unique(ds=outlib.dm, key=USUBJID);
%check_missing(ds=outlib.dm, var=RFSTDTC);   /* expect: the screen failures */
%check_missing(ds=outlib.dm, var=RFENDTC);

proc print data=outlib.dm(obs=10) label noobs;
  title "SDTM DM - first 10 records (synthetic data)";
run;
