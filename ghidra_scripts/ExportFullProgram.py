# Export entire program: for each function, ASM listing (with comments/labels) + decompiled C code below it.
# PLUS: after all functions, exports every remaining defined byte range in memory that is NOT covered
# by any function body (data blobs, pointer tables like the one at 0x080010a0, unanalyzed islands).
# This fixes the "where are my 50k lines" problem: the original version only walked the FunctionManager,
# so anything Ghidra didn't turn into a function (or data) silently vanished from the export.
# @author YourName
# @category Export
# @keybinding Ctrl+Shift+P
# @menupath Tools.Export.Export Full Program with Decompilation
# @runtime Jython

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.listing import CommentType, Instruction, Data
from ghidra.program.model.mem import MemoryAccessException

def getTModeRegister(program):
    for name in ["TMode", "TBIT", "TB", "tbit", "Tmode"]:
        r = program.getRegister(name)
        if r is not None:
            return r
    return None

def getInstructionMode(instr, tmode_reg):
    if tmode_reg is None:
        return "?"
    try:
        ctx = instr.getInstructionContext()
        val = ctx.getRegisterValue(tmode_reg)
        if val is not None and val.getUnsignedValue() == 1:
            return "T"
        return "A"
    except:
        return "?"

def bytesToHex(b):
    if b is None:
        return ""
    return " ".join(["%02x" % (x & 0xff) for x in b])

def safeStr(s):
    if s is None:
        return ""
    return s.replace("\n", " | ").replace("\r", "")

def formatInstruction(instr, tmode_reg):
    mode = getInstructionMode(instr, tmode_reg)
    length = instr.getLength()
    tag = "[%s%d]" % (mode, length)
    line = "%s  %s  %-30s  %s" % (
        instr.getAddress().toString(),
        tag,
        bytesToHex(instr.getBytes()),
        instr.toString()
    )
    eol = instr.getComment(CommentType.EOL)
    if eol:
        line += "   ; " + safeStr(eol)
    syms = instr.getSymbols()
    if len(syms) > 0:
        line += "   ; " + ", ".join([s.getName() for s in syms])
    return line

def getFunctionMode(func, listing, tmode_reg):
    instr = listing.getInstructionAt(func.getEntryPoint())
    if instr is None:
        return "?"
    return getInstructionMode(instr, tmode_reg)

def exportFunction(out, func, listing, decompiler, monitor, tmode_reg):
    entry = func.getEntryPoint()
    name = func.getName()
    try:
        sig = func.getPrototypeString(False, False)
    except:
        sig = "(signature unavailable)"

    mode = getFunctionMode(func, listing, tmode_reg)
    mode_name = {"T": "THUMB", "A": "ARM", "?": "UNKNOWN"}[mode]

    out.write("\n\n" + "=" * 100 + "\n")
    out.write("FUNCTION:  %s\n" % name)
    out.write("Entry:     %s\n" % entry)
    out.write("Mode:      %s\n" % mode_name)
    out.write("Signature: %s\n" % sig)
    out.write("-" * 100 + "\n")

    body = func.getBody()
    addrIter = body.getAddresses(True)
    while addrIter.hasNext():
        addr = addrIter.next()
        cu = listing.getCodeUnitAt(addr)
        if cu is None:
            continue

        plate = cu.getComment(CommentType.PLATE)
        if plate:
            out.write("; " + safeStr(plate) + "\n")
        pre = cu.getComment(CommentType.PRE)
        if pre:
            out.write("; " + safeStr(pre) + "\n")

        if isinstance(cu, Instruction):
            out.write(formatInstruction(cu, tmode_reg) + "\n")
        elif isinstance(cu, Data):
            out.write("%s  (data)  %s\n" % (addr, cu.toString()))

    out.write("\n; --- DECOMPILED C ---\n")
    try:
        result = decompiler.decompileFunction(func, 60, monitor)
        if result and result.decompileCompleted():
            c = result.getDecompiledFunction().getC()
            out.write(c)
            if not c.endswith("\n"):
                out.write("\n")
        else:
            out.write("// Decompilation did not complete\n")
    except Exception as e:
        out.write("// Decompilation error: %s\n" % str(e))

def collectCoveredRanges(program):
    """All address ranges already exported via function bodies."""
    fm = program.getFunctionManager()
    covered = []
    for func in fm.getFunctions(True):
        for rng in func.getBody().getRanges(True):
            covered.append((rng.getMinAddress(), rng.getMaxAddress()))
    covered.sort(key=lambda r: r[0].getOffset())
    return covered

def uncovered_ranges(program, covered):
    """Memory byte ranges not touched by any function body."""
    mem = program.getMemory()
    result = []
    for block in mem.getBlocks():
        if not block.isInitialized():
            continue
        start = block.getStartAddress()
        end = block.getEndAddress()
        # subtract covered ranges from [start..end]
        pieces = [(start, end)]
        for cmin, cmax in covered:
            newpieces = []
            for pmin, pmax in pieces:
                # cut [cmin..cmax] out of [pmin..pmax]
                if cmax < pmin or cmin > pmax:
                    newpieces.append((pmin, pmax))
                    continue
                if cmin > pmin:
                    newpieces.append((pmin, cmin.prev()))
                if cmax < pmax:
                    newpieces.append((cmax.next(), pmax))
            pieces = newpieces
        result.extend(pieces)
    return result

def exportUncoveredData(out, program, covered):
    listing = program.getListing()
    mem = program.getMemory()
    ranges = uncovered_ranges(program, covered)
    total = 0
    out.write("\n\n" + "=" * 100 + "\n")
    out.write("UNCOVERED RANGES (not part of any function body)\n")
    out.write("=" * 100 + "\n")
    for rmin, rmax in ranges:
        size = rmax.getOffset() - rmin.getOffset() + 1
        if size <= 0:
            continue
        out.write("\n--- RANGE %s .. %s (%d bytes) ---\n" % (rmin, rmax, size))
        addr = rmin
        while addr is not None and addr.compareTo(rmax) <= 0:
            cu = listing.getCodeUnitAt(addr)
            nxt = addr.add(16)
            if cu is None:
                # raw bytes, 16 per line
                chunk = []
                a = addr
                while a is not None and a.compareTo(rmax) <= 0 and len(chunk) < 16:
                    try:
                        chunk.append(mem.getByte(a) & 0xff)
                    except MemoryAccessException:
                        chunk.append(None)
                    a = a.next()
                hexpart = " ".join(["%02x" % b if b is not None else "--" for b in chunk])
                asciipart = "".join([chr(b) if b is not None and 32 <= b < 127 else "." for b in chunk])
                out.write("%s  %s   %s\n" % (addr.toString(), hexpart.ljust(47), asciipart))
                addr = nxt if nxt.compareTo(rmax) <= 0 else None
            elif isinstance(cu, Data):
                out.write("%s  (data)  %s\n" % (addr, cu.toString()))
                sz = cu.getLength()
                if sz <= 0:
                    sz = 1
                addr = addr.add(sz)
            else:
                # instruction outside a function (unanalyzed island marked as code)
                out.write("%s  (code, no function)  %s\n" % (addr, cu.toString()))
                addr = addr.add(max(cu.getLength(), 1))
            total += 1
    println("[i] Uncovered ranges exported.")

def main():
    program = currentProgram
    listing = program.getListing()
    fm = program.getFunctionManager()
    tmode_reg = getTModeRegister(program)

    if tmode_reg is None:
        println("[!] TMode register not found - mode tags will be '?'")
    else:
        println("[i] TMode register found: %s" % tmode_reg.getName())

    try:
        outFile = askFile("Where to save export?", "Save")
        if outFile is None:
            return
        outPath = outFile.getAbsolutePath()
    except:
        outPath = program.getName() + "_full_export.txt"

    decompiler = DecompInterface()
    decompiler.openProgram(program)
    monitor = ConsoleTaskMonitor()

    funcs = list(fm.getFunctions(True))
    funcs.sort(key=lambda f: f.getEntryPoint().getOffset())

    out = open(outPath, "w")
    try:
        out.write("=" * 100 + "\n")
        out.write("GHIDRA EXPORT: %s\n" % program.getName())
        out.write("Language:      %s\n" % program.getLanguageID())
        out.write("Image base:    %s\n" % program.getImageBase())
        out.write("Functions:     %d\n" % len(funcs))
        out.write("=" * 100 + "\n")

        done = 0
        for func in funcs:
            exportFunction(out, func, listing, decompiler, monitor, tmode_reg)
            out.flush()
            done += 1
            if done % 50 == 0:
                println("Processed: %d / %d" % (done, len(funcs)))

        # NEW: everything that is NOT inside a function body still gets exported
        covered = collectCoveredRanges(program)
        exportUncoveredData(out, program, covered)

        out.write("\n\n" + "=" * 100 + "\nSYMBOLS\n" + "=" * 100 + "\n")
        for sym in program.getSymbolTable().getAllSymbols(True):
            out.write("%s:  %-40s  (%s)\n" % (
                sym.getAddress(), sym.getName(), sym.getSymbolType().toString()
            ))
    finally:
        out.close()
        decompiler.dispose()

    println("Done! File: %s" % outPath)

if __name__ == "__main__":
    main()
