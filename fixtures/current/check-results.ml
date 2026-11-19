let check_current_saved name expected_hyps expected_concl =
  let th = load_th name in
  let subset xs ys = forall (fun x -> exists (aconv x) ys) xs in
  if not (subset expected_hyps (hyp th) && subset (hyp th) expected_hyps) then
    failwith ("CHECK_FAILED: hypotheses: " ^ name)
  else if not (aconv (concl th) expected_concl) then
    failwith ("CHECK_FAILED: conclusion: " ^ name)
  else print_endline ("CHECKED: " ^ name);;

let check_current_results () =
  let bool_ty = mk_type ("bool", []) in
  let var s = mk_var (s, bool_ty) in
  let truth = mk_mconst ("T", bool_ty) in
  let falsity = mk_mconst ("F", bool_ty) in
  let feature s = mk_mconst ("currentFeatures$" ^ s, bool_ty) in
  let conjunction a b =
    mk_comb (mk_comb (mk_mconst ("/\\", mk_fun_ty bool_ty (mk_fun_ty bool_ty bool_ty)), a), b) in
  let p = var "p" in
  let q = var "q" in
  let x = var "x" in
  let y = var "y" in
  let z = var "fresh" in
  let capture = mk_eq (mk_abs (z, y), mk_abs (z, y)) in
  let shadow = mk_abs (x, mk_abs (x, x)) in
  let swapped = conjunction y x in
  let tiny = mk_type ("currentFeatures$tiny", []) in
  let rep_ty = mk_fun_ty tiny bool_ty in
  let rep = mk_var ("rep", rep_ty) in
  let td = mk_mconst ("bool$TYPE_DEFINITION",
    mk_fun_ty (mk_fun_ty bool_ty bool_ty) (mk_fun_ty rep_ty bool_ty)) in
  let td_body = mk_comb (mk_comb (td, mk_abs (x, truth)), rep) in
  let tiny_expected = mk_comb
    (mk_mconst ("?", mk_fun_ty (mk_fun_ty rep_ty bool_ty) bool_ty),
     mk_abs (rep, td_body)) in
  check_current_saved "currentAnonB$original" [p; q] (conjunction p q);
  check_current_saved "currentAnonB$cross_anon" [p; q] q;
  check_current_saved "currentFeatures$tiny_type" [] tiny_expected;
  check_current_saved "currentFeatures$pair_spec" []
    (conjunction (mk_eq (feature "left", truth)) (mk_eq (feature "right", falsity)));
  check_current_saved "currentFeatures$pair_def" []
    (conjunction (mk_eq (feature "first", truth)) (mk_eq (feature "second", falsity)));
  check_current_saved "currentFeatures$capture" [capture] capture;
  check_current_saved "currentFeatures$shadow" [] (mk_eq (shadow, shadow));
  check_current_saved "currentFeatures$gen_abs_none" []
    (mk_eq (mk_abs (x, x), mk_abs (x, x)));
  check_current_saved "currentFeatures$simultaneous" [swapped] swapped;
  check_current_saved "currentFeatures$marked" [p] p;
  let num_ty = mk_type ("num", []) in
  let cv_ty = mk_type ("cval", []) in
  let num_to_num = mk_fun_ty num_ty num_ty in
  let zero = mk_mconst ("_0", num_ty) in
  let numeral n = mk_comb (mk_mconst ("NUMERAL", num_to_num), n) in
  let bit name n = mk_comb (mk_mconst (name, num_to_num), n) in
  let two = numeral (bit "BIT2" zero) in
  let three = numeral (bit "BIT1" (bit "BIT1" zero)) in
  let five = numeral (bit "BIT1" (bit "BIT2" zero)) in
  let cv_num n = mk_comb (mk_mconst ("Cexp_num", mk_fun_ty num_ty cv_ty), n) in
  let add = mk_mconst ("Cexp_add", mk_fun_ty cv_ty (mk_fun_ty cv_ty cv_ty)) in
  check_current_saved "currentCompute$add" []
    (mk_eq (mk_comb (mk_comb (add, cv_num two), cv_num three), cv_num five));
  print_endline "CURRENT_ALL_CHECKS_PASSED";;

let check_current_anonymous () =
  let bool_ty = mk_type ("bool", []) in
  let p = mk_var ("p", bool_ty) in
  let q = mk_var ("q", bool_ty) in
  let conjunction = mk_mconst ("/\\", mk_fun_ty bool_ty (mk_fun_ty bool_ty bool_ty)) in
  check_current_saved "currentAnonA#0" [p; q]
    (mk_comb (mk_comb (conjunction, p), q));;
