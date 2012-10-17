%global __python python
%{!?py_ver: %global py_ver %(%{__python} -c 'import sys;print(sys.version[0:3])')}
%global pythonversion %{py_ver}
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?_initrddir: %global _initrddir %{_sysconfdir}/rc.d/init.d}
%global selinux_policyver %(%{__sed} -e 's,.*selinux-policy-\\([^/]*\\)/.*,\\1,' /usr/share/selinux/devel/policyhelp || echo 0.0.0)
%global selinux_types %(%{__awk} '/^#[[:space:]]*SELINUXTYPE=/,/^[^#]/ { if ($3 == "-") printf "%s ", $2 }' /etc/selinux/config 2>/dev/null)
%global selinux_variants %([ -z "%{selinux_types}" ] && echo mls strict targeted || echo %{selinux_types})

Name:             bcfg2-selinux
Version:          1.3.0
Release:          0.1pre1
Summary:          Bcfg2 Client and Server SELinux policy

%if 0%{?suse_version}
Group:            System/Management
Conflicts:        selinux-policy = 2.20120725
%else
Group:            Applications/System
# the selinux reference policy 2.20120725 (3.11.1 in RH versioning)
# contains a bogus bcfg2 module
Conflicts:        selinux-policy = 3.11.1
%endif

License:          BSD
URL:              http://bcfg2.org
Source0:          ftp://ftp.mcs.anl.gov/pub/bcfg/bcfg2-%{version}.tar.gz
%if 0%{?suse_version}
# SUSEs OBS does not understand the id macro below.
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}
%else
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
%endif
BuildArch:        noarch

BuildRequires:    checkpolicy, selinux-policy-devel, hardlink
BuildRequires:    /usr/share/selinux/devel/policyhelp

Requires:         selinux-policy >= %{selinux_policyver}
Requires:         %{name} = %{version}-%{release}
Requires(post):   /usr/sbin/semodule, /sbin/restorecon, /sbin/fixfiles, bcfg2
Requires(postun): /usr/sbin/semodule, /sbin/restorecon, /sbin/fixfiles, bcfg2

%description
Bcfg2 helps system administrators produce a consistent, reproducible,
and verifiable description of their environment, and offers
visualization and reporting tools to aid in day-to-day administrative
tasks. It is the fifth generation of configuration management tools
developed in the Mathematics and Computer Science Division of Argonne
National Laboratory.

It is based on an operational model in which the specification can be
used to validate and optionally change the state of clients, but in a
feature unique to bcfg2 the client's response to the specification can
also be used to assess the completeness of the specification. Using
this feature, bcfg2 provides an objective measure of how good a job an
administrator has done in specifying the configuration of client
systems. Bcfg2 is therefore built to help administrators construct an
accurate, comprehensive specification.

Bcfg2 has been designed from the ground up to support gentle
reconciliation between the specification and current client states. It
is designed to gracefully cope with manual system modifications.

Finally, due to the rapid pace of updates on modern networks, client
systems are constantly changing; if required in your environment,
Bcfg2 can enable the construction of complex change management and
deployment strategies.

This package includes the Bcfg2 server and client SELinux policy.

%prep
%setup -q -n bcfg2-%{version}

%build
cd redhat/selinux
for selinuxvariant in %{selinux_variants}; do
  make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile
  mv bcfg2.pp bcfg2.pp.${selinuxvariant}
  make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile clean
done
cd -

%install
for selinuxvariant in %{selinux_variants}; do
  install -d %{buildroot}%{_datadir}/selinux/${selinuxvariant}
  install -p -m 644 redhat/selinux/bcfg2.pp.${selinuxvariant} \
    %{buildroot}%{_datadir}/selinux/${selinuxvariant}/bcfg2.pp
done
/usr/sbin/hardlink -cv %{buildroot}%{_datadir}/selinux

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot} || exit 2

%files
%defattr(-,root,root,0755)
%doc redhat/selinux/*
%{_datadir}/selinux/*/bcfg2.pp

%post
for selinuxvariant in %{selinux_variants}; do
  /usr/sbin/semodule -s ${selinuxvariant} -i \
    %{_datadir}/selinux/${selinuxvariant}/bcfg2.pp &> /dev/null || :
done
/sbin/fixfiles -R bcfg2 restore || :
if rpm -q bcfg2-server >& /dev/null; then
   /sbin/fixfiles -R bcfg2-server restore || :
fi
/sbin/restorecon -R %{_localstatedir}/cache/bcfg2 || :
/sbin/restorecon -R %{_localstatedir}/lib/bcfg2 || :

%postun
if [ $1 -eq 0 ] ; then
  for selinuxvariant in %{selinux_variants}; do
    /usr/sbin/semodule -s ${selinuxvariant} -r bcfg2 &> /dev/null || :
  done
  /sbin/fixfiles -R bcfg2 restore || :
  if rpm -q bcfg2-server >& /dev/null; then
      /sbin/fixfiles -R bcfg2-server restore || :
  fi
  [ -d %{_localstatedir}/cache/bcfg2 ] && \
      /sbin/restorecon -R %{_localstatedir}/cache/bcfg2 || :
  [ -d %{_localstatedir}/lib/bcfg2 ] && \
      /sbin/restorecon -R %{_localstatedir}/lib/bcfg2 || :
fi

%changelog
* Fri Sep 14 2012 Chris St. Pierre <chris.a.st.pierre@gmail.com> 1.3.0-0.2pre1
- Broke bcfg2-selinux into its own specfile
