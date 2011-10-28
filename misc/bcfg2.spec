%define release 0.1
%define __python python
%{!?py_ver: %define py_ver %(%{__python} -c 'import sys;print(sys.version[0:3])')}
%define pythonversion %{py_ver}
%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?_initrddir: %define _initrddir %{_sysconfdir}/rc.d/init.d}

# Most rpm-based distributions include the lxml package a 'python-lxml',
# but some distributions and some people who roll their own lxml packages
# call it just 'lxml'. We'll try to catch both.
%define dfl_lxml python-lxml
%define alt_lxml lxml
%define lxmldep %(rpm -q %{alt_lxml} 2>&1 > /dev/null && echo %{alt_lxml} || echo %{dfl_lxml})

Name:             bcfg2
Version:          1.2.0rc2
Release:          %{release}
Summary:          Configuration management system

Group:            Applications/System
License:          BSD
URL:              http://bcfg2.org
Source0:          ftp://ftp.mcs.anl.gov/pub/bcfg/%{name}-%{version}.tar.gz
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:        noarch

BuildRequires:    python-devel
BuildRequires:    %{lxmldep}

# %{rhel} wasn't set before rhel 6.  so this checks for old RHEL
# %systems (and potentially very old Fedora systems, too)
%if "%{_vendor}" == "redhat" && 0%{?rhel} <= 6
BuildRequires: python-sphinx10
# the python-sphinx10 package doesn't set sys.path correctly, so we
# have to do it for them
%define pythonpath /usr/lib/python%{py_ver}/site-packages/Sphinx-1.0.4-py%{py_ver}.egg
%else
BuildRequires: python-sphinx >= 0.6
%endif

Requires:         %{lxmldep} >= 0.9

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

%package -n bcfg2-server
Version: %{version}
Summary: Bcfg2 Server
Group: System Tools
Requires: bcfg2
%if "%{py_ver}" < "2.6"
Requires:         python-ssl
%endif
Requires:         %{lxmldep} >= 1.2.1
%if "%{_vendor}" == "redhat"
Requires: gamin-python
%endif

%description -n bcfg2-server
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

%package -n bcfg2-doc
Summary:          Configuration management system documentation
Group:            Documentation

%description -n bcfg2-doc
Configuration management system documentation

%package -n bcfg2-web
Version: %{version}
Summary: Bcfg2 Web Reporting Interface
Group: System Tools
Requires: bcfg2-server
Requires: httpd,Django
%if "%{_vendor}" == "redhat"
Requires: mod_wsgi
%define apache_conf %{_sysconfdir}/httpd
%else
Requires: apache2-mod_wsgi
%define apache_conf %{_sysconfdir}/apache2
%endif

%description -n bcfg2-web
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

%prep
%setup -q -n bcfg2-%{version}

%build
%{__python}%{pythonversion} setup.py build
%{__python}%{pythonversion} setup.py build_dtddoc

%{?pythonpath: export PYTHONPATH="%{pythonpath}"}
%{__python}%{pythonversion} setup.py build_sphinx

%install
%{__python}%{pythonversion} setup.py install --root=%{buildroot} --record=INSTALLED_FILES --prefix=/usr
%{__install} -d %{buildroot}%{_bindir}
%{__install} -d %{buildroot}%{_sbindir}
%{__install} -d %{buildroot}%{_initrddir}
%{__install} -d %{buildroot}%{_sysconfdir}/default
%{__install} -d %{buildroot}%{_sysconfdir}/cron.daily
%{__install} -d %{buildroot}%{_sysconfdir}/cron.hourly
%{__install} -d %{buildroot}%{_prefix}/lib/bcfg2
mkdir -p %{buildroot}%{_defaultdocdir}/bcfg2-doc-%{version}

%{__mv} %{buildroot}/usr/bin/bcfg2* %{buildroot}%{_sbindir}
%{__install} -m 755 debian/bcfg2.init %{buildroot}%{_initrddir}/bcfg2
%{__install} -m 755 debian/bcfg2-server.init %{buildroot}%{_initrddir}/bcfg2-server
%{__install} -m 755 debian/bcfg2.default %{buildroot}%{_sysconfdir}/default/bcfg2
%{__install} -m 755 debian/bcfg2-server.default %{buildroot}%{_sysconfdir}/default/bcfg2-server
%{__install} -m 755 debian/bcfg2.cron.daily %{buildroot}%{_sysconfdir}/cron.daily/bcfg2
%{__install} -m 755 debian/bcfg2.cron.hourly %{buildroot}%{_sysconfdir}/cron.hourly/bcfg2
%{__install} -m 755 tools/bcfg2-cron %{buildroot}%{_prefix}/lib/bcfg2/bcfg2-cron

mv build/sphinx/html/* %{buildroot}%{_defaultdocdir}/bcfg2-doc-%{version}
mv build/dtd %{buildroot}%{_defaultdocdir}/bcfg2-doc-%{version}/

%{__install} -d %{buildroot}%{apache_conf}/conf.d
%{__install} -m 644 misc/apache/bcfg2.conf %{buildroot}%{apache_conf}/conf.d/wsgi_bcfg2.conf

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot} || exit 2

%files -n bcfg2
%defattr(-,root,root,-)
%{_sbindir}/bcfg2
%{python_sitelib}/Bcfg2/*.py*
%{python_sitelib}/Bcfg2/Client/*
%{_mandir}/man1/bcfg2.1*
%{_mandir}/man5/bcfg2.conf.5*
%{_initrddir}/bcfg2
%config(noreplace) %{_sysconfdir}/default/bcfg2
%{_sysconfdir}/cron.hourly/bcfg2
%{_sysconfdir}/cron.daily/bcfg2
%{_prefix}/lib/bcfg2/bcfg2-cron

%post -n bcfg2-server
/sbin/chkconfig --add bcfg2-server

%files -n bcfg2-server
%defattr(-,root,root,-)

%{_initrddir}/bcfg2-server

%{python_sitelib}/Bcfg2/Server

%if "%{pythonversion}" >= "2.5"
%{python_sitelib}/*egg-info
%endif

%dir %{_datadir}/bcfg2
%{_datadir}/bcfg2/Hostbase
%{_datadir}/bcfg2/schemas
%{_datadir}/bcfg2/xsl-transforms
%config(noreplace) %{_sysconfdir}/default/bcfg2-server
%{_sbindir}/bcfg2-admin
%{_sbindir}/bcfg2-build-reports
%{_sbindir}/bcfg2-info
%{_sbindir}/bcfg2-ping-sweep
%{_sbindir}/bcfg2-lint
%{_sbindir}/bcfg2-repo-validate
%{_sbindir}/bcfg2-reports
%{_sbindir}/bcfg2-server
%{_sbindir}/bcfg2-yum-helper

%{_mandir}/man5/bcfg2-lint.conf.5*
%{_mandir}/man8/*.8*
%dir %{_prefix}/lib/bcfg2

%files doc
%defattr(-,root,root,-)
%doc %{_defaultdocdir}/bcfg2-doc-%{version}

%files -n bcfg2-web
%defattr(-,root,root,-)

%{_datadir}/bcfg2/reports.wsgi
%{_datadir}/bcfg2/site_media

%config(noreplace) %{apache_conf}/conf.d/wsgi_bcfg2.conf

%changelog
%changelog
* Thu Jan 27 2011 Chris St. Pierre <stpierreca@ornl.gov> 1.2.0pre1-0.0
- Added -doc sub-package

* Mon Jun 21 2010 Fabian Affolter <fabian@bernewireless.net> - 1.1.0rc3-0.1
- Changed source0 in order that it works with spectool 

* Fri Feb 2 2007 Mike Brady <mike.brady@devnull.net.nz> 0.9.1
- Removed use of _libdir due to Red Hat x86_64 issue.

* Fri Dec 22 2006 Jeffrey C. Ollie <jeff@ocjtech.us> - 0.8.7.1-5
- Server needs client library files too so put them in main package

* Wed Dec 20 2006 Jeffrey C. Ollie <jeff@ocjtech.us> - 0.8.7.1-4
- Yes, actually we need to require openssl

* Wed Dec 20 2006 Jeffrey C. Ollie <jeff@ocjtech.us> - 0.8.7.1-3
- Don't generate SSL cert in post script, it only needs to be done on
  the server and is handled by the bcfg2-admin tool.
- Move the /etc/bcfg2.key file to the server package
- Don't install a sample copy of the config file, just ghost it
- Require gamin-python for the server package
- Don't require openssl
- Make the client a separate package so you don't have to have the
  client if you don't want it

* Wed Dec 20 2006 Jeffrey C. Ollie <jeff@ocjtech.us> - 0.8.7.1-2
- Add more documentation

* Mon Dec 18 2006 Jeffrey C. Ollie <jeff@ocjtech.us> - 0.8.7.1-1
- First version for Fedora Extras

* Fri Sep 15 2006 Narayan Desai <desai@mcs.anl.gov> - 0.8.4-1
- Initial log

