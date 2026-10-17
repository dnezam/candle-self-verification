let check_saved name expected =
  let th = load_th name in
  if (match hyp th with [] -> false | _ -> true) then
    failwith ("CHECK_FAILED: hypotheses: " ^ name)
  else if not (aconv (concl th) expected) then
    failwith ("CHECK_FAILED: conclusion: " ^ name)
  else print_endline ("CHECKED: " ^ name);;

let check_results () =
  let bool_ty = mk_type ("bool", []) in
  let a_ty = mk_vartype "'a" in
  let x = mk_var ("x", a_ty) in
  let marker = mk_mconst ("marker$stmarker", mk_fun_ty a_ty a_ty) in
  let expected_marker =
    mk_comb (mk_mconst ("!", mk_fun_ty (mk_fun_ty a_ty bool_ty) bool_ty),
             mk_abs (x, mk_eq (mk_comb (marker, x), x))) in
  check_saved "candle$TRUTH" (mk_mconst ("T", bool_ty));
  check_saved "bool$TRUTH" (mk_mconst ("T", bool_ty));
  check_saved "marker$stmarker_def" expected_marker;
  let num_ty = mk_type ("num", []) in
  let cval_ty = mk_type ("cval", []) in
  let num_to_num = mk_fun_ty num_ty num_ty in
  let numeral n = mk_comb (mk_mconst ("NUMERAL", num_to_num), n) in
  let bit name n = mk_comb (mk_mconst (name, num_to_num), n) in
  let n0 = mk_mconst ("_0", num_ty) in
  let n2 = numeral (bit "BIT2" n0) in
  let n3 = numeral (bit "BIT1" (bit "BIT1" n0)) in
  let n5 = numeral (bit "BIT1" (bit "BIT2" n0)) in
  let cexp_num n = mk_comb (mk_mconst ("Cexp_num", mk_fun_ty num_ty cval_ty), n) in
  let cexp_add = mk_mconst ("Cexp_add", mk_fun_ty cval_ty (mk_fun_ty cval_ty cval_ty)) in
  let add_exp = mk_comb (mk_comb (cexp_add, cexp_num n2), cexp_num n3) in
  let expected_compute = mk_eq (add_exp, cexp_num n5) in
  check_saved "smallCompute$add" expected_compute;
  print_endline "ALL_CHECKS_PASSED";;

