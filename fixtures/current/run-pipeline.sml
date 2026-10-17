val _ = app load ["DArray", "PIntMap", "RawTheory_dtype"];
val pft_dir = OS.Path.concat (pipeline_converter, "src/postkernel/prooftrace");
fun pft_use file = PolyML.use (OS.Path.concat (pft_dir, file));
val _ = app (fn name => (pft_use (name ^ ".sig"); pft_use (name ^ ".sml")))
  ["ProofTraceParser", "ProofTraceWalk", "PFTOpcodes", "PFTWriter",
   "IntPairTable", "PFTCandleComputePreamble", "PFTEmit", "PFTCandlePreamble",
   "PFTReader", "PFTMerge"];
val _ = use (OS.Path.concat (pipeline_fixtures, "audit-raw.sml"));
val _ = audit_current_raw
  (OS.Path.concat (pipeline_build, "traces/raw/.hol/objs"));
val visited = ref ["min"];
val ordered = ref ([] : (string * string) list);
fun visit name =
  if List.exists (fn n => n = name) (!visited) then () else let
    val path = case List.find (fn (n, _) => n = name) pipeline_traces of
        SOME (_, p) => p
      | NONE => raise Fail ("missing raw theory: " ^ name)
    val (root, heap) = ProofTraceParser.parse path
    val info = ProofTraceParser.shRoot heap root
    val parents = ProofTraceParser.list heap
      (ProofTraceParser.tuple2 heap
        (ProofTraceParser.str heap, ProofTraceParser.str heap)) (#parents info)
    val _ = List.app (visit o #1) parents
    val _ = visited := name :: !visited
  in ordered := !ordered @ [(name, path)] end;
val _ = List.app visit
  ["currentAnonA", "currentAnonB", "currentFeatures", "currentCompute"];
val raw_order = TextIO.openOut (OS.Path.concat (pipeline_build, "raw-order.txt"));
val _ = List.app (fn (name, path) =>
  TextIO.output (raw_order, name ^ "\t" ^ path ^ "\n")) (!ordered);
val _ = TextIO.closeOut raw_order;
val _ = PFTEmit.emit_expect := false;
fun inventory file = let
  val {ruleset, ...} = PFTReader.read_header {file = file, binary = true}
  val descs = PFTOpcodes.descs_for_ruleset ruleset
  val counts = ref ([] : (string * int) list)
  val axioms = ref ([] : string option list)
  fun count name =
    case List.find (fn (n, _) => n = name) (!counts) of
        NONE => counts := !counts @ [(name, 1)]
      | SOME _ => counts := List.map
          (fn (n, total) => (n, if n = name then total + 1 else total)) (!counts)
  fun command name _ = count name
  val format : PFTReader.format_handler = {
    tyvar = command "TYVAR", tyop = command "TYOP", var = command "VAR",
    const = command "CONST", comb = command "COMB", abs = command "ABS",
    new_const = command "NEW_CONST", new_type = command "NEW_TYPE",
    axiom = fn (_, _, name) => (count "AXIOM"; axioms := name :: !axioms),
    save = command "SAVE", load = command "LOAD", del = command "DEL",
    del_range = command "DEL_RANGE"}
  fun specific opcode reader = let
    val desc = PFTOpcodes.lookup_desc descs opcode
    val _ = #readVarint reader ()
    val _ = PFTReader.read_raw_args desc reader
  in count (#tag desc) end
  val _ = PFTReader.read {file = file, binary = true,
    format_handler = format, ruleset_handler = specific}
  val out = TextIO.openOut (file ^ ".inventory")
  val _ = TextIO.output (out, "RULESET\t" ^ ruleset ^ "\n")
  val _ = List.app (fn (name, total) => TextIO.output
    (out, "COMMAND\t" ^ name ^ "\t" ^ Int.toString total ^ "\n")) (!counts)
  val _ = List.app (fn name => TextIO.output (out,
    "AXIOM\t" ^ (case name of SOME n => "NAMED\t" ^ n | NONE => "UNNAMED") ^ "\n"))
    (rev (!axioms))
in TextIO.closeOut out end;

fun emit ruleset subdir = let
  val dir = OS.Path.concat (pipeline_build, subdir)
  val candle = case ruleset of PFTEmit.Candle => true | _ => false
  val paths = ref ([] : string list)
  fun output name = OS.Path.concat (dir, name ^ ".pft.bin")
  fun add path = paths := !paths @ [path]
  val _ = if candle then
    (PFTCandlePreamble.emit {output = output "preamble", binary = true};
     add (output "preamble")) else ()
  fun one (name, path) = let
    val _ = print ("CONVERTING: " ^ subdir ^ "/" ^ name ^ "\n")
    val _ = TextIO.flushOut TextIO.stdOut
    val _ = PFTEmit.emit_theory
      {trace = path, output = output name, binary = true, ruleset = ruleset}
    val _ = add (output name)
  in
    if candle andalso name = "cv" then
      (PFTCandleComputePreamble.emit_file
        {output = output "compute-preamble", binary = true};
       add (output "compute-preamble")) else ()
  end
  val _ = List.app one (!ordered)
  val order = TextIO.openOut (OS.Path.concat (dir, "order.txt"))
  val _ = List.app (fn path => TextIO.output (order, path ^ "\n")) (!paths)
  val _ = TextIO.closeOut order
  val targets = List.map (fn (thy, name) => PFTMerge.ThyThm (thy, name, false))
    pipeline_targets
  val _ = PFTMerge.merge {inputs = !paths, targets = targets,
    output = output "merged", binary = true}
  val _ = List.app inventory (!paths @ [output "merged"])
in () end;
val _ = emit PFTEmit.HOL4 "hol4";
val _ = emit PFTEmit.Candle "candle";
val _ = print "CURRENT_CONVERSION_AND_MERGE_PASSED\n";
