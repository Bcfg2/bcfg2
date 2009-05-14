# TODO: Add completion for each admin mode
_bcfg2-admin() {
	local cur prev sedcmd possibles
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"
	sedcmd='sed -n -e s/^[[:space:]]\+\([[:alpha:]]\+\)[[:space:]]\+.*$/\1/p'

	if [[ ${COMP_CWORD} -eq 1 ]] || [[ -n "${prev}" && ${prev} == -* ]]
	then
		possibles="$(bcfg2-admin help | ${sedcmd})"
	#elif bcfg2-admin ${prev} help &>/dev/null ; then
	#	possibles=$(bcfg2-admin ${prev} help | ${sedcmd})
	fi

	[[ -n "${possibles}" ]] && \
		COMPREPLY=( $(compgen -W "${possibles}" -- ${cur}) )

	return 0
}
complete -F _bcfg2-admin bcfg2-admin
