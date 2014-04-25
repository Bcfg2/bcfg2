# TODO: Add completion for each admin mode
_bcfg2-admin() {
	local cur prev possibles
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	if [[ ${COMP_CWORD} -eq 1 ]] || [[ -n "${prev}" && ${prev} == -* ]]
	then
		possibles="$(bcfg2-admin help | awk '{print $1}')"
	#elif bcfg2-admin ${prev} help &>/dev/null ; then
	#	possibles=$(bcfg2-admin ${prev} help | ${sedcmd})
	fi

	[[ -n "${possibles}" ]] && \
		COMPREPLY=( $(compgen -W "${possibles}" -- ${cur}) )

	return 0
}
_bcfg2-info() {
	local cur prev possibles
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	if [[ ${COMP_CWORD} -eq 1 ]] || [[ -n "${prev}" && ${prev} == -* ]]
	then
		possibles="$(bcfg2-info help | awk '{print $1}')"
	fi

	[[ -n "${possibles}" ]] && \
		COMPREPLY=( $(compgen -W "${possibles}" -- ${cur}) )

	return 0
}
complete -F _bcfg2-admin bcfg2-admin
complete -F _bcfg2-info bcfg2-info
