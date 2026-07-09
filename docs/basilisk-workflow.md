# Basilisk build workflow

This workspace uses a dedicated Basilisk compiler wrapper instead of the
VS Code generated `gcc` or `gcc-15` build tasks.

## Build the active file in VS Code

Use:

```text
Basilisk/qcc: 生成活动文件
```

This task calls:

```bash
tools/basilisk-cc <source.c> -o <output> -lm
```

The wrapper sets `BASILISK`, sets `OPENGLIBS`, builds `qcc` when needed,
builds the Basilisk `gl` helper libraries when needed, and then calls
`qcc -autolink`.

Do not use the generated tasks named like:

```text
C/C++: gcc 生成活动文件
C/C++: gcc-15 生成活动文件
```

Those are plain C compiler tasks and do not understand Basilisk headers,
`qcc` preprocessing, `foreach` syntax, dimensions, or `#pragma autolink`.

## Build from the terminal

From the repository root:

```bash
./tools/basilisk-cc basilisk/src/test/capwave.c -o /tmp/capwave -lm
```

With extra Basilisk/C flags:

```bash
./tools/basilisk-cc -DCLSVOF=1 basilisk/src/test/capwave.c -o /tmp/capwave-clsvof -lm
```

## Build and run from the terminal

Use `tools/basilisk-run` when you want the same behavior as the VS Code
run task:

```bash
./tools/basilisk-run basilisk/src/test/bc0.c
```

With compiler flags:

```bash
./tools/basilisk-run -DCLSVOF=1 basilisk/src/test/capwave.c
```

With program arguments, separate them using `--`:

```bash
./tools/basilisk-run path/to/program.c -- arg1 arg2
```

## Run from VS Code

Use:

```text
Basilisk/qcc: 运行活动文件
```

This builds the active file first, then runs the generated executable from
the source file directory.

Some tests require runtime input files or external tools. For example,
`basilisk/src/test/basilisk.c` needs `basilisk.gnu`, which is generated
from `basilisk.eps` using `pstoedit`.

## CMake

CMake is not the right primary build system for Basilisk programs in this
workspace. Basilisk programs are compiled through `qcc`, which performs
Basilisk-specific preprocessing and autolinking before invoking the C
compiler.

The existing CMake configuration is useful only for the `wsServer`
subproject. VS Code automatic CMake configuration is disabled so it does
not replace the Basilisk/qcc workflow for normal `.c` files.
