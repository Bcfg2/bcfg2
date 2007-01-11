%define release 0.1
%define __python python
%define pythonversion 2.3
%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:             bcfg2
Version:          0.9.0pre2
Release: %{release}
Summary:          Configuration management system

Group:            Applications/System
License:          BSD
URL:              http://trac.mcs.anl.gov/projects/bcfg2
Source0:          ftp://ftp.mcs.anl.gov/pub/bcfg/bcfg2-%{version}.tar.gz
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:        noarch

BuildRequires:    python-devel
Requires:         python-lxml

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
Requires: bcfg2, pyOpenSSL
%if "%{_vendor}" == "redhat"
Requires: gamin-python
%endif


%description -n bcfg2-server
Bcfg2 client

%prep
%setup -q

%build
%{__python}%{pythonversion} setup.py build

%install
%{__python}%{pythonversion} setup.py install --root=%{buildroot} --record=INSTALLED_FILES
%{__install} -d %{buildroot}/usr/bin
%{__install} -d %{buildroot}/usr/sbin
%{__install} -d %{buildroot}/etc/init.d
%{__install} -d %{buildroot}/etc/default
%{__install} -d %{buildroot}/etc/cron.daily
%{__install} -d %{buildroot}/etc/cron.hourly
%{__install} -d %{buildroot}/usr/lib/bcfg2
%{__mv} %{buildroot}/usr/bin/bcfg2* %{buildroot}/usr/sbin
%{__install} -m 755 debian/buildsys/common/bcfg2.init %{buildroot}/etc/init.d/bcfg2
%{__install} -m 755 debian/buildsys/common/bcfg2-server.init %{buildroot}/etc/init.d/bcfg2-server
%{__install} -m 755 debian/bcfg2.default %{buildroot}/etc/default/bcfg2
%{__install} -m 755 debian/bcfg2.cron.daily %{buildroot}/etc/cron.daily/bcfg2
%{__install} -m 755 debian/bcfg2.cron.hourly %{buildroot}/etc/cron.hourly/bcfg2
%{__install} -m 755 tools/bcfg2-cron %{buildroot}/usr/lib/bcfg2/bcfg2-cron

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot} || exit 2

%files -n bcfg2
%defattr(-,root,root)
/usr/sbin/bcfg2
/usr/lib*/python%{pythonversion}/site-packages/Bcfg2/*.py*
/usr/lib*/python%{pythonversion}/site-packages/Bcfg2/Client/*
/usr/share/man/man1/*
/usr/share/man/man5/*
/etc/init.d/bcfg2
%config(noreplace) /etc/default/bcfg2
/etc/cron.hourly/bcfg2
/etc/cron.daily/bcfg2
/usr/lib/bcfg2/bcfg2-cron

%post -n bcfg2-server
/sbin/chkconfig --add bcfg2-server

%files -n bcfg2-server
%defattr(-,root,root,_)

%ghost %attr(600,root,root) %config(noreplace) %{_sysconfdir}/bcfg2.key

%{_initrddir}/bcfg2-server

%{python_sitelib}/Bcfg2/Server

%{_datadir}/bcfg2

%{_sbindir}/bcfg2-admin
%{_sbindir}/bcfg2-build-reports
%{_sbindir}/bcfg2-info
%{_sbindir}/bcfg2-ping-sweep
%{_sbindir}/bcfg2-query
%{_sbindir}/bcfg2-repo-validate
%{_sbindir}/bcfg2-server

%{_mandir}/man8/bcfg2-build-reports.8*
%{_mandir}/man8/bcfg2-info.8*
%{_mandir}/man8/bcfg2-repo-validate.8*
%{_mandir}/man8/bcfg2-server.8*

%dir %{_var}/lib/bcfg2

%changelog
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

