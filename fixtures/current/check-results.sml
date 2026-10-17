fun current_expected_sequents () = let
  open Lib Type Term
  infixr 3 -->
  val bool_ty = Type.bool
  fun var s = mk_var (s, bool_ty)
  fun constant thy name ty = mk_thy_const {Thy = thy, Name = name, Ty = ty}
  fun equality (left, right) = let
    val ty = type_of left
  in list_mk_comb (constant "min" "=" (ty --> ty --> bool_ty), [left, right]) end
  fun conjunction (left, right) = list_mk_comb
    (constant "bool" "/\\" (bool_ty --> bool_ty --> bool_ty), [left, right])
  fun existential (v, body) = mk_comb
    (constant "bool" "?" ((type_of v --> bool_ty) --> bool_ty), mk_abs (v, body))
  fun feature name = constant "currentFeatures" name bool_ty
  val truth = constant "bool" "T" bool_ty
  val falsity = constant "bool" "F" bool_ty
  val p = var "p"
  val q = var "q"
  val x = var "x"
  val y = var "y"
  val z = var "fresh"
  val capture = equality (mk_abs (z, y), mk_abs (z, y))
  val shadow = mk_abs (x, mk_abs (x, x))
  val swapped = conjunction (y, x)
  val tiny = mk_thy_type {Thy = "currentFeatures", Tyop = "tiny", Args = []}
  val rep = mk_var ("rep", tiny --> bool_ty)
  val td = constant "bool" "TYPE_DEFINITION"
    ((bool_ty --> bool_ty) --> (tiny --> bool_ty) --> bool_ty)
  val tiny_expected = existential
    (rep, list_mk_comb (td, [mk_abs (x, truth), rep]))
  val num_ty = mk_thy_type {Thy = "num", Tyop = "num", Args = []}
  val cv_ty = mk_thy_type {Thy = "cv", Tyop = "cv", Args = []}
  val zero = constant "arithmetic" "ZERO" num_ty
  fun numeral n = mk_comb (constant "arithmetic" "NUMERAL" (num_ty --> num_ty), n)
  fun bit name n = mk_comb (constant "arithmetic" name (num_ty --> num_ty), n)
  val two = numeral (bit "BIT2" zero)
  val three = numeral (bit "BIT1" (bit "BIT1" zero))
  val five = numeral (bit "BIT1" (bit "BIT2" zero))
  fun cv_num n = mk_comb (constant "cv" "Num" (num_ty --> cv_ty), n)
  val add = constant "cv" "cv_add" (cv_ty --> cv_ty --> cv_ty)
in
  [("currentAnonB$original", [p, q], conjunction (p, q)),
   ("currentAnonB$cross_anon", [p, q], q),
   ("currentFeatures$tiny_type", [], tiny_expected),
   ("currentFeatures$pair_spec", [], conjunction
      (equality (feature "left", truth),
       equality (feature "right", falsity))),
   ("currentFeatures$pair_def", [], conjunction
      (equality (feature "first", truth),
       equality (feature "second", falsity))),
   ("currentFeatures$capture", [capture], capture),
   ("currentFeatures$shadow", [], equality (shadow, shadow)),
   ("currentFeatures$gen_abs_none", [], equality (mk_abs (x, x), mk_abs (x, x))),
   ("currentFeatures$simultaneous", [swapped], swapped),
   ("currentFeatures$marked", [p], p),
   ("currentCompute$add", [], equality
      (list_mk_comb (add, [cv_num two, cv_num three]), cv_num five))]
end;

fun check_current_sequent db (name, expected_hyps, expected_concl) = let
    val th = case PFTReplay.lookup db name of
        SOME th => th
      | NONE => raise Fail ("CHECK_FAILED: missing target: " ^ name)
    val actual_hyps = Thm.hyp th
    fun subset xs ys = List.all (fn x => List.exists (Term.aconv x) ys) xs
  in
    if not (subset expected_hyps actual_hyps andalso
            subset actual_hyps expected_hyps)
    then raise Fail ("CHECK_FAILED: hypotheses: " ^ name)
    else if not (Term.aconv (Thm.concl th) expected_concl)
    then raise Fail ("CHECK_FAILED: conclusion: " ^ name)
    else print ("CHECKED: " ^ name ^ "\n")
end;

fun check_current_results db =
  (List.app (check_current_sequent db) (current_expected_sequents ());
   print "CURRENT_ALL_CHECKS_PASSED\n");

fun check_current_anonymous db =
  case List.find (fn (name, _, _) => name = "currentAnonB$original")
    (current_expected_sequents ()) of
      SOME (_, hyps, conclusion) =>
        check_current_sequent db ("currentAnonA#0", hyps, conclusion)
    | NONE => raise Fail "missing anonymous fixture expectation";
