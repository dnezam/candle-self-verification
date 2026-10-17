val _ = app load ["DArray", "PIntMap", "RawTheory_dtype"];
val pft_dir = OS.Path.concat (Globals.HOLDIR, "src/postkernel/prooftrace");
fun pft_use file = PolyML.use (OS.Path.concat (pft_dir, file));
val _ = app (fn name => (pft_use (name ^ ".sig"); pft_use (name ^ ".sml")))
  ["ProofTraceParser", "ProofTraceWalk", "ProofTraceReplay", "PFTOpcodes",
   "PFTWriter", "IntPairTable", "PFTCandleComputePreamble", "PFTEmit",
   "PFTCandlePreamble"];
val _ = PolyML.use "raw-manifest.sml";
val _ = PFTEmit.emit_expect := true;
val _ = PFTCandlePreamble.emit {output="candle-preamble.pft.bin",binary=true};
val visited = ref ["min"];
val order = TextIO.openOut "replay-order.txt";
val _ = TextIO.output (order,"candle-preamble.pft.bin\n");
fun visit name = if List.exists (fn n => n=name) (!visited) then () else let
  val path = case List.find (fn (n,_) => n=name) traces of
     SOME (_,p) => p | NONE => raise Fail ("missing raw trace: " ^ name)
  val (root,heap) = ProofTraceParser.parse path
  val info = ProofTraceParser.shRoot heap root
  val parents = ProofTraceParser.list heap
    (ProofTraceParser.tuple2 heap
      (ProofTraceParser.str heap, ProofTraceParser.str heap)) (#parents info)
  val _ = List.app (visit o #1) parents
  val output = name ^ ".candle.pft.bin"
  val _ = print ("Converting " ^ name ^ "\n")
  val _ = TextIO.flushOut TextIO.stdOut
  val _ = PFTEmit.emit_theory
    {trace=path,output=output,binary=true,ruleset=PFTEmit.Candle}
  val _ = TextIO.output (order,output ^ "\n")
  val _ = visited := name :: !visited
in () end;
val _ = List.app visit ["bool","marker","smallCompute"];
val _ = TextIO.closeOut order;
val _ = print "PINNED_CONVERSION_COMPLETE\n";
