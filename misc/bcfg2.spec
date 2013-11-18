# Fedora 13+ and EL6 contain these macros already; only needed for EL5
%if 0%{?rhel} && 0%{?rhel} <= 5
%global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")
%define python_version %(%{__python} -c 'import sys;print(sys.version[0:3])')
%endif

# openSUSE macro translation
%if 0%{?suse_version}
%global python_version %{py_ver}
%{!?_initrddir: %global _initrddir %{_sysconfdir}/rc.d/init.d}
# openSUSE < 11.2
%if %{suse_version} < 1120
%global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")
%endif
%endif

# For -pre or -rc releases, remove the initial <hash><percent>
# characters from the appropriate line below.
#
# Don't forget to change the Release: tag below to something like 0.1
#%%global _rc 1
#%%global _pre 2
%global _pre_rc %{?_pre:.pre%{_pre}}%{?_rc:.rc%{_rc}}

Name:             bcfg2
Version:          1.3.3
Release:          1%{?_pre_rc}%{?dist}
Summary:          A configuration management system

%if 0%{?suse_version}
# http://en.opensuse.org/openSUSE:Package_group_guidelines
Group:            System/Management
%else
Group:            Applications/System
%endif
License:          BSD
URL:              http://bcfg2.org
Source0:          ftp://ftp.mcs.anl.gov/pub/bcfg/%{name}-%{version}.tar.gz
# Used in %%check
Source1:          http://www.w3.org/2001/XMLSchema.xsd
%if %{?rhel}%{!?rhel:10} <= 5 || 0%{?suse_version}
# EL5 and OpenSUSE require the BuildRoot tag
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
%endif
BuildArch:        noarch

BuildRequires:    python
BuildRequires:    python-devel
BuildRequires:    python-lxml
BuildRequires:    python-boto
%if 0%{?suse_version}
BuildRequires:    python-M2Crypto
BuildRequires:    python-Genshi
BuildRequires:    python-gamin
BuildRequires:    python-pyinotify
BuildRequires:    python-python-daemon
BuildRequires:    python-CherryPy >= 3
%else # ! suse_version
BuildRequires:    python-daemon
BuildRequires:    python-inotify
%if "%{_vendor}" == "redhat" && 0%{!?rhel:1} && 0%{!?fedora:1}
# by default, el5 doesn't have the %%rhel macro, provided by this
# package; EPEL build servers install buildsys-macros by default, but
# explicitly requiring this may help builds in other environments
BuildRequires:    buildsys-macros
%else # vendor != redhat || rhel defined
%if 0%{?rhel} && 0%{?rhel} < 6
BuildRequires:    python-ssl
%else # rhel > 5
# EL5 lacks python-mock, so test suite is disabled
BuildRequires:    python-sqlalchemy
BuildRequires:    python-nose
BuildRequires:    mock
BuildRequires:    m2crypto
BuildRequires:    Django
BuildRequires:    python-genshi
BuildRequires:    python-cheetah
BuildRequires:    pylibacl
BuildRequires:    libselinux-python
BuildRequires:    python-pep8
BuildRequires:    python-cherrypy >= 3
BuildRequires:    python-mock
BuildRequires:    pylint
%endif # rhel > 5
%endif # vendor != redhat || rhel defined
%endif # ! suse_version

%if 0%{?mandriva_version}
# mandriva seems to behave differently than other distros and needs
# this explicitly.
BuildRequires:    python-setuptools
%endif
%if 0%{?mandriva_version} == 201100
# mandriva 2011 has multiple providers for libsane, so (at least when
# building on OBS) one must be chosen explicitly: "have choice for
# libsane.so.1 needed by python-imaging: libsane1 sane-backends-iscan"
BuildRequires:    libsane1
%endif

# RHEL 5 and 6 ship with sphinx 0.6, but sphinx 1.0 is available with
# a different package name in EPEL.
%if "%{_vendor}" == "redhat" && 0%{?rhel} <= 6 && 0%{?fedora} == 0
BuildRequires:    python-sphinx10
# python-sphinx10 doesn't set sys.path correctly; do it for them
%global pythonpath %(find %{python_sitelib} -name Sphinx*.egg)
%else
BuildRequires:    python-sphinx >= 1.0
%endif
BuildRequires:    python-docutils

%if 0%{?fedora} >= 16
BuildRequires:    systemd-units
%endif

%if 0%{?rhel} && 0%{?rhel} < 6
Requires:         python-ssl
%endif
Requires:         libselinux-python

%if 0%{?fedora} >= 16
Requires(post):   systemd-units
Requires(preun):  systemd-units
Requires(postun): systemd-units
%else
Requires(post):   /sbin/chkconfig
Requires(preun):  /sbin/chkconfig
Requires(preun):  /sbin/service
Requires(postun): /sbin/service
%endif

%if "%{_vendor}" != "redhat"
# fedora and rhel (and possibly other distros) do not know this tag.
Recommends:       cron
%endif


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

This package includes the Bcfg2 client software.

%package server
Summary:          Bcfg2 Server
%if 0%{?suse_version}
Group:            System/Management
%else
Group:            System Environment/Daemons
%endif
Requires:         bcfg2 = %{version}-%{release}
Requires:         python-lxml >= 1.2.1
%if 0%{?suse_version}
Requires:         python-pyinotify
Requires:         python-python-daemon
%else
Requires:         python-inotify
Requires:         python-daemon
%endif
Requires:         /usr/sbin/sendmail
Requires:         /usr/bin/openssl
Requires:         graphviz
Requires:         python-nose

%if %{_vendor} == redhat
%if 0%{?fedora} >= 16
Requires(post):   systemd-units
Requires(preun):  systemd-units
Requires(postun): systemd-units
Requires(post):   systemd-sysv
%else
Requires(post):   /sbin/chkconfig
Requires(preun):  /sbin/chkconfig
Requires(preun):  /sbin/service
Requires(postun): /sbin/service
%endif
%endif


%description server
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

This package includes the Bcfg2 server software.

%package server-cherrypy
Summary:          Bcfg2 Server - CherryPy backend
%if 0%{?suse_version}
Group:            System/Management
%else
Group:            System Environment/Daemons
%endif
Requires:         bcfg2 = %{version}-%{release}
Requires:         bcfg2-server = %{version}-%{release}

# cherrypy 3.3 actually doesn't exist yet, but 3.2 has bugs that
# prevent it from working:
# https://bitbucket.org/cherrypy/cherrypy/issue/1154/assertionerror-in-recv-when-ssl-is-enabled
Requires:         python-cherrypy > 3.3

%description server-cherrypy
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

This package includes the Bcfg2 CherryPy server backend.

%package web
Summary:          Bcfg2 Web Reporting Interface

%if 0%{?suse_version}
Group:            System/Management
Requires:         python-django >= 1.2
Requires:         python-django-south >= 0.7
%else
Group:            System Tools
Requires:         Django >= 1.2
Requires:         Django-south >= 0.7
Requires:         bcfg2-server
%endif
Requires:         httpd
%if "%{_vendor}" == "redhat"
Requires:         mod_wsgi
%global apache_conf %{_sysconfdir}/httpd
%else
Requires:         apache2-mod_wsgi
%global apache_conf %{_sysconfdir}/apache2
%endif


%description web
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

This package includes the Bcfg2 reports web frontend.


%package doc
Summary:          Documentation for Bcfg2
%if 0%{?suse_version}
Group:            Documentation/HTML
%else
Group:            Documentation
%endif


%description doc
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

This package includes the Bcfg2 documentation.


%package examples
Summary:          Examples for Bcfg2
Group:            Documentation


%description examples
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

This package includes the examples files for Bcfg2.


%prep
%setup -q -n %{name}-%{version}%{?_pre_rc}

# The pylint and pep8 unit tests fail on RH-derivative distros
%if "%{_vendor}" == "redhat"
mv testsuite/Testsrc/test_code_checks.py \
    testsuite/Testsrc/test_code_checks.py.disable_unit_tests
awk '
    BEGIN {line=0}
    /class Test(Pylint|PEP8)/ {line=FNR+1}
    FNR==line {sub("True","False")}
    {print $0}
    ' testsuite/Testsrc/test_code_checks.py.disable_unit_tests \
    > testsuite/Testsrc/test_code_checks.py
%endif

# Fixup some paths
%{__perl} -pi -e 's@/etc/default@%{_sysconfdir}/sysconfig@g' tools/bcfg2-cron

# Get rid of extraneous shebangs
for f in `find src/lib -name \*.py`
do
    sed -i -e '/^#!/,1d' $f
done

sed -i "s/apache2/httpd/g" misc/apache/bcfg2.conf


%build
%{__python} setup.py build
%{?pythonpath: PYTHONPATH="%{pythonpath}"} \
    %{__python} setup.py build_sphinx


%install
%if 0%{?rhel} == 5 || 0%{?suse_version}
# EL5 and OpenSUSE require the buildroot to be cleaned manually
rm -rf %{buildroot}
%endif

%{__python} setup.py install -O1 --skip-build --root=%{buildroot} --prefix=/usr
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_sbindir}
install -d %{buildroot}%{_initrddir}
install -d %{buildroot}%{_sysconfdir}/cron.daily
install -d %{buildroot}%{_sysconfdir}/cron.hourly
install -d %{buildroot}%{_sysconfdir}/sysconfig
install -d %{buildroot}%{_libexecdir}
install -d %{buildroot}%{_localstatedir}/cache/%{name}
install -d %{buildroot}%{_localstatedir}/lib/%{name}
%if 0%{?suse_version}
install -d %{buildroot}/var/adm/fillup-templates
%endif

mv %{buildroot}%{_bindir}/bcfg2* %{buildroot}%{_sbindir}

%if 0%{?fedora} < 16
# Install SysV init scripts for everyone but new Fedoras
install -m 755 redhat/scripts/bcfg2.init \
    %{buildroot}%{_initrddir}/bcfg2
install -m 755 redhat/scripts/bcfg2-server.init \
    %{buildroot}%{_initrddir}/bcfg2-server
install -m 755 redhat/scripts/bcfg2-report-collector.init \
    %{buildroot}%{_initrddir}/bcfg2-report-collector
%endif
install -m 755 debian/bcfg2.cron.daily \
    %{buildroot}%{_sysconfdir}/cron.daily/bcfg2
install -m 755 debian/bcfg2.cron.hourly \
    %{buildroot}%{_sysconfdir}/cron.hourly/bcfg2
install -m 755 tools/bcfg2-cron \
    %{buildroot}%{_libexecdir}/bcfg2-cron

install -m 644 debian/bcfg2.default \
    %{buildroot}%{_sysconfdir}/sysconfig/bcfg2
install -m 644 debian/bcfg2-server.default \
    %{buildroot}%{_sysconfdir}/sysconfig/bcfg2-server
%if 0%{?suse_version}
install -m 755 debian/bcfg2.default \
    %{buildroot}/var/adm/fillup-templates/sysconfig.bcfg2
install -m 755 debian/bcfg2-server.default \
    %{buildroot}/var/adm/fillup-templates/sysconfig.bcfg2-server
ln -s %{_initrddir}/bcfg2 %{buildroot}%{_sbindir}/rcbcfg2
ln -s %{_initrddir}/bcfg2-server %{buildroot}%{_sbindir}/rcbcfg2-server
%endif

touch %{buildroot}%{_sysconfdir}/%{name}.{cert,conf,key}

# systemd
install -d %{buildroot}%{_unitdir}
install -p -m 644 redhat/systemd/%{name}.service \
    %{buildroot}%{_unitdir}/%{name}.service
install -p -m 644 redhat/systemd/%{name}-server.service \
    %{buildroot}%{_unitdir}/%{name}-server.service

# Webserver
install -d %{buildroot}%{apache_conf}/conf.d
install -p -m 644 misc/apache/bcfg2.conf \
    %{buildroot}%{apache_conf}/conf.d/wsgi_bcfg2.conf

# mandriva cannot handle %ghost without the file existing,
# so let's touch a bunch of empty config files
touch %{buildroot}%{_sysconfdir}/bcfg2.conf

%if 0%{?rhel} == 5
# Required for EL5
%clean
rm -rf %{buildroot}
%endif


%if 0%{?rhel} != 5
# EL5 lacks python-mock, so test suite is disabled
%check
# Downloads not allowed in koji; fix .xsd urls to point to local files
sed -i "s@schema_url = .*\$@schema_url = 'file://`pwd`/`basename %{SOURCE1}`'@" \
    testsuite/Testschema/test_schema.py
sed "s@http://www.w3.org/2001/xml.xsd@file://$(pwd)/schemas/xml.xsd@" \
    %{SOURCE1} > `basename %{SOURCE1}`
%{__python} setup.py test
%endif


%post
%if 0%{?fedora} >= 18
  %systemd_post bcfg2.service
%else
  if [ $1 -eq 1 ] ; then
      # Initial installation
  %if 0%{?suse_version}
      %fillup_and_insserv -f bcfg2
  %else %if 0%{?fedora} >= 16
      /bin/systemctl daemon-reload >/dev/null 2>&1 || :
  %else
      /sbin/chkconfig --add bcfg2
  %endif %endif
  fi
%endif

%post server
%if 0%{?fedora} >= 18
  %systemd_post bcfg2-server.service
%else
  if [ $1 -eq 1 ] ; then
      # Initial installation
  %if 0%{?suse_version}
      %fillup_and_insserv -f bcfg2-server
  %else %if 0%{?fedora} >= 16
      /bin/systemctl daemon-reload >/dev/null 2>&1 || :
  %else
      /sbin/chkconfig --add bcfg2-server
  %endif %endif
  fi
%endif

%preun
%if 0%{?fedora} >= 18
  %systemd_preun bcfg2.service
%else
  if [ $1 -eq 0 ]; then
      # Package removal, not upgrade
  %if 0%{?suse_version}
      %stop_on_removal bcfg2
  %else %if 0%{?fedora} >= 16
      /bin/systemctl --no-reload disable bcfg2.service > /dev/null 2>&1 || :
      /bin/systemctl stop bcfg2.service > /dev/null 2>&1 || :
  %else
      /sbin/service bcfg2 stop &>/dev/null || :
      /sbin/chkconfig --del bcfg2
  %endif %endif
  fi
%endif

%preun server
%if 0%{?fedora} >= 18
  %systemd_preun bcfg2-server.service
%else
  if [ $1 -eq 0 ]; then
      # Package removal, not upgrade
  %if 0%{?suse_version}
      %stop_on_removal bcfg2-server
      %stop_on_removal bcfg2-report-collector
  %else %if 0%{?fedora} >= 16
      /bin/systemctl --no-reload disable bcfg2-server.service > /dev/null 2>&1 || :
      /bin/systemctl stop bcfg2-server.service > /dev/null 2>&1 || :
  %else
      /sbin/service bcfg2-server stop &>/dev/null || :
      /sbin/chkconfig --del bcfg2-server
  %endif %endif
  fi
%endif

%postun
%if 0%{?fedora} >= 18
  %systemd_postun bcfg2.service
%else
  %if 0%{?fedora} >= 16
  /bin/systemctl daemon-reload >/dev/null 2>&1 || :
  %endif
  if [ $1 -ge 1 ] ; then
      # Package upgrade, not uninstall
  %if 0%{?suse_version}
      %insserv_cleanup
  %else %if 0%{?fedora} >= 16
      /bin/systemctl try-restart bcfg2.service >/dev/null 2>&1 || :
  %else
      /sbin/service bcfg2 condrestart &>/dev/null || :
  %endif %endif
  fi
%endif

%postun server
%if 0%{?fedora} >= 18
  %systemd_postun bcfg2-server.service
%else
  %if 0%{?fedora} >= 16
  /bin/systemctl daemon-reload >/dev/null 2>&1 || :
  %endif
  if [ $1 -ge 1 ] ; then
      # Package upgrade, not uninstall
  %if 0%{?fedora} >= 16
      /bin/systemctl try-restart bcfg2-server.service >/dev/null 2>&1 || :
  %else
      /sbin/service bcfg2-server condrestart &>/dev/null || :
  %endif
  fi
  %if 0%{?suse_version}
  if [ $1 -eq 0 ]; then
      # clean up on removal.
      %insserv_cleanup
  fi
  %endif
%endif

%if 0%{?fedora} || 0%{?rhel}
%triggerun -- bcfg2 < 1.2.1-1
/usr/bin/systemd-sysv-convert --save bcfg2 >/dev/null 2>&1 || :
/bin/systemctl --no-reload enable bcfg2.service >/dev/null 2>&1 || :
/sbin/chkconfig --del bcfg2 >/dev/null 2>&1 || :
/bin/systemctl try-restart bcfg2.service >/dev/null 2>&1 || :

%triggerun server -- bcfg2-server < 1.2.1-1
/usr/bin/systemd-sysv-convert --save bcfg2-server >/dev/null 2>&1 || :
/bin/systemctl --no-reload enable bcfg2-server.service >/dev/null 2>&1 || :
/sbin/chkconfig --del bcfg2-server >/dev/null 2>&1 || :
/bin/systemctl try-restart bcfg2-server.service >/dev/null 2>&1 || :
%endif


%files
%if 0%{?rhel} == 5 || 0%{?suse_version}
# Required for EL5 and OpenSUSE
%defattr(-,root,root,-)
%endif
%doc COPYRIGHT LICENSE README
%{_mandir}/man1/bcfg2.1*
%{_mandir}/man5/bcfg2.conf.5*
%ghost %attr(600,root,root) %config(noreplace,missingok) %{_sysconfdir}/bcfg2.cert
%ghost %attr(0600,root,root) %config(noreplace,missingok) %{_sysconfdir}/bcfg2.conf
%if 0%{?fedora} >= 16
    %config(noreplace) %{_unitdir}/%{name}.service
%else
    %{_initrddir}/bcfg2
%endif
%if 0%{?fedora} || 0%{?rhel}
%config(noreplace) %{_sysconfdir}/sysconfig/bcfg2
%else
%config(noreplace) %{_sysconfdir}/default/bcfg2
%endif
%{_sysconfdir}/cron.daily/bcfg2
%{_sysconfdir}/cron.hourly/bcfg2
%{_sbindir}/bcfg2
%{_libexecdir}/bcfg2-cron
%dir %{_localstatedir}/cache/%{name}
%{python_sitelib}/Bcfg2*.egg-info
%dir %{python_sitelib}/Bcfg2
%{python_sitelib}/Bcfg2/__init__.py*
%{python_sitelib}/Bcfg2/Client
%{python_sitelib}/Bcfg2/Compat.py*
%{python_sitelib}/Bcfg2/Logger.py*
%{python_sitelib}/Bcfg2/Options.py*
%{python_sitelib}/Bcfg2/Proxy.py*
%{python_sitelib}/Bcfg2/Utils.py*
%{python_sitelib}/Bcfg2/version.py*
%if 0%{?suse_version}
%{_sbindir}/rcbcfg2
%config(noreplace) /var/adm/fillup-templates/sysconfig.bcfg2
%endif

%files server
%if 0%{?rhel} == 5 || 0%{?suse_version}
%defattr(-,root,root,-)
%endif
%ghost %attr(600,root,root) %config(noreplace) %{_sysconfdir}/bcfg2.key
%if 0%{?fedora} >= 16
    %config(noreplace) %{_unitdir}/%{name}-server.service
%else
    %{_initrddir}/bcfg2-server
    %{_initrddir}/bcfg2-report-collector
%endif
%config(noreplace) %{_sysconfdir}/sysconfig/bcfg2-server
%{_sbindir}/bcfg2-*
%dir %{_localstatedir}/lib/%{name}
%{python_sitelib}/Bcfg2/Cache.py*
%{python_sitelib}/Bcfg2/Encryption.py*
%{python_sitelib}/Bcfg2/SSLServer.py*
%{python_sitelib}/Bcfg2/Statistics.py*
%{python_sitelib}/Bcfg2/settings.py*
%{python_sitelib}/Bcfg2/Server
%{python_sitelib}/Bcfg2/Reporting
%{python_sitelib}/Bcfg2/manage.py*
%exclude %{python_sitelib}/Bcfg2/Server/CherryPyCore.py

%dir %{_datadir}/bcfg2
%{_datadir}/bcfg2/schemas
%{_datadir}/bcfg2/xsl-transforms
%{_datadir}/bcfg2/Hostbase
%if 0%{?suse_version}
%{_sbindir}/rcbcfg2-server
%config(noreplace) /var/adm/fillup-templates/sysconfig.bcfg2-server
%endif

%{_mandir}/man5/bcfg2-lint.conf.5*
%{_mandir}/man8/bcfg2*.8*

%doc tools/*

%files server-cherrypy
%if 0%{?rhel} == 5 || 0%{?suse_version}
%defattr(-,root,root,-)
%endif
%{python_sitelib}/Bcfg2/Server/CherryPyCore.py

%files web
%if 0%{?rhel} == 5 || 0%{?suse_version}
%defattr(-,root,root,-)
%endif
%{_datadir}/bcfg2/reports.wsgi
%{_datadir}/bcfg2/site_media
%config(noreplace) %{apache_conf}/conf.d/wsgi_bcfg2.conf

%files doc
%if 0%{?rhel} == 5 || 0%{?suse_version}
%defattr(-,root,root,-)
%endif
%doc build/sphinx/html/*

%files examples
%if 0%{?rhel} == 5 || 0%{?suse_version}
%defattr(-,root,root,-)
%endif
%doc examples/*


%changelog
* Thu Nov 07 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.3-1
- New upstream release

* Sun Aug 04 2013 John Morris <john@zultron.com> - 1.3.2-2
- Reconcile divergences with Fedora specfile, as requested by upstream
  (equally large changes made in Fedora version to reconcile with
  this file)
- Python macro cleanups
- Accommodations for OpenSUSE
- Macros for pre and rc releases
- %%check section
- Move BRs to top of file
- Rearrange lines to match Fedora
- Group: tag tweaks
- Startup/shutdown changes
- Separate examples package
- Remove %%{__install} macros; RH has backed away from those
- Add fedora systemd units, both f16 and f18 variants :P
  - Changes to %%post* scripts
- Rearrange %%files sections

* Mon Jul 01 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.2-1
- New upstream release

* Thu Mar 21 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.1-1
- New upstream release

* Fri Mar 15 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.0-0.0
- New upstream release

* Tue Jan 29 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.0-0.0rc2
- New upstream release

* Wed Jan 09 2013 Sol Jerome <sol.jerome@gmail.com> 1.3.0-0.0rc1
- New upstream release

* Tue Oct 30 2012 Sol Jerome <sol.jerome@gmail.com> 1.3.0-0.0pre2
- New upstream release

* Wed Oct 17 2012 Chris St. Pierre <chris.a.st.pierre@gmail.com> 1.3.0-0.2pre1
- Split bcfg2-selinux into its own specfile

* Fri Sep 14 2012 Chris St. Pierre <chris.a.st.pierre@gmail.com> 1.3.0-0.1pre1
- Added -selinux subpackage

* Fri Aug 31 2012 Sol Jerome <sol.jerome@gmail.com> 1.3.0-0.0pre1
- New upstream release

* Wed Aug 15 2012 Chris St. Pierre <chris.a.st.pierre@gmail.com> 1.2.3-0.1
- Added tools/ as doc for bcfg2-server subpackage

* Sat Feb 18 2012 Christopher 'm4z' Holm <686f6c6d@googlemail.com> 1.2.1
- Added Fedora and Mandriva compatibilty (for Open Build Service).
- Added missing dependency redhat-lsb.

* Tue Feb 14 2012 Christopher 'm4z' Holm <686f6c6d@googlemail.com> 1.2.1
- Added openSUSE compatibility.
- Various changes to satisfy rpmlint.

* Thu Jan 27 2011 Chris St. Pierre <chris.a.st.pierre@gmail.com> 1.2.0pre1-0.0
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
