# Fish completion for calc

# Disable file completion by default
complete -c calc -f

# Options
complete -c calc -s h -l help -d 'Show help message'
complete -c calc -s v -l version -d 'Show version information'
complete -c calc -s e -l expression -d 'Evaluate a single expression' -x
complete -c calc -s q -l quiet -d 'Suppress expression in output'
complete -c calc -s s -l show -d 'Show expression in output'
complete -c calc -l json -d 'Output result as JSON'
complete -c calc -s i -l interactive -d 'Start interactive REPL mode'

# Functions
complete -c calc -n '__fish_use_subcommand' -a 'sin cos tan asin acos atan sinh cosh tanh' -d 'Trigonometric function'
complete -c calc -n '__fish_use_subcommand' -a 'sqrt log log10 log2 exp' -d 'Mathematical function'
complete -c calc -n '__fish_use_subcommand' -a 'abs floor ceil round' -d 'Rounding function'
complete -c calc -n '__fish_use_subcommand' -a 'factorial gcd lcm perm comb nPr nCr' -d 'Combinatorics function'
complete -c calc -n '__fish_use_subcommand' -a 'mean median mode std variance sum min max' -d 'Statistics function'
complete -c calc -n '__fish_use_subcommand' -a 'isprime primefactors nextprime prevprime' -d 'Prime function'

# Constants
complete -c calc -n '__fish_use_subcommand' -a 'pi' -d 'Mathematical constant π'
complete -c calc -n '__fish_use_subcommand' -a 'e' -d 'Euler\'s number'
complete -c calc -n '__fish_use_subcommand' -a 'tau' -d '2π'
complete -c calc -n '__fish_use_subcommand' -a 'i' -d 'Imaginary unit'
complete -c calc -n '__fish_use_subcommand' -a 'avogadro' -d 'Avogadro constant'
complete -c calc -n '__fish_use_subcommand' -a 'planck' -d 'Planck constant'
complete -c calc -n '__fish_use_subcommand' -a 'boltzmann' -d 'Boltzmann constant'
complete -c calc -n '__fish_use_subcommand' -a 'c' -d 'Speed of light'

# Units
complete -c calc -n '__fish_use_subcommand' -a 'm km cm mm in ft yd mi' -d 'Length unit'
complete -c calc -n '__fish_use_subcommand' -a 's ms min h d wk yr' -d 'Time unit'
complete -c calc -n '__fish_use_subcommand' -a 'B KB MB GB TB' -d 'Data unit'
complete -c calc -n '__fish_use_subcommand' -a 'kg g mg lb oz' -d 'Mass unit'
complete -c calc -n '__fish_use_subcommand' -a 'L mL gal' -d 'Volume unit'
