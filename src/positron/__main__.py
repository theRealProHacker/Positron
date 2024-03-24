import sys

match sys.argv[1:]:
    case []:
        print("Usage: positron <file>")
    case l if "-h" in l or "--help" in l:
        print("Usage: positron <file>")
    case [file]:
        from positron import set_cwd, run

        set_cwd(file)
        run(file)
    case _:
        print("Usage: positron <file>")
