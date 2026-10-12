/*------------------------------------------------------------------
  00_setup.sas  -  run this first
  1. EDIT the path below so it points to the folder holding this project.
  2. It loads the QC macros and creates a permanent library for output.
-------------------------------------------------------------------*/
%let root = /home/your_user/clinical-sas-practice;   /* <-- EDIT ME */

options dlcreatedir;                                  /* creates the output folder if it is missing */
libname outlib "&root./output";
%include "&root./macros/qc_checks.sas";

options nodate nonumber;
