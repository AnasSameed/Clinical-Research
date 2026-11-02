/*------------------------------------------------------------------
  qc_checks.sas  -  small reusable QC macros
  %check_unique(ds=, key=)   -> writes PASS/FAIL to the log if KEY is unique
  %check_missing(ds=, var=)  -> counts missing values of VAR
-------------------------------------------------------------------*/
%macro check_unique(ds=, key=);
  proc sort data=&ds. out=_chk_sorted nodupkey dupout=_chk_dups;
    by &key.;
  run;

  %local ndup;
  proc sql noprint;
    select count(*) into :ndup trimmed from _chk_dups;
  quit;

  %if &ndup. = 0 %then %put NOTE: [QC PASS] &ds. has unique &key..;
  %else %put WARNING: [QC FAIL] &ds. has &ndup. duplicate &key. record(s).;

  proc datasets lib=work nolist; delete _chk_sorted _chk_dups; quit;
%mend check_unique;

%macro check_missing(ds=, var=);
  %local nmiss;
  proc sql noprint;
    select count(*) into :nmiss trimmed from &ds. where missing(&var.);
  quit;
  %put NOTE: [QC INFO] &ds.: &nmiss. record(s) with missing &var..;
%mend check_missing;
