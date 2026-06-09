# Bash completion for calc

_calc_completion() {
    local cur prev words cword
    _init_completion || return

    # Options
    local options="-h --help -v --version -e --expression -q --quiet -s --show --json -i --interactive"

    if [[ ${cur} == -* ]]; then
        COMPREPLY=($(compgen -W "${options}" -- "${cur}"))
        return
    fi

    # Functions
    local functions="sin cos tan asin acos atan sinh cosh tanh sqrt log log10 log2 exp abs floor ceil round factorial gcd lcm perm comb nPr nCr mean median mode std variance sum min max isprime primefactors nextprime prevprime"

    # Constants
    local constants="pi e tau i avogadro planck boltzmann c"

    # Units
    local units="m km cm mm in ft yd mi s ms min h d wk yr B KB MB GB TB kg g mg lb oz L mL gal"

    case ${prev} in
        -e|--expression)
            # Suggest functions and constants for expression context
            COMPREPLY=($(compgen -W "${functions} ${constants}" -- "${cur}"))
            return
            ;;
        *)
            # Suggest options, functions, constants, and units
            COMPREPLY=($(compgen -W "${options} ${functions} ${constants} ${units}" -- "${cur}"))
            return
            ;;
    esac
}

complete -F _calc_completion calc
