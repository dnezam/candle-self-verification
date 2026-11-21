(* Load ProofTraceParser before this file, then pass the raw .hol/objs directory. *)
fun audit_current_raw dir = let
  open ProofTraceParser
  fun parse_theory name = let
    val (root, heap) = parse (OS.Path.concat (dir, name ^ "Theory.tr.gz"))
  in (heap, shRoot heap root) end
  fun proof heap th = let val (_, _, p) = shThm heap th in shProof heap p end
  fun unwrap heap th = case proof heap th of
      save_dep_prf inner => unwrap heap inner
    | p => p
  fun named heap all_thms name =
    case List.find (fn (n, _) => n = name)
      (list heap (tuple3 heap (str heap, fn p => p, shThmInfo heap)) all_thms) of
        SOME (_, (th, _)) => th
      | NONE => raise Fail ("raw fixture missing theorem: " ^ name)
  val (ha, a) = parse_theory "currentAnonA"
  val anonymous = list ha (fn p => p) (#anon_thms a)
  val _ = case anonymous of
      [th] => (case unwrap ha th of
          CONJ_prf (left, right) =>
            (case (unwrap ha left, unwrap ha right) of
                (ASSUME_prf _, ASSUME_prf _) => ()
              | _ => raise Fail "raw anonymous theorem must conjoin assumptions")
        | _ => raise Fail "raw anonymous theorem must be CONJ")
    | _ => raise Fail "raw fixture must contain exactly one anonymous theorem"
  val (hb, b) = parse_theory "currentAnonB"
  val _ = case unwrap hb (named hb (#all_thms b) "original") of
      Disk_prf ("currentAnonA", id) =>
        (case thmId hb id of Thm.SavedAnon 0 => ()
          | _ => raise Fail "raw fixture must load anonymous theorem zero")
    | _ => raise Fail "raw original must be a cross-theory disk dependency"
  val (hf, f) = parse_theory "currentFeatures"
  val _ = case unwrap hf (named hf (#all_thms f) "marked") of
      Mark_prf ("outer current fixture", inner) =>
        (case unwrap hf inner of
            Mark_prf ("inner current fixture", _) => ()
          | _ => raise Fail "raw fixture missing inner Mark wrapper")
    | _ => raise Fail "raw fixture missing outer Mark wrapper"
  val _ = case unwrap hf (named hf (#all_thms f) "pair_spec") of
      Def_spec_prf (_, names) =>
        if length (list hf (fn p => p) names) = 2 then ()
        else raise Fail "raw specification must define two constants"
    | _ => raise Fail "raw fixture missing Def_spec"
  val _ = case unwrap hf (named hf (#all_thms f) "pair_def") of
      Def_const_list_prf (_, names) =>
        if length (list hf (fn p => p) names) = 2 then ()
        else raise Fail "raw definition must define two constants"
    | _ => raise Fail "raw fixture missing Def_const_list"
  val _ = case unwrap hf (named hf (#all_thms f) "tiny_type") of
      Def_tyop_prf _ => ()
    | _ => raise Fail "raw fixture missing Def_tyop"
  val _ = case unwrap hf (named hf (#all_thms f) "gen_abs_none") of
      GEN_ABS_prf (opt, _, _) =>
        (case option hf (fn p => p) opt of NONE => ()
          | SOME _ => raise Fail "raw GEN_ABS fixture must use NONE")
    | _ => raise Fail "raw fixture missing GEN_ABS NONE"
  val (hc, c) = parse_theory "currentCompute"
  val _ = case unwrap hc (named hc (#all_thms c) "add") of
      compute_prf _ => ()
    | _ => raise Fail "raw fixture missing compute"
in print "CURRENT_RAW_AUDIT_PASSED\n" end;
