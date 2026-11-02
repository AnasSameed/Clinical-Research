/*------------------------------------------------------------------
  02_adsl.sas  -  build a simplified ADaM ADSL (Subject-Level Analysis Dataset)
  Input : outlib.dm
  Output: outlib.adsl
-------------------------------------------------------------------*/
/* Run 00_setup.sas first, in the same SAS session, so the macro variable ROOT and the library OUTLIB exist. */

data outlib.adsl;
  length TRT01P $20 AGEGR1 $5 SAFFL $1;
  set outlib.dm;

  /* planned treatment */
  TRT01P = ARM;
  select (ARMCD);
    when ("PBO")   TRT01PN = 1;
    when ("TRT10") TRT01PN = 2;
    otherwise      TRT01PN = .;
  end;

  /* numeric treatment dates from ISO character dates (?? hides notes for blanks) */
  TRTSDT = input(RFSTDTC, ?? yymmdd10.);
  TRTEDT = input(RFENDTC, ?? yymmdd10.);
  format TRTSDT TRTEDT date9.;

  /* safety population = received at least one dose */
  if not missing(TRTSDT) then SAFFL = "Y";
  else SAFFL = "N";

  /* age group */
  if      AGE >= 65 then AGEGR1 = ">=65";
  else if AGE >= 18 then AGEGR1 = "<65";

  /* treatment duration in days (inclusive); stays missing if a date is missing */
  if not missing(TRTSDT) and not missing(TRTEDT) then TRTDURD = TRTEDT - TRTSDT + 1;

  label TRT01P="Planned Treatment for Period 01" TRT01PN="Planned Treatment for Period 01 (N)"
        TRTSDT="Date of First Exposure to Treatment" TRTEDT="Date of Last Exposure to Treatment"
        SAFFL="Safety Population Flag" AGEGR1="Pooled Age Group 1"
        TRTDURD="Total Treatment Duration (Days)";
run;

%check_unique(ds=outlib.adsl, key=USUBJID);
%check_missing(ds=outlib.adsl, var=TRTSDT);
%check_missing(ds=outlib.adsl, var=TRTEDT);   /* expect 2 screen failures + 1 dosed subject with no last-dose date */

proc freq data=outlib.adsl;
  tables TRT01P*SAFFL / nocol nopercent;
  title "ADSL - subjects by planned treatment and safety flag";
run;

proc means data=outlib.adsl n mean std min max maxdec=1;
  where SAFFL = "Y";
  class TRT01P;
  var AGE TRTDURD;
  title "ADSL - age and treatment duration, safety population";
run;
