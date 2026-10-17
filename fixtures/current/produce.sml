val _ = load "boolLib";
open HolKernel Parse boolLib;

fun fixture_check name expected_hyps expected_concl th =
  if not (aconv (concl th) expected_concl) then
    raise Fail ("fixture conclusion: " ^ name)
  else if length (hyp th) <> length expected_hyps orelse
          not (List.all (fn h => List.exists (aconv h) (hyp th)) expected_hyps)
  then raise Fail ("fixture hypotheses: " ^ name)
  else print ("PRODUCED: " ^ name ^ "\n");

val _ = new_theory "currentAnonA";
val p = mk_var ("p", bool);
val q = mk_var ("q", bool);
val anonymous = CONJ (ASSUME p) (ASSUME q);
val anon_data = ThyDataSexp.new
  {thydataty = "current_fixture_anon", merge = ThyDataSexp.append_merge,
   load = fn _ => (), other_tds = fn (data, _) => SOME data};
val _ = #set anon_data (ThyDataSexp.List [ThyDataSexp.Thm anonymous]);
val _ = export_theory ();

val _ = new_theory "currentAnonB";
(* Use the same disk theorem operation as persistent theory-data loading. *)
val anonymous_loaded = Thm.disk_thm
  ("currentAnonA", Thm.SavedAnon 0)
  (((("currentAnonA", 0), []), []), [mk_conj (p, q), p, q]);
val _ = fixture_check "currentAnonB$original" [p, q]
  (mk_conj (p, q)) anonymous_loaded;
val _ = save_thm ("original", anonymous_loaded);
val cross_anon = CONJUNCT2 anonymous_loaded;
val _ = fixture_check "currentAnonB$cross_anon" [p, q] q cross_anon;
val _ = save_thm ("cross_anon", cross_anon);
val _ = export_theory ();

val _ = new_theory "currentFeatures";
val _ = fixture_check "currentAnonA#0" [p, q] (mk_conj (p, q)) anonymous;
val b = mk_var ("b", bool);
val pred = mk_abs (b, T);
val nonempty = EXISTS (mk_exists (b, mk_comb (pred, b)), T)
  (EQ_MP (SYM (BETA_CONV (mk_comb (pred, T)))) TRUTH);
val tiny_type = new_type_definition ("tiny", nonempty);
val _ = save_thm ("tiny_type", tiny_type);

val left = mk_var ("left", bool);
val right = mk_var ("right", bool);
val pair_body = mk_conj (mk_eq (left, T), mk_eq (right, F));
val pair_witness = EXISTS
  (mk_exists (left, mk_exists (right, pair_body)), T)
  (EXISTS (mk_exists (right, subst [left |-> T] pair_body), F)
    (CONJ (REFL T) (REFL F)));
val pair_spec = new_specification
  ("pair_spec", ["left", "right"], pair_witness);

val first = mk_var ("first", bool);
val second = mk_var ("second", bool);
val pair_def = Theory.Definition.gen_new_specification
  ("pair_def", CONJ (ASSUME (mk_eq (first, T)))
                    (ASSUME (mk_eq (second, F))));

val x = mk_var ("x", bool);
val y = mk_var ("y", bool);
val z = mk_var ("z", bool);
val capture_input = mk_eq (mk_abs (y, x), mk_abs (y, x));
val capture = INST [x |-> y] (ASSUME capture_input);
val capture_expected = mk_eq (mk_abs (z, y), mk_abs (z, y));
val _ = fixture_check "currentFeatures$capture" [capture_expected]
  capture_expected capture;
val _ = save_thm ("capture", capture);
val shadow_tm = mk_abs (x, mk_abs (x, x));
val shadow_expected = mk_eq (shadow_tm, shadow_tm);
val shadow = INST [x |-> y] (REFL shadow_tm);
val _ = fixture_check "currentFeatures$shadow" [] shadow_expected shadow;
val _ = save_thm ("shadow", shadow);
val gen_abs_none = Thm.GEN_ABS NONE [x] (REFL x);
val _ = fixture_check "currentFeatures$gen_abs_none" []
  (mk_eq (mk_abs (x, x), mk_abs (x, x))) gen_abs_none;
val _ = save_thm ("gen_abs_none", gen_abs_none);
val simultaneous_input = mk_conj (x, y);
val simultaneous_expected = mk_conj (y, x);
val simultaneous = INST [x |-> y, y |-> x] (ASSUME simultaneous_input);
val _ = fixture_check "currentFeatures$simultaneous" [simultaneous_expected]
  simultaneous_expected simultaneous;
val _ = save_thm ("simultaneous", simultaneous);
val marked = Thm.mark "outer current fixture"
  (Thm.mark "inner current fixture" (ASSUME p));
val _ = fixture_check "currentFeatures$marked" [p] p marked;
val _ = save_thm ("marked", marked);
val _ = export_theory ();
val _ = print "CURRENT_CORE_PRODUCED\n";

val _ = load "cv_computeLib";
val _ = new_theory "currentCompute";
val add = cv_computeLib.cv_compute []
  (Parse.Term [QUOTE "cv_add (cv$Num 2) (cv$Num 3)"]);
val _ = fixture_check "currentCompute$add" []
  (Parse.Term [QUOTE "cv_add (cv$Num 2) (cv$Num 3) = cv$Num 5"]) add;
val _ = save_thm ("add", add);
val _ = export_theory ();
val _ = print "CURRENT_FIXTURES_PRODUCED\n";
