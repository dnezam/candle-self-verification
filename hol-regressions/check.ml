(* Each check names a theorem the replay saved, its expected hypotheses and
   its expected conclusion, built here from Candle terms. The comment above
   each one gives that sequent in HOL notation and, where the sequent alone
   doesn't show it, what the fixture exercises; the fixtures' sources are
   in HOL's src/postkernel/prooftrace/tests. *)
let check_sequent name hs tm th =
  if length (hyp th) = length hs &&
     forall (fun h -> exists (aconv h) (hyp th)) hs &&
     aconv (concl th) tm then print_endline ("PFT_EXACT " ^ name)
  else failwith ("wrong sequent: " ^ name);;
let check_saved name hs tm = check_sequent name hs tm (load_th name);;
let check_refl name tm = check_saved name [] (mk_eq(tm,tm));;
let forall_bool v tm = mk_comb
  (inst [bool_ty,mk_vartype "'a"] (mk_const("!",[])),mk_abs(v,tm));;
let conj p q = mk_comb(mk_comb(mk_const("/\\",[]),p),q);;
let imp p q = mk_comb(mk_comb(mk_const("==>",[]),p),q);;

let check_export_results () =
  let x = mk_var("x",bool_ty) in
  let a = mk_const("pftExport_shadow$first",[]) in
  let b = mk_const("pftExport_shadow$second",[]) in
  (* |- first = first /\ (!x. x = x) /\ second = second: a specification
     whose inner binder shadows a witness variable *)
  check_saved "pftExport_shadow$SHADOW" []
    (conj (mk_eq(a,a)) (conj (forall_bool x (mk_eq(x,x))) (mk_eq(b,b))));
  (* |- T, from a specification whose constant doesn't occur in it;
     |- unused = unused for that constant *)
  check_saved "pftExport_vacuous$VACUOUS" [] (mk_const("T",[]));
  check_refl "pftExport_vacuous$UNUSED_REFL"
    (mk_const("pftExport_vacuous$unused",[]));
  let v = mk_var("pftExport_overlap$first",bool_ty) in
  let first = mk_const("pftExport_overlap$first",[]) in
  (* |- !first. first = first, where the bound variable has the new
     constant's full name and the body uses the constant *)
  check_saved "pftExport_overlap$OVERLAP" []
    (forall_bool v (mk_eq(first,first)));
  let p = mk_eq(x,x) in
  let check name = check_saved ("pftExport_hypotheses$" ^ name) in
  (* Each kernel rule must carry its premises' hypotheses into the result.
     With p = (x = x):
     CONJ_LEFT, CONJ_RIGHT: p |- p /\ p. The same sequent on purpose: one is
       CONJ (ASSUME p) (REFL x), the other CONJ (REFL x) (ASSUME p), so
       the hypothesis comes from the left premise in one, the right in the
       other. *)
  check "CONJ_LEFT" [p] (conj p p);
  check "CONJ_RIGHT" [p] (conj p p);
  let truth = mk_const("T",[]) in
  (* MP: T |- x = x. The implication is ADD_ASSUM T (DISCH T (REFL x)), that
     is T |- T ==> x = x, so the hypothesis T comes from the implication. *)
  check "MP" [truth] p;
  (* DISJ_CASES: p, p ==> p |- p; both hypotheses come from the disjunction,
     p |- p \/ p with p ==> p added by ADD_ASSUM, and neither from the cases *)
  check "DISJ_CASES" [p;imp p p] p;
  let y = mk_var("y",bool_ty) in
  (* CHOOSE: (!y. (\y. T) y ==> p) |- p; the hypothesis comes from the
     existential premise, added with ADD_ASSUM *)
  check "CHOOSE" [forall_bool y (imp (mk_comb(mk_abs(y,truth),y)) p)] p;
  (* |- LET (\x. T) = LET (\x. T), at LET : (bool -> bool) -> bool -> bool,
     from GEN_ABS with LET as the supplied binder constant *)
  let let_tm = inst [bool_ty,mk_vartype "'a";bool_ty,mk_vartype "'b"]
    (mk_const("LET",[])) in
  check_refl "pftExport_binder$LET" (mk_comb(let_tm,mk_abs(x,truth)));;

let check_oracle_results () =
  let v name = mk_var(name,bool_ty) in
  (* q, r |- p: an oracle theorem's hypotheses *)
  check_saved "oracle_hyps$hyps" [v "q";v "r"] (v "p");
  (* (\y. x = x') = (\y. x = x') |- p, with x' a free variable named
     x pft%0: the hypothesis's binder, renamed towards x, must capture
     neither free variable *)
  let lam = mk_abs(v "y",mk_eq(v "x",v "x pft%0")) in
  check_saved "oracle_hyps$capture" [mk_eq(lam,lam)] (v "p");
  (* |- c = c for c : 'a -> 'a at 'a = bool and at 'a = bool -> bool;
     then |- T = T, proved through instances of a constant that was deleted
     before the theorem was saved *)
  let c = mk_const("oracle_hyps$c",[]) in
  List.iter (fun (name,ty) ->
    check_refl ("oracle_hyps$" ^ name) (inst [ty,mk_vartype "'a"] c))
    ["POLY_BOOL",bool_ty; "POLY_FUN",mk_fun_ty bool_ty bool_ty];
  check_refl "oracle_retired_instance$RESULT" (mk_const("T",[]));;

let term_kind_check () =
  let f = mk_var("f",mk_fun_ty bool_ty bool_ty) in
  let x = mk_var("x",bool_ty) in
  let y = mk_var("y",bool_ty) in
  (* |- t = t for each t:
     RENAME: (\f. \f. x), from a proof that keeps the application f x
       reachable (through SUBST) while it shares its children with \f. x;
     SPEC: (\f. T), likewise for f T, through a specification;
     EMPTY_BINDER: (\x. \y. x) with both binders named "", a legal
       variable name *)
  List.iter (fun (name,tm) -> check_refl ("pft_term_kinds$" ^ name) tm)
    [("RENAME",mk_abs(f,mk_abs(f,x)));
     ("SPEC",mk_abs(f,mk_const("T",[])));
     ("EMPTY_BINDER",mk_abs(x,mk_abs(y,x)))];
  ignore (mk_mconst("pft_term_kinds$unused",bool_ty));;

let check_identity_results () =
  let n = mk_comb(mk_const("~",[]),mk_const("T",[])) in
  (* NEGATION: ~T |- ~T, from NOT_INTRO applied to ASSUME ~T, a negation
     rather than an implication to F;
     RESULT: |- !a. stream_abs (stream_rep a) = a, in a theory that also
     declares stream_abs' and stream_rep' and a retired type's renamed
     _abs/_rep constants, all clashing with the names synthesized for the
     bijections *)
  check_saved "identity_negation$NEGATION" [n] n;
  let stream = mk_type("identity_type_names$stream",[]) in
  let a = mk_var("a",stream) in
  let abs = mk_const("identity_type_names$stream_abs",[]) in
  let rep = mk_const("identity_type_names$stream_rep",[]) in
  let all = mk_mconst("!",mk_fun_ty (mk_fun_ty stream bool_ty) bool_ty) in
  check_saved "identity_type_names$RESULT" []
    (mk_comb(all,mk_abs(a,mk_eq(mk_comb(abs,mk_comb(rep,a)),a))));;

let check_compute_results () =
  let check name input result =
    check_saved ("pft_compute_binders$" ^ name) [] (mk_eq(input,result)) in
  let cv = mk_type ("cval",[]) in
  let num = mk_type ("num",[]) in
  let nn = mk_fun_ty num num in
  let zero = mk_mconst ("_0",num) in
  let bit name tm = mk_comb (mk_mconst(name,nn),tm) in
  let rec bits n =
    if n = 0 then zero
    else if n mod 2 = 1 then bit "BIT1" (bits (n / 2))
    else bit "BIT2" (bits ((n - 2) / 2)) in
  let numeral n =
    if n = 0 then zero else
    mk_comb (mk_mconst("NUMERAL",nn),bits n) in
  let cvnum n = mk_comb
    (mk_mconst("Cexp_num",mk_fun_ty num cv),numeral n) in
  let letc = mk_mconst("LET",mk_fun_ty (mk_fun_ty cv cv) (mk_fun_ty cv cv)) in
  let let_tm v body arg = mk_comb (mk_comb (letc,mk_abs(v,body)),arg) in
  let x = mk_var("x",cv) in
  let y = mk_var("y",cv) in
  let addc = mk_mconst("Cexp_add",mk_fun_ty cv (mk_fun_ty cv cv)) in
  let add a b = mk_comb(mk_comb(addc,a),b) in
  (* cv computations, with cv numerals written as numbers:
     CAPTURE: |- LET (\x. LET (\y. x + y) 4) 2 = 6, where HOL names both
       binders x though the inner body uses both, so emission must pick a
       fresh inner name;
     CLOSURE_NESTED: |- LET (\x. 4 + x) 2 = 6, built by beta-substituting
       4 beneath the binder;
     LARGE_NUMERAL: |- n = n for n = 2 ** 64, past the machine-word range;
     KIND_CAPTURE: |- (\f. \f. kind_x) = (\f. \f. kind_x), substituting
       \f. kind_x while the proof keeps f kind_x, which has the same
       children: capture analysis must not take one for the other *)
  let nested = let_tm x (let_tm y (add x y) (cvnum 4)) (cvnum 2) in
  check "CAPTURE" nested (cvnum 6);
  check "CLOSURE_NESTED"
    (let_tm x (add (cvnum 4) x) (cvnum 2)) (cvnum 6);
  let large = cvnum 18446744073709551616 in
  check "LARGE_NUMERAL" large large;
  let b = mk_type("bool",[]) in
  let f = mk_var("f",mk_fun_ty b b) in
  let v = mk_var("kind_x",b) in
  let abstraction = mk_abs(f,v) in
  let capture = mk_abs(f,abstraction) in
  check "KIND_CAPTURE" capture capture;;

(* Replay inputs relative to the fixture directory, in order: the logical
   prerequisites precede the fixtures; the computation ancestors precede the
   compute preamble and the computation fixture. *)
replay_all ["preamble.pft"; "bool.candle.pft"];;
replay_all ["oracle/oracle_hyps.candle.pft";
            "oracle/oracle_retired_instance.candle.pft"];;
check_oracle_results ();;
replay_all ["export/vacuous.candle.pft"; "export/shadow.candle.pft";
            "export/overlap.candle.pft"; "export/hypotheses.candle.pft";
            "export/binder.candle.pft"];;
check_export_results ();;
replay_all ["term-kind/term-kinds.candle.pft"];;
term_kind_check ();;
replay_all ["identity/identity_negation.candle.pft";
            "identity/identity_type_names.candle.pft"];;
check_identity_results ();;
replay_all ["marker.candle.pft"; "num.candle.pft"; "normalForms.candle.pft";
            "combin.candle.pft"; "boolSimpsContext.candle.pft";
            "sat.candle.pft"; "canonContext.candle.pft";
            "normalFormsContext.candle.pft"; "folToolsContext.candle.pft";
            "folMappingContext.candle.pft"; "mesonLibContext.candle.pft";
            "Canon_Port_Context.candle.pft";
            "InductiveDefinitionContext.candle.pft"; "relation.candle.pft";
            "prim_rec.candle.pft"; "quotient.candle.pft"; "pair.candle.pft";
            "arithmetic.candle.pft"; "sum.candle.pft"; "one.candle.pft";
            "option.candle.pft"; "While.candle.pft"; "numeral.candle.pft";
            "cv.candle.pft"; "compute-preamble.pft";
            "compute-binder/compute-binders.pft.bin"];;
check_compute_results ();;
print_endline "ALL_CANDLE_PASS";;
