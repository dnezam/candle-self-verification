val _ = load "cv_computeLib";
open HolKernel Parse boolLib;
val _ = new_theory "smallCompute";
val add = cv_computeLib.cv_compute [] ``cv_add (cv$Num 2) (cv$Num 3)``;
val _ = if null (hyp add) andalso
           aconv (concl add) ``cv_add (cv$Num 2) (cv$Num 3) = cv$Num 5``
        then () else raise Fail "unexpected compute sequent";
val _ = save_thm ("add", add);
val _ = export_theory ();
val _ = print "PINNED_COMPUTE_PRODUCED\n";
